<template>
  <div class="view-root">
    <div class="view-header">
      <div>
        <h1 class="view-title">Backup &amp; Restore</h1>
        <p class="view-sub">Create AES-256 encrypted backups and restore them at any time.</p>
      </div>
    </div>

    <!-- Security notice -->
    <div class="security-notice">
      <svg viewBox="0 0 24 24"><path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4z"/></svg>
      <div>
        <strong>End-to-end encrypted</strong>
        Backups are encrypted with AES-256-GCM using a passphrase you choose. The passphrase is never stored — without it, the backup cannot be decrypted.
      </div>
    </div>

    <div class="panels">

      <!-- ── Create Backup ───────────────────────────────── -->
      <div class="panel">
        <div class="panel-header">
          <svg viewBox="0 0 24 24"><path d="M19 12v7H5v-7H3v7c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2v-7h-2zm-6 .67l2.59-2.58L17 11.5l-5 5-5-5 1.41-1.41L11 12.67V3h2z"/></svg>
          Create Backup
        </div>
        <div class="panel-body">
          <p class="panel-desc">Downloads a <code>.gwbak</code> file containing your database, themes, plugin configs, and optional config files.</p>

          <div class="form-group">
            <label>Encryption Passphrase <span class="required">*</span></label>
            <div class="password-wrap">
              <input
                :type="showPass ? 'text' : 'password'"
                v-model="createPass"
                class="form-input"
                placeholder="Choose a strong passphrase (min 8 chars)"
                @keyup.enter="createBackup"
              />
              <button class="toggle-vis" @click="showPass = !showPass" type="button">
                <svg v-if="showPass" viewBox="0 0 24 24"><path d="M12 7c2.76 0 5 2.24 5 5 0 .65-.13 1.26-.36 1.83l2.92 2.92c1.51-1.26 2.7-2.89 3.43-4.75-1.73-4.39-6-7.5-11-7.5-1.4 0-2.74.25-3.98.7l2.16 2.16C10.74 7.13 11.35 7 12 7zM2 4.27l2.28 2.28.46.46A11.804 11.804 0 001 12c1.73 4.39 6 7.5 11 7.5 1.55 0 3.03-.3 4.38-.84l.42.42L19.73 22 21 20.73 3.27 3 2 4.27zM7.53 9.8l1.55 1.55c-.05.21-.08.43-.08.65 0 1.66 1.34 3 3 3 .22 0 .44-.03.65-.08l1.55 1.55c-.67.33-1.41.53-2.2.53-2.76 0-5-2.24-5-5 0-.79.2-1.53.53-2.2zm4.31-.78l3.15 3.15.02-.16c0-1.66-1.34-3-3-3l-.17.01z"/></svg>
                <svg v-else viewBox="0 0 24 24"><path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"/></svg>
              </button>
            </div>
            <div class="pass-strength" v-if="createPass">
              <div class="strength-bar">
                <div class="strength-fill" :style="{ width: passStrength.pct + '%', background: passStrength.color }"></div>
              </div>
              <span :style="{ color: passStrength.color }">{{ passStrength.label }}</span>
            </div>
          </div>

          <div class="form-group">
            <label>Confirm Passphrase</label>
            <input :type="showPass ? 'text' : 'password'" v-model="confirmPass" class="form-input" placeholder="Re-enter passphrase" />
            <p v-if="confirmPass && createPass !== confirmPass" class="field-err">Passphrases do not match</p>
          </div>

          <div class="what-included">
            <div class="included-title">What's included:</div>
            <div class="included-items">
              <div class="included-item">
                <svg viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
                Full database snapshot
              </div>
              <div class="included-item">
                <svg viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
                All custom themes
              </div>
              <div class="included-item">
                <svg viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
                Plugin configs &amp; metadata
              </div>
              <div class="included-item">
                <svg viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
                Environment config files
              </div>
            </div>
          </div>

          <button
            class="btn-primary full"
            @click="createBackup"
            :disabled="creating || !createPass || createPass !== confirmPass || createPass.length < 8"
          >
            <svg v-if="!creating" viewBox="0 0 24 24"><path d="M19 12v7H5v-7H3v7c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2v-7h-2zm-6 .67l2.59-2.58L17 11.5l-5 5-5-5 1.41-1.41L11 12.67V3h2z"/></svg>
            <div v-else class="spinner-sm"></div>
            {{ creating ? 'Creating backup…' : 'Download Backup' }}
          </button>
        </div>
      </div>

      <!-- ── Restore Backup ──────────────────────────────── -->
      <div class="panel">
        <div class="panel-header">
          <svg viewBox="0 0 24 24"><path d="M12 5V1L7 6l5 5V7c3.31 0 6 2.69 6 6s-2.69 6-6 6-6-2.69-6-6H4c0 4.42 3.58 8 8 8s8-3.58 8-8-3.58-8-8-8z"/></svg>
          Restore from Backup
        </div>
        <div class="panel-body">
          <p class="panel-desc">Upload a <code>.gwbak</code> file to restore. You can choose which sections to restore.</p>

          <!-- File drop zone -->
          <div
            class="drop-zone"
            :class="{ dragover: isDragging, 'has-file': restoreFile }"
            @dragover.prevent="isDragging = true"
            @dragleave="isDragging = false"
            @drop.prevent="onDrop"
            @click="$refs.restoreInput.click()"
          >
            <input type="file" ref="restoreInput" accept=".gwbak" @change="onFileSelect" style="display:none" />
            <template v-if="!restoreFile">
              <svg viewBox="0 0 24 24"><path d="M19.35 10.04C18.67 6.59 15.64 4 12 4 9.11 4 6.6 5.64 5.35 8.04 2.34 8.36 0 10.91 0 14c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.65-4.96zM14 13v4h-4v-4H7l5-5 5 5h-3z"/></svg>
              <span>Drop .gwbak file here or <strong>click to browse</strong></span>
            </template>
            <template v-else>
              <svg viewBox="0 0 24 24" class="file-ok"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
              <span>{{ restoreFile.name }}</span>
              <button class="clear-file" @click.stop="clearFile">×</button>
            </template>
          </div>

          <!-- Manifest preview -->
          <div v-if="manifest" class="manifest-card">
            <div class="manifest-title">Backup Information</div>
            <div class="manifest-row"><span>Created</span><span>{{ formatDate(manifest.created_at) }}</span></div>
            <div class="manifest-row"><span>Hostname</span><span>{{ manifest.hostname }}</span></div>
            <div class="manifest-row"><span>Version</span><span>{{ manifest.ghostwire_version }}</span></div>
          </div>

          <div class="form-group" style="margin-top:16px">
            <label>Backup Passphrase</label>
            <input :type="showRestorePass ? 'text' : 'password'" v-model="restorePass" class="form-input" placeholder="Enter the backup's passphrase" />
          </div>

          <!-- Verify -->
          <button
            class="btn-secondary full"
            @click="peekBackup"
            :disabled="!restoreFile || !restorePass || peeking"
            style="margin-bottom:16px"
          >
            <div v-if="peeking" class="spinner-sm"></div>
            <svg v-else viewBox="0 0 24 24"><path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"/></svg>
            {{ peeking ? 'Verifying…' : 'Verify Passphrase' }}
          </button>

          <p v-if="peekError" class="field-err">{{ peekError }}</p>

          <!-- Restore options (shown after successful peek) -->
          <template v-if="manifest">
            <div class="restore-options">
              <div class="options-title">Restore sections:</div>
              <label class="option-row">
                <input type="checkbox" v-model="restoreOptions.restore_db" />
                <div>
                  <span class="option-name">Database</span>
                  <span class="option-desc">Users, VPN sessions, DNS events, all records. Requires service restart.</span>
                </div>
              </label>
              <label class="option-row">
                <input type="checkbox" v-model="restoreOptions.restore_themes" />
                <div>
                  <span class="option-name">Custom Themes</span>
                  <span class="option-desc">Re-import saved custom themes (built-ins are never overwritten).</span>
                </div>
              </label>
              <label class="option-row">
                <input type="checkbox" v-model="restoreOptions.restore_plugins" />
                <div>
                  <span class="option-name">Plugin Configs</span>
                  <span class="option-desc">Restore plugin configuration values (not plugin binaries).</span>
                </div>
              </label>
              <label class="option-row warning-row">
                <input type="checkbox" v-model="restoreOptions.restore_config" />
                <div>
                  <span class="option-name">Config Files <span class="warn-tag">Advanced</span></span>
                  <span class="option-desc">Overwrite .env and ipsec config files. Use with caution.</span>
                </div>
              </label>
            </div>

            <button
              class="btn-danger full"
              @click="confirmRestore"
              :disabled="restoring"
            >
              <div v-if="restoring" class="spinner-sm"></div>
              <svg v-else viewBox="0 0 24 24"><path d="M12 5V1L7 6l5 5V7c3.31 0 6 2.69 6 6s-2.69 6-6 6-6-2.69-6-6H4c0 4.42 3.58 8 8 8s8-3.58 8-8-3.58-8-8-8z"/></svg>
              {{ restoring ? 'Restoring…' : 'Restore Now' }}
            </button>
          </template>

          <!-- Restore result -->
          <div v-if="restoreResult" class="restore-result">
            <div class="result-title">
              <svg viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
              Restore complete
            </div>
            <div class="result-row" v-if="restoreResult.themes_restored">Themes restored: {{ restoreResult.themes_restored }}</div>
            <div class="result-row" v-if="restoreResult.plugins_restored">Plugin configs restored: {{ restoreResult.plugins_restored }}</div>
            <div class="result-row" v-if="restoreResult.db_restored">Database restored ✓ — restart the service to apply</div>
            <div class="result-warn" v-for="w in (restoreResult.warnings || [])" :key="w">⚠ {{ w }}</div>
          </div>

        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import api from '@/utils/api'

// Create
const createPass  = ref('')
const confirmPass = ref('')
const showPass    = ref(false)
const creating    = ref(false)

// Restore
const restoreFile     = ref(null)
const restorePass     = ref('')
const showRestorePass = ref(false)
const isDragging      = ref(false)
const peeking         = ref(false)
const peekError       = ref(null)
const manifest        = ref(null)
const restoring       = ref(false)
const restoreResult   = ref(null)
const restoreOptions  = ref({
  restore_db: true,
  restore_themes: true,
  restore_plugins: true,
  restore_config: false,
})

const passStrength = computed(() => {
  const p = createPass.value
  if (!p) return { pct: 0, color: 'var(--text3)', label: '' }
  let score = 0
  if (p.length >= 8)  score++
  if (p.length >= 16) score++
  if (/[A-Z]/.test(p)) score++
  if (/[0-9]/.test(p)) score++
  if (/[^A-Za-z0-9]/.test(p)) score++
  if (score <= 1) return { pct: 25,  color: 'var(--danger)',  label: 'Weak' }
  if (score <= 2) return { pct: 50,  color: 'var(--warning)', label: 'Fair' }
  if (score <= 3) return { pct: 75,  color: 'var(--info)',    label: 'Good' }
  return { pct: 100, color: 'var(--success)', label: 'Strong' }
})

async function createBackup() {
  if (!createPass.value || createPass.value !== confirmPass.value) return
  creating.value = true
  try {
    const resp = await api.post('/backup/create', { passphrase: createPass.value }, { responseType: 'blob' })
    const url  = URL.createObjectURL(new Blob([resp.data]))
    const a    = document.createElement('a')
    const cd   = resp.headers['content-disposition'] || ''
    const fnMatch = cd.match(/filename="?([^"]+)"?/)
    a.href     = url
    a.download = fnMatch ? fnMatch[1] : 'ghostwire-backup.gwbak'
    a.click()
    URL.revokeObjectURL(url)
    createPass.value  = ''
    confirmPass.value = ''
  } catch (e) {
    console.error('Backup failed', e)
  } finally {
    creating.value = false
  }
}

function onDrop(e) {
  isDragging.value = false
  const file = e.dataTransfer.files?.[0]
  if (file && file.name.endsWith('.gwbak')) {
    restoreFile.value = file
    manifest.value = null
    peekError.value = null
  }
}

function onFileSelect(e) {
  const file = e.target.files?.[0]
  if (file) {
    restoreFile.value = file
    manifest.value = null
    peekError.value = null
  }
}

function clearFile() {
  restoreFile.value = null
  manifest.value = null
  peekError.value = null
  restoreResult.value = null
}

async function peekBackup() {
  if (!restoreFile.value || !restorePass.value) return
  peeking.value = true
  peekError.value = null
  manifest.value = null
  try {
    const form = new FormData()
    form.append('file', restoreFile.value)
    form.append('passphrase', restorePass.value)
    const { data } = await api.post('/backup/peek', form, { headers: { 'Content-Type': 'multipart/form-data' } })
    manifest.value = data
  } catch (e) {
    peekError.value = e.response?.data?.detail || 'Wrong passphrase or invalid backup file'
  } finally {
    peeking.value = false
  }
}

async function confirmRestore() {
  if (!confirm('This will overwrite selected data. Are you sure you want to restore?')) return
  restoring.value = true
  restoreResult.value = null
  try {
    const form = new FormData()
    form.append('file', restoreFile.value)
    form.append('passphrase', restorePass.value)
    const params = new URLSearchParams({
      restore_db:      restoreOptions.value.restore_db,
      restore_themes:  restoreOptions.value.restore_themes,
      restore_plugins: restoreOptions.value.restore_plugins,
      restore_config:  restoreOptions.value.restore_config,
    })
    const { data } = await api.post(`/backup/restore?${params}`, form, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    restoreResult.value = data
  } catch (e) {
    peekError.value = e.response?.data?.detail || 'Restore failed'
  } finally {
    restoring.value = false
  }
}

function formatDate(iso) {
  if (!iso) return '—'
  try { return new Date(iso).toLocaleString() } catch { return iso }
}
</script>

<style scoped>
.view-root { padding: 28px 32px; max-width: 960px; }
.view-header { margin-bottom: 20px; }
.view-title { font-size: 22px; font-weight: 700; color: var(--text); margin-bottom: 4px; }
.view-sub { font-size: 13px; color: var(--text3); }

.security-notice { display: flex; align-items: flex-start; gap: 14px; background: rgba(52,211,153,0.07); border: 1px solid rgba(52,211,153,0.25); border-radius: var(--radius); padding: 14px 18px; margin-bottom: 28px; }
.security-notice svg { width: 22px; height: 22px; fill: var(--success); flex-shrink: 0; margin-top: 1px; }
.security-notice div { font-size: 13px; color: var(--text2); line-height: 1.5; }
.security-notice strong { color: var(--success); display: block; margin-bottom: 3px; }

.panels { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
@media (max-width: 780px) { .panels { grid-template-columns: 1fr; } }

.panel { background: var(--bg2); border: 1px solid var(--border); border-radius: var(--radius); overflow: hidden; }
.panel-header { display: flex; align-items: center; gap: 10px; padding: 16px 20px; border-bottom: 1px solid var(--border); font-size: 14px; font-weight: 700; color: var(--text); }
.panel-header svg { width: 18px; height: 18px; fill: var(--accent); }
.panel-body { padding: 20px; }
.panel-desc { font-size: 13px; color: var(--text3); margin-bottom: 18px; line-height: 1.5; }
.panel-desc code { background: var(--bg3); padding: 1px 6px; border-radius: 4px; font-size: 11px; }

.form-group { margin-bottom: 14px; }
.form-group label { display: block; font-size: 11px; font-weight: 600; color: var(--text3); text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 6px; }
.required { color: var(--danger); }
.form-input { width: 100%; background: var(--bg3); border: 1px solid var(--border); color: var(--text); border-radius: var(--radius-sm); padding: 8px 10px; font-size: 13px; outline: none; box-sizing: border-box; }
.form-input:focus { border-color: var(--accent); }
.password-wrap { position: relative; }
.password-wrap .form-input { padding-right: 38px; }
.toggle-vis { position: absolute; right: 8px; top: 50%; transform: translateY(-50%); background: none; border: none; color: var(--text3); cursor: pointer; padding: 2px; display: flex; }
.toggle-vis svg { width: 16px; height: 16px; fill: currentColor; }
.toggle-vis:hover { color: var(--text); }
.field-err { font-size: 12px; color: var(--danger); margin-top: 5px; }

.pass-strength { display: flex; align-items: center; gap: 8px; margin-top: 6px; }
.strength-bar { flex: 1; height: 3px; background: var(--border); border-radius: 2px; overflow: hidden; }
.strength-fill { height: 100%; border-radius: 2px; transition: width 0.3s, background 0.3s; }
.pass-strength span { font-size: 11px; font-weight: 600; }

.what-included { background: var(--bg3); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 12px 14px; margin-bottom: 16px; }
.included-title { font-size: 11px; font-weight: 700; color: var(--text3); text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 8px; }
.included-items { display: flex; flex-direction: column; gap: 5px; }
.included-item { display: flex; align-items: center; gap: 7px; font-size: 12px; color: var(--text2); }
.included-item svg { width: 12px; height: 12px; fill: var(--success); flex-shrink: 0; }

.btn-primary { background: var(--accent); color: #fff; border: none; padding: 10px 20px; border-radius: var(--radius-sm); font-size: 13px; font-weight: 600; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 8px; transition: opacity 0.15s; }
.btn-primary:hover { opacity: 0.85; }
.btn-primary:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-secondary { background: transparent; color: var(--text2); border: 1px solid var(--border); padding: 9px 16px; border-radius: var(--radius-sm); font-size: 13px; font-weight: 600; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 8px; transition: all 0.15s; }
.btn-secondary svg { width: 16px; height: 16px; fill: currentColor; }
.btn-secondary:hover { border-color: var(--accent); color: var(--accent); }
.btn-secondary:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-danger { background: rgba(248,113,113,0.12); color: var(--danger); border: 1px solid rgba(248,113,113,0.3); padding: 10px 16px; border-radius: var(--radius-sm); font-size: 13px; font-weight: 600; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 8px; transition: all 0.15s; }
.btn-danger:hover { background: rgba(248,113,113,0.22); }
.btn-danger:disabled { opacity: 0.4; cursor: not-allowed; }
.full { width: 100%; }

.spinner-sm { width: 16px; height: 16px; border: 2px solid rgba(255,255,255,0.3); border-top-color: #fff; border-radius: 50%; animation: spin 0.7s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* Drop zone */
.drop-zone { border: 2px dashed var(--border); border-radius: var(--radius-sm); padding: 28px 20px; text-align: center; color: var(--text3); cursor: pointer; transition: all 0.2s; font-size: 13px; display: flex; flex-direction: column; align-items: center; gap: 8px; margin-bottom: 16px; position: relative; }
.drop-zone svg { width: 32px; height: 32px; fill: currentColor; }
.drop-zone:hover, .drop-zone.dragover { border-color: var(--accent); color: var(--accent); background: rgba(99,102,241,0.05); }
.drop-zone.has-file { border-color: var(--success); color: var(--success); background: rgba(52,211,153,0.05); }
.drop-zone.has-file svg.file-ok { fill: var(--success); }
.clear-file { position: absolute; top: 8px; right: 8px; background: none; border: none; color: var(--text3); font-size: 18px; cursor: pointer; line-height: 1; }
.clear-file:hover { color: var(--danger); }

/* Manifest card */
.manifest-card { background: var(--bg3); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 12px 14px; margin-bottom: 4px; }
.manifest-title { font-size: 11px; font-weight: 700; color: var(--accent); text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 8px; }
.manifest-row { display: flex; justify-content: space-between; font-size: 12px; padding: 3px 0; border-bottom: 1px solid var(--border); }
.manifest-row:last-child { border-bottom: none; }
.manifest-row span:first-child { color: var(--text3); }
.manifest-row span:last-child { color: var(--text); font-weight: 600; }

/* Restore options */
.restore-options { background: var(--bg3); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 14px; margin-bottom: 14px; }
.options-title { font-size: 11px; font-weight: 700; color: var(--text3); text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 10px; }
.option-row { display: flex; align-items: flex-start; gap: 10px; padding: 7px 0; border-bottom: 1px solid var(--border); cursor: pointer; }
.option-row:last-child { border-bottom: none; }
.option-row input[type="checkbox"] { margin-top: 3px; accent-color: var(--accent); flex-shrink: 0; }
.option-name { display: block; font-size: 13px; color: var(--text); font-weight: 600; }
.option-desc { display: block; font-size: 11px; color: var(--text3); margin-top: 2px; line-height: 1.4; }
.warn-tag { font-size: 10px; background: rgba(251,191,36,0.15); color: var(--warning); border: 1px solid rgba(251,191,36,0.25); border-radius: 8px; padding: 0 6px; margin-left: 6px; vertical-align: middle; }

/* Restore result */
.restore-result { background: rgba(52,211,153,0.07); border: 1px solid rgba(52,211,153,0.25); border-radius: var(--radius-sm); padding: 14px 16px; margin-top: 14px; }
.result-title { display: flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 700; color: var(--success); margin-bottom: 8px; }
.result-title svg { width: 16px; height: 16px; fill: currentColor; }
.result-row { font-size: 12px; color: var(--text2); padding: 2px 0; }
.result-warn { font-size: 12px; color: var(--warning); padding: 2px 0; }
</style>
