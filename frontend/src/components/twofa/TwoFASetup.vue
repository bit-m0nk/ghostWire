<template>
  <div class="twofa-panel">

    <!-- Status bar -->
    <div class="status-bar" :class="status.totp_enabled ? 'status-on' : 'status-off'">
      <span class="status-dot"></span>
      <span>Two-factor authentication is <strong>{{ status.totp_enabled ? 'enabled' : 'disabled' }}</strong></span>
    </div>

    <!-- Already enabled: show disable form -->
    <div v-if="status.totp_enabled" class="card mt-3">
      <div class="card-title">🔐 Disable 2FA</div>
      <p class="text-muted text-sm mb-3">
        You will need your authenticator app code and your panel password to disable 2FA.
      </p>
      <div class="form-group">
        <label>Current panel password</label>
        <input v-model="disable.password" type="password" placeholder="Your panel password" />
      </div>
      <div class="form-group">
        <label>Authenticator code</label>
        <input v-model="disable.code" type="text" inputmode="numeric" maxlength="6"
               placeholder="000000" class="code-input" />
      </div>
      <div v-if="disableError" class="alert alert-danger">{{ disableError }}</div>
      <div v-if="disableOk" class="alert alert-success">{{ disableOk }}</div>
      <button class="btn-danger" @click="doDisable" :disabled="disabling">
        {{ disabling ? 'Disabling…' : 'Disable 2FA' }}
      </button>
    </div>

    <!-- Not yet enabled: setup flow -->
    <div v-else>
      <!-- Step 1: initiate setup -->
      <div v-if="!qrVisible" class="card mt-3">
        <div class="card-title">📱 Set up authenticator app</div>
        <p class="text-muted text-sm mb-3">
          Use any TOTP app — Google Authenticator, Authy, 1Password, Bitwarden, or any RFC 6238 compatible app.
        </p>
        <button class="btn-primary" @click="startSetup" :disabled="setupLoading">
          {{ setupLoading ? 'Loading…' : 'Set up 2FA' }}
        </button>
        <div v-if="setupError" class="alert alert-danger mt-2">{{ setupError }}</div>
      </div>

      <!-- Step 2: scan QR + confirm -->
      <div v-else class="card mt-3">
        <div class="card-title">📷 Scan QR code</div>
        <p class="text-muted text-sm mb-3">
          Scan this QR code with your authenticator app (Google Authenticator, Authy, 1Password, Bitwarden…),
          then enter the 6-digit code below to confirm.
        </p>

        <!-- QR code rendered as SVG from backend -->
        <div class="qr-wrap" v-if="qrSvg">
          <div class="qr-inner" v-html="qrSvg"></div>
        </div>
        <div v-else-if="setupLoading" class="qr-placeholder">
          <div class="qr-spinner"></div>
          <span class="text-muted text-sm" style="margin-top:8px">Loading QR code…</span>
        </div>
        <div v-else class="qr-placeholder">
          <span class="text-muted text-sm">⚠ QR code failed to load — use the manual key below</span>
        </div>

        <!-- Manual entry fallback — secret grouped in 4-char chunks -->
        <details class="manual-secret mt-2">
          <summary class="text-sm" style="cursor:pointer;color:var(--text2)">
            Can't scan? Enter the key manually
          </summary>
          <div class="mt-2" style="font-size:12px;color:var(--text3);margin-bottom:6px">
            In your authenticator app choose <strong>"Enter a setup key"</strong> and type:
          </div>
          <div class="secret-box mt-1">
            <code class="grouped-secret">{{ groupedSecret }}</code>
            <button class="btn-ghost btn-sm" @click="copySecret" title="Copy to clipboard">📋 Copy</button>
          </div>
          <div style="font-size:11px;color:var(--text3);margin-top:6px">
            Type: <strong>Time-based (TOTP)</strong> &nbsp;·&nbsp; Period: 30 s &nbsp;·&nbsp; Digits: 6
          </div>
        </details>

        <div class="form-group mt-3">
          <label>Panel password (re-confirm)</label>
          <input v-model="confirm.password" type="password" placeholder="Your panel password" />
        </div>
        <div class="form-group">
          <label>6-digit code from your app</label>
          <input v-model="confirm.code" type="text" inputmode="numeric" maxlength="6"
                 placeholder="000000" class="code-input" />
        </div>
        <div v-if="confirmError" class="alert alert-danger">{{ confirmError }}</div>
        <div v-if="confirmOk" class="alert alert-success">{{ confirmOk }}</div>
        <div class="flex gap-2 mt-2">
          <button class="btn-primary" @click="doConfirm"
                  :disabled="confirming || confirm.code.length < 6">
            {{ confirming ? 'Activating…' : 'Activate 2FA' }}
          </button>
          <button class="btn-ghost" @click="qrVisible=false">Cancel</button>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import api from '@/utils/api'

const status       = ref({ totp_enabled: false, has_secret: false })
const qrVisible    = ref(false)
const qrSvg        = ref('')
const setupSecret  = ref('')
// Display secret in groups of 4 chars — much easier to type manually
const groupedSecret = computed(() => {
  if (!setupSecret.value) return ''
  return setupSecret.value.match(/.{1,4}/g)?.join(' ') || setupSecret.value
})
const setupLoading = ref(false)
const setupError   = ref('')

const confirm      = ref({ password: '', code: '' })
const confirming   = ref(false)
const confirmError = ref('')
const confirmOk    = ref('')

const disable      = ref({ password: '', code: '' })
const disabling    = ref(false)
const disableError = ref('')
const disableOk    = ref('')

onMounted(fetchStatus)

async function fetchStatus() {
  try {
    const { data } = await api.get('/2fa/status')
    status.value = data
  } catch (e) {
    console.error('2FA status fetch failed', e)
  }
}

async function startSetup() {
  setupLoading.value = true
  setupError.value   = ''
  try {
    // Step 1: generate/retrieve secret (also stores it server-side)
    const { data } = await api.get('/2fa/setup')
    setupSecret.value = data.secret

    // Step 2: show the QR panel immediately with a loading placeholder,
    //         then fetch the SVG via native fetch() — NOT axios.
    //
    //         WHY: axios intercepts the response and, even with
    //         responseType:'text', may return a parsed object or empty string
    //         when the Content-Type is image/svg+xml. v-html then receives a
    //         non-string value and renders nothing. fetch().text() always
    //         returns the raw response body as a string regardless of MIME type.
    qrSvg.value     = ''
    qrVisible.value = true

    const token = localStorage.getItem('ghostwire_token')
    const res = await fetch('/api/2fa/setup/qr', {
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: 'image/svg+xml, text/plain, */*',
      },
    })
    if (!res.ok) throw new Error(`QR fetch failed: HTTP ${res.status}`)
    const svg = await res.text()
    if (!svg || !svg.includes('<svg')) throw new Error('Invalid QR response — check backend logs')
    qrSvg.value = svg
  } catch (e) {
    // If something fails after qrVisible was set, roll back so the
    // user sees the error on the first step, not a blank QR panel.
    qrVisible.value    = false
    setupError.value   = e.message || 'Setup failed — please try again'
  } finally {
    setupLoading.value = false
  }
}

async function doConfirm() {
  confirming.value  = true
  confirmError.value = ''
  confirmOk.value   = ''
  try {
    await api.post('/2fa/setup/confirm', {
      password: confirm.value.password,
      code:     confirm.value.code.trim(),
    })
    confirmOk.value = '✓ 2FA enabled! Your account is now protected.'
    await fetchStatus()
    qrVisible.value = false
  } catch (e) {
    confirmError.value = e.response?.data?.detail || 'Confirmation failed'
  } finally {
    confirming.value = false
  }
}

async function doDisable() {
  disabling.value    = true
  disableError.value = ''
  disableOk.value    = ''
  try {
    await api.post('/2fa/disable', {
      password: disable.value.password,
      code:     disable.value.code.trim(),
    })
    disableOk.value = '2FA has been disabled.'
    disable.value   = { password: '', code: '' }
    await fetchStatus()
  } catch (e) {
    disableError.value = e.response?.data?.detail || 'Failed to disable 2FA'
  } finally {
    disabling.value = false
  }
}

function copySecret() {
  // Copy the raw secret (no spaces) — authenticator apps want the plain base32 string
  navigator.clipboard?.writeText(setupSecret.value).catch(() => {})
}
</script>

<style scoped>
.twofa-panel { max-width: 520px; }
.status-bar {
  display: flex; align-items: center; gap: 10px;
  padding: 12px 16px; border-radius: var(--radius-sm);
  font-size: 13px; border: 1px solid;
}
.status-on  { background: rgba(52,211,153,0.1);  border-color: rgba(52,211,153,0.3);  color: var(--success); }
.status-off { background: rgba(148,163,184,0.08); border-color: var(--border);          color: var(--text2); }
.status-dot { width:8px; height:8px; border-radius:50%; flex-shrink:0;
              background: currentColor; box-shadow: 0 0 6px currentColor; }
.qr-wrap {
  display: flex; justify-content: center; align-items: center;
  padding: 12px; background: #fff; border-radius: 10px;
  border: 2px solid rgba(99,102,241,0.2);
}
.qr-inner { display: flex; align-items: center; justify-content: center; }
.qr-inner svg { width: 220px !important; height: 220px !important;
                display: block; max-width: 100%; }
.qr-placeholder {
  display: flex; flex-direction: column; justify-content: center; align-items: center;
  height: 140px; background: var(--bg3); border-radius: 8px;
  border: 1px dashed var(--border); gap: 4px;
}
.qr-spinner {
  width: 28px; height: 28px; border: 3px solid var(--border);
  border-top-color: var(--accent); border-radius: 50%;
  animation: qr-spin 0.8s linear infinite;
}
@keyframes qr-spin { to { transform: rotate(360deg); } }
.code-input { text-align:center; font-size:22px; font-weight:700;
              letter-spacing:8px; font-family:monospace; color:var(--accent); }
.manual-secret { margin-top: 8px; }
.secret-box { display:flex; align-items:center; gap:8px;
              background:var(--bg3); padding:10px 12px; border-radius:6px;
              border: 1px solid var(--border); }
.secret-box code { font-family:monospace; color:var(--accent2);
                   word-break:break-all; flex:1; }
.grouped-secret { font-size:14px; font-weight:600; letter-spacing:2px; }
.mt-1 { margin-top: 4px; }
.mt-2 { margin-top: 8px; }
.mt-3 { margin-top: 16px; }
</style>
