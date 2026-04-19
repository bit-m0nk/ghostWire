<template>
  <div class="config-page">
    <div class="page-header">
      <h2 class="page-title">Configuration</h2>
      <span class="text-muted text-sm">Changes are saved to <code>/opt/ghostwire/.env</code></span>
    </div>

    <!-- Tab bar -->
    <div class="tab-bar">
      <button v-for="t in tabs" :key="t.id"
        class="tab-btn" :class="{ active: tab === t.id }"
        @click="tab = t.id">
        <span class="tab-icon">{{ t.icon }}</span>
        {{ t.label }}
        <span v-if="t.id === 'smtp' && smtpOk" class="tab-badge tab-ok">✓</span>
        <span v-if="t.id === 'smtp' && !smtpOk" class="tab-badge tab-warn">!</span>
        <span v-if="t.id === 'ddns' && ddnsEnabled" class="tab-badge tab-ok">✓</span>
        <span v-if="t.id === 'notif' && tgOk" class="tab-badge tab-ok">✓</span>
      </button>
    </div>

    <!-- ── SMTP ─────────────────────────────────────────────────────────── -->
    <div v-if="tab === 'smtp'" class="card">
      <div class="card-title">📧 SMTP / Email Settings</div>
      <p class="section-desc">Used to send welcome emails to new users and IP-change alerts to admins.</p>

      <div class="field-grid">
        <div class="form-group">
          <label>SMTP Host *</label>
          <input v-model="smtp.host" placeholder="smtp.gmail.com" />
        </div>
        <div class="form-group">
          <label>Port</label>
          <select v-model.number="smtp.port">
            <option :value="587">587 — STARTTLS (recommended)</option>
            <option :value="465">465 — SSL/TLS</option>
            <option :value="25">25 — Plain (not recommended)</option>
          </select>
        </div>
        <div class="form-group">
          <label>TLS Mode</label>
          <select v-model="smtp.tls">
            <option value="starttls">STARTTLS</option>
            <option value="ssl">SSL</option>
            <option value="none">None</option>
          </select>
        </div>
        <div class="form-group">
          <label>SMTP Username</label>
          <input v-model="smtp.user" placeholder="you@gmail.com" autocomplete="off" />
        </div>
        <div class="form-group">
          <label>SMTP Password
            <span v-if="smtp.has_password && !smtp.password" class="saved-badge">● saved</span>
          </label>
          <input v-model="smtp.password" type="password"
            :placeholder="smtp.has_password ? 'Leave blank to keep current' : 'Enter password'"
            autocomplete="new-password" />
        </div>
        <div class="form-group">
          <label>From Address <span class="text-muted">(defaults to username)</span></label>
          <input v-model="smtp.from_addr" placeholder="vpn@yourdomain.com" />
        </div>
        <div class="form-group span-2">
          <label>Notify Email <span class="text-muted">(admin alerts go here)</span></label>
          <input v-model="smtp.notify_email" type="email" placeholder="admin@yourdomain.com" />
        </div>
      </div>

      <div class="action-row">
        <button class="btn-primary" @click="saveSmtp" :disabled="smtp.saving">
          {{ smtp.saving ? 'Saving…' : 'Save SMTP Settings' }}
        </button>
        <button class="btn-ghost" @click="testSmtp" :disabled="smtp.testing || !smtpOk">
          {{ smtp.testing ? 'Sending…' : 'Send Test Email' }}
        </button>
        <div class="status-pill" :class="smtpOk ? 'pill-ok' : 'pill-warn'">
          <span class="pill-dot"></span>
          {{ smtpOk ? `Configured · ${smtp.host}` : 'Not configured' }}
        </div>
      </div>

      <div v-if="smtp.msg" class="alert mt-2" :class="`alert-${smtp.msgType}`">{{ smtp.msg }}</div>

      <div class="hint-box">
        <strong>Gmail tip:</strong> Use an <a href="https://myaccount.google.com/apppasswords" target="_blank">App Password</a>,
        not your account password. Set port 587 + STARTTLS.
      </div>
    </div>

    <!-- ── DDNS ─────────────────────────────────────────────────────────── -->
    <div v-if="tab === 'ddns'" class="card">
      <div class="card-title">🌐 Dynamic DNS (DDNS)</div>
      <p class="section-desc">
        Keeps your VPN hostname updated when your home IP changes.
        Supports <strong>Dynu</strong> (primary) and <strong>No-IP</strong> as failover.
      </p>

      <div class="form-group">
        <label class="toggle-label">
          <div class="toggle-wrap">
            <input type="checkbox" v-model="ddns.use_ddns" class="toggle-input" />
            <span class="toggle-track"><span class="toggle-thumb"></span></span>
          </div>
          Enable DDNS
        </label>
      </div>

      <template v-if="ddns.use_ddns">
        <div class="field-grid">
          <div class="form-group">
            <label>Primary provider</label>
            <select v-model="ddns.ddns_primary">
              <option value="dynu">Dynu (recommended — free)</option>
              <option value="noip">No-IP</option>
            </select>
          </div>
          <div class="form-group">
            <label>Public hostname <span class="text-muted">(what users connect to)</span></label>
            <input v-model="ddns.ddns_hostname" placeholder="myvpn.dynu.net" />
          </div>
        </div>

        <div class="provider-section">
          <div class="provider-header">
            <span class="provider-logo dynu-logo">D</span>
            Dynu DDNS
            <span class="provider-badge" :class="ddns.dynu_username && ddns.dynu_has_password ? 'badge-success' : 'badge-gray'">
              {{ ddns.dynu_username && ddns.dynu_has_password ? 'Configured' : 'Incomplete' }}
            </span>
          </div>
          <div class="field-grid">
            <div class="form-group">
              <label>Dynu Hostname</label>
              <input v-model="ddns.dynu_hostname" placeholder="myvpn.dynu.net" />
            </div>
            <div class="form-group">
              <label>Dynu Username</label>
              <input v-model="ddns.dynu_username" placeholder="your-dynu-username" autocomplete="off" />
            </div>
            <div class="form-group span-2">
              <label>IP Update Password
                <span v-if="ddns.dynu_has_password && !ddns.dynu_ip_update_pass" class="saved-badge">● saved</span>
                <span class="text-muted"> — from <a href="https://www.dynu.com/ControlPanel/APICredentials" target="_blank">dynu.com/ControlPanel/APICredentials</a></span>
              </label>
              <input v-model="ddns.dynu_ip_update_pass" type="password"
                :placeholder="ddns.dynu_has_password ? 'Leave blank to keep current' : 'IP Update Password (not login password)'"
                autocomplete="new-password" />
            </div>
          </div>
        </div>

        <div class="provider-section">
          <div class="provider-header">
            <span class="provider-logo noip-logo">N</span>
            No-IP DDNS <span class="text-muted text-sm">(failover)</span>
            <span class="provider-badge" :class="ddns.noip_username && ddns.noip_has_password ? 'badge-success' : 'badge-gray'">
              {{ ddns.noip_username && ddns.noip_has_password ? 'Configured' : 'Incomplete' }}
            </span>
          </div>
          <div class="field-grid">
            <div class="form-group">
              <label>No-IP Hostname</label>
              <input v-model="ddns.noip_hostname" placeholder="myvpn.ddns.net" />
            </div>
            <div class="form-group">
              <label>No-IP Username / Email</label>
              <input v-model="ddns.noip_username" placeholder="you@email.com" autocomplete="off" />
            </div>
            <div class="form-group span-2">
              <label>No-IP Password
                <span v-if="ddns.noip_has_password && !ddns.noip_password" class="saved-badge">● saved</span>
              </label>
              <input v-model="ddns.noip_password" type="password"
                :placeholder="ddns.noip_has_password ? 'Leave blank to keep current' : 'Password'"
                autocomplete="new-password" />
            </div>
          </div>
        </div>
      </template>

      <div class="action-row">
        <button class="btn-primary" @click="saveDdns" :disabled="ddns.saving">
          {{ ddns.saving ? 'Saving…' : 'Save DDNS Settings' }}
        </button>
        <div class="status-pill" :class="ddnsEnabled ? 'pill-ok' : 'pill-warn'">
          <span class="pill-dot"></span>
          {{ ddnsEnabled ? `Enabled · ${ddns.ddns_primary} · ${ddns.ddns_hostname || 'no hostname'}` : 'Disabled' }}
        </div>
      </div>
      <div v-if="ddns.msg" class="alert mt-2" :class="`alert-${ddns.msgType}`">{{ ddns.msg }}</div>
    </div>

    <!-- ── Notifications ─────────────────────────────────────────────────── -->
    <div v-if="tab === 'notif'" class="card">
      <div class="card-title">🔔 Notifications</div>
      <p class="section-desc">Get notified when your server IP changes or something goes wrong.</p>

      <div class="provider-section">
        <div class="provider-header">
          <span class="provider-logo tg-logo">✈</span>
          Telegram Bot
          <span class="provider-badge" :class="tgOk ? 'badge-success' : 'badge-gray'">
            {{ tgOk ? 'Configured' : 'Not configured' }}
          </span>
        </div>
        <div class="field-grid">
          <div class="form-group">
            <label>Bot Token
              <span v-if="notif.tg_enabled && !notif.tg_bot_token" class="saved-badge">● saved</span>
            </label>
            <input v-model="notif.tg_bot_token" type="password"
              :placeholder="notif.tg_enabled ? 'Leave blank to keep current' : '1234567890:AAF...'"
              autocomplete="off" />
          </div>
          <div class="form-group">
            <label>Chat ID</label>
            <input v-model="notif.tg_chat_id" placeholder="-1001234567890" />
          </div>
        </div>
        <div class="hint-box">
          Create a bot via <a href="https://t.me/BotFather" target="_blank">@BotFather</a>.
          Get your Chat ID by messaging <a href="https://t.me/userinfobot" target="_blank">@userinfobot</a>.
        </div>
      </div>

      <div class="provider-section">
        <div class="provider-header">
          <span class="provider-logo email-logo">@</span>
          Email Alerts
        </div>
        <div class="form-group" style="max-width:360px">
          <label>Alert recipient email</label>
          <input v-model="notif.notify_email" type="email" placeholder="admin@yourdomain.com" />
          <div class="text-muted text-sm mt-1">Uses the SMTP settings from the Email tab.</div>
        </div>
      </div>

      <div class="action-row">
        <button class="btn-primary" @click="saveNotif" :disabled="notif.saving">
          {{ notif.saving ? 'Saving…' : 'Save Notification Settings' }}
        </button>
      </div>
      <div v-if="notif.msg" class="alert mt-2" :class="`alert-${notif.msgType}`">{{ notif.msg }}</div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '@/utils/api'

const tab = ref('smtp')
const tabs = [
  { id: 'smtp',  icon: '📧', label: 'Email / SMTP' },
  { id: 'ddns',  icon: '🌐', label: 'DDNS' },
  { id: 'notif', icon: '🔔', label: 'Notifications' },
]

// ── SMTP state ────────────────────────────────────────────────────────────────
const smtp = ref({
  host: '', port: 587, user: '', password: '', tls: 'starttls',
  from_addr: '', notify_email: '', has_password: false,
  saving: false, testing: false, msg: '', msgType: 'info',
})

const smtpOk = computed(() => !!smtp.value.host)

async function loadSmtp() {
  try {
    const { data } = await api.get('/config/smtp')
    Object.assign(smtp.value, {
      host:         data.host         || '',
      port:         data.port         || 587,
      user:         data.user         || '',
      tls:          data.tls          || 'starttls',
      from_addr:    data.from_addr    || '',
      notify_email: data.notify_email || '',
      has_password: data.has_password || false,
      password: '',   // never pre-fill password
    })
  } catch {}
}

async function saveSmtp() {
  smtp.value.saving = true; smtp.value.msg = ''
  try {
    const payload = {
      host:         smtp.value.host,
      port:         smtp.value.port,
      user:         smtp.value.user,
      tls:          smtp.value.tls,
      from_addr:    smtp.value.from_addr,
      notify_email: smtp.value.notify_email,
    }
    // Only send password if the field was touched
    if (smtp.value.password) payload.password = smtp.value.password
    const { data } = await api.post('/config/smtp', payload)
    smtp.value.msg = data.message || 'Saved'
    smtp.value.msgType = 'success'
    smtp.value.password = ''
    smtp.value.has_password = true
    await loadSmtp()
  } catch (e) {
    smtp.value.msg = e.response?.data?.detail || 'Save failed'
    smtp.value.msgType = 'danger'
  } finally {
    smtp.value.saving = false
    setTimeout(() => smtp.value.msg = '', 6000)
  }
}

async function testSmtp() {
  smtp.value.testing = true; smtp.value.msg = ''
  try {
    const { data } = await api.post('/config/smtp/test')
    smtp.value.msg = data.message; smtp.value.msgType = 'success'
  } catch (e) {
    smtp.value.msg = e.response?.data?.detail || 'Test failed'
    smtp.value.msgType = 'danger'
  } finally {
    smtp.value.testing = false
    setTimeout(() => smtp.value.msg = '', 8000)
  }
}

// ── DDNS state ────────────────────────────────────────────────────────────────
const ddns = ref({
  use_ddns: false, ddns_primary: 'dynu', ddns_hostname: '',
  dynu_hostname: '', dynu_username: '', dynu_ip_update_pass: '', dynu_has_password: false,
  noip_hostname: '', noip_username: '', noip_password: '', noip_has_password: false,
  saving: false, msg: '', msgType: 'info',
})

const ddnsEnabled = computed(() => ddns.value.use_ddns)

async function loadDdns() {
  try {
    const { data } = await api.get('/config/ddns')
    Object.assign(ddns.value, {
      use_ddns:        data.use_ddns       || false,
      ddns_primary:    data.ddns_primary   || 'dynu',
      ddns_hostname:   data.ddns_hostname  || '',
      dynu_hostname:   data.dynu_hostname  || '',
      dynu_username:   data.dynu_username  || '',
      dynu_has_password: data.dynu_has_password || false,
      noip_hostname:   data.noip_hostname  || '',
      noip_username:   data.noip_username  || '',
      noip_has_password: data.noip_has_password || false,
      dynu_ip_update_pass: '',
      noip_password: '',
    })
  } catch {}
}

async function saveDdns() {
  ddns.value.saving = true; ddns.value.msg = ''
  try {
    const payload = {
      use_ddns:      ddns.value.use_ddns,
      ddns_primary:  ddns.value.ddns_primary,
      ddns_hostname: ddns.value.ddns_hostname,
      dynu_hostname: ddns.value.dynu_hostname,
      dynu_username: ddns.value.dynu_username,
      noip_hostname: ddns.value.noip_hostname,
      noip_username: ddns.value.noip_username,
    }
    if (ddns.value.dynu_ip_update_pass) payload.dynu_ip_update_pass = ddns.value.dynu_ip_update_pass
    if (ddns.value.noip_password)       payload.noip_password       = ddns.value.noip_password
    const { data } = await api.post('/config/ddns', payload)
    ddns.value.msg = data.message || 'Saved'; ddns.value.msgType = 'success'
    ddns.value.dynu_ip_update_pass = ''; ddns.value.noip_password = ''
    await loadDdns()
  } catch (e) {
    ddns.value.msg = e.response?.data?.detail || 'Save failed'; ddns.value.msgType = 'danger'
  } finally {
    ddns.value.saving = false
    setTimeout(() => ddns.value.msg = '', 6000)
  }
}

// ── Notifications state ───────────────────────────────────────────────────────
const notif = ref({
  tg_enabled: false, tg_bot_token: '', tg_chat_id: '', notify_email: '',
  saving: false, msg: '', msgType: 'info',
})

const tgOk = computed(() => notif.value.tg_enabled)

async function loadNotif() {
  try {
    const { data } = await api.get('/config/notifications')
    Object.assign(notif.value, {
      tg_enabled:  data.tg_enabled   || false,
      tg_chat_id:  data.tg_chat_id   || '',
      notify_email: data.notify_email || '',
      tg_bot_token: '',
    })
  } catch {}
}

async function saveNotif() {
  notif.value.saving = true; notif.value.msg = ''
  try {
    const payload = {
      tg_chat_id:   notif.value.tg_chat_id,
      notify_email: notif.value.notify_email,
    }
    if (notif.value.tg_bot_token) payload.tg_bot_token = notif.value.tg_bot_token
    const { data } = await api.post('/config/notifications', payload)
    notif.value.msg = data.message || 'Saved'; notif.value.msgType = 'success'
    notif.value.tg_bot_token = ''
    await loadNotif()
  } catch (e) {
    notif.value.msg = e.response?.data?.detail || 'Save failed'; notif.value.msgType = 'danger'
  } finally {
    notif.value.saving = false
    setTimeout(() => notif.value.msg = '', 6000)
  }
}

onMounted(() => {
  loadSmtp()
  loadDdns()
  loadNotif()
})
</script>

<style scoped>
.config-page { display: flex; flex-direction: column; gap: 20px; padding-bottom: 32px; }
.page-header { display: flex; justify-content: space-between; align-items: center; }
.page-title  { font-size: 20px; font-weight: 700; }

/* Tab bar */
.tab-bar { display: flex; gap: 4px; background: var(--bg2); border: 1px solid var(--border); border-radius: var(--radius); padding: 4px; width: fit-content; }
.tab-btn {
  display: flex; align-items: center; gap: 6px;
  padding: 7px 16px; border-radius: 7px; font-size: 13px; font-weight: 500;
  color: var(--text2); background: transparent; border: none;
  transition: all 0.15s; cursor: pointer; position: relative;
}
.tab-btn:hover { color: var(--text); background: var(--bg3); }
.tab-btn.active { background: var(--bg3); color: var(--text); box-shadow: 0 1px 4px rgba(0,0,0,0.3); }
.tab-icon { font-size: 14px; }
.tab-badge {
  font-size: 10px; font-weight: 700; padding: 1px 5px;
  border-radius: 10px; line-height: 1.4;
}
.tab-ok   { background: rgba(52,211,153,0.2); color: var(--success); }
.tab-warn { background: rgba(251,191,36,0.2); color: var(--warning); }

/* Section description */
.section-desc { font-size: 13px; color: var(--text2); margin-bottom: 20px; line-height: 1.6; }

/* Field grid */
.field-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0 16px; }
.span-2 { grid-column: span 2; }
@media (max-width: 640px) { .field-grid { grid-template-columns: 1fr; } .span-2 { grid-column: span 1; } }

/* Saved badge */
.saved-badge { font-size: 10px; color: var(--success); background: rgba(52,211,153,0.15); padding: 1px 6px; border-radius: 10px; margin-left: 4px; font-weight: 600; }

/* Action row */
.action-row { display: flex; align-items: center; gap: 12px; margin-top: 20px; flex-wrap: wrap; }

/* Status pill */
.status-pill { display: flex; align-items: center; gap: 6px; font-size: 12px; padding: 5px 12px; border-radius: 20px; font-weight: 500; }
.pill-ok   { background: rgba(52,211,153,0.1); color: var(--success); border: 1px solid rgba(52,211,153,0.2); }
.pill-warn { background: rgba(251,191,36,0.1);  color: var(--warning); border: 1px solid rgba(251,191,36,0.2); }
.pill-dot  { width: 6px; height: 6px; border-radius: 50%; background: currentColor; }

/* Provider sections */
.provider-section { background: var(--bg3); border: 1px solid var(--border); border-radius: var(--radius); padding: 16px 18px; margin-bottom: 14px; }
.provider-header { display: flex; align-items: center; gap: 10px; font-size: 14px; font-weight: 600; color: var(--text); margin-bottom: 14px; }
.provider-logo {
  width: 28px; height: 28px; border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 800; color: #fff; flex-shrink: 0;
}
.dynu-logo  { background: linear-gradient(135deg, #4f8ef7, #7c5ef7); }
.noip-logo  { background: linear-gradient(135deg, #10b981, #059669); }
.tg-logo    { background: linear-gradient(135deg, #229ED9, #1a7fc1); }
.email-logo { background: linear-gradient(135deg, #f59e0b, #d97706); }

/* Toggle */
.toggle-label { display: flex; align-items: center; gap: 10px; cursor: pointer; font-size: 14px; font-weight: 500; color: var(--text); }
.toggle-wrap  { position: relative; display: inline-flex; flex-shrink: 0; }
.toggle-input { position: absolute; opacity: 0; width: 0; height: 0; }
.toggle-track {
  width: 40px; height: 22px; background: var(--bg3); border: 1px solid var(--border);
  border-radius: 11px; transition: all 0.2s; display: flex; align-items: center; padding: 2px;
}
.toggle-input:checked + .toggle-track { background: var(--accent); border-color: var(--accent); }
.toggle-thumb { width: 16px; height: 16px; background: #fff; border-radius: 50%; transition: transform 0.2s; flex-shrink: 0; }
.toggle-input:checked + .toggle-track .toggle-thumb { transform: translateX(18px); }

/* Hint box */
.hint-box {
  background: rgba(79,142,247,0.06); border: 1px solid rgba(79,142,247,0.15);
  border-radius: 8px; padding: 10px 14px; font-size: 12px; color: var(--text2);
  margin-top: 14px; line-height: 1.6;
}
.hint-box a { color: var(--accent); }
</style>
