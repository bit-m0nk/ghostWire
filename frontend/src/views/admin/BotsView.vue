<template>
  <div class="bots-page">

    <div class="page-header">
      <div>
        <h1 class="page-title">Bot Integrations</h1>
        <p class="page-sub">Send VPN events to Telegram, Discord, or Slack. One codebase — pick your platform.</p>
      </div>
    </div>

    <div v-if="loading" class="loading-state">
      <div class="spinner"></div><span>Loading…</span>
    </div>

    <div v-else class="bots-layout">

      <!-- Platform cards -->
      <div class="platform-cards">
        <div
          v-for="cfg in configs"
          :key="cfg.platform"
          class="platform-card"
          :class="{ active: cfg.is_enabled, selected: selectedPlatform === cfg.platform }"
          @click="selectedPlatform = cfg.platform"
        >
          <div class="pc-icon" :style="{ background: platformMeta[cfg.platform]?.color + '22', border: '1px solid ' + platformMeta[cfg.platform]?.color + '44' }">
            <span v-html="platformMeta[cfg.platform]?.icon"></span>
          </div>
          <div class="pc-info">
            <div class="pc-name">{{ platformMeta[cfg.platform]?.label }}</div>
            <div class="pc-status" :class="cfg.is_enabled ? 'status-on' : 'status-off'">
              {{ cfg.is_enabled ? 'Enabled' : 'Disabled' }}
            </div>
          </div>
          <div class="pc-toggle">
            <div class="toggle-wrap" :class="{ on: cfg.is_enabled }" @click.stop="togglePlatform(cfg)">
              <div class="toggle-knob"></div>
            </div>
          </div>
        </div>
      </div>

      <!-- Config panel for selected platform -->
      <div class="config-panel" v-if="activeCfg">
        <div class="cp-header">
          <div class="cp-title">
            <span v-html="platformMeta[activeCfg.platform]?.icon" class="cp-icon"></span>
            Configure {{ platformMeta[activeCfg.platform]?.label }}
          </div>
          <button
            class="btn-test btn-sm"
            :disabled="!activeCfg.is_enabled || testing"
            @click="testPlatform"
          >
            {{ testing ? 'Sending…' : '🧪 Send Test' }}
          </button>
        </div>

        <div v-if="testResult" class="test-result" :class="testResult.ok ? 'ok' : 'fail'">
          {{ testResult.ok ? '✓ Test message sent successfully' : '✗ ' + testResult.error }}
        </div>

        <!-- Telegram config -->
        <div v-if="activeCfg.platform === 'telegram'" class="cred-fields">
          <div class="form-row">
            <label>Bot Token</label>
            <div class="secret-row">
              <input v-model="editForm.tg_bot_token" :type="showSecrets ? 'text' : 'password'" placeholder="1234567890:ABC-xxx…" />
              <button class="eye-btn" @click="showSecrets = !showSecrets">{{ showSecrets ? '🙈' : '👁' }}</button>
            </div>
            <p class="field-hint">Create a bot via <a href="https://t.me/BotFather" target="_blank">@BotFather</a>, copy the token here.</p>
          </div>
          <div class="form-row">
            <label>Chat ID</label>
            <input v-model="editForm.tg_chat_id" placeholder="-1001234567890" />
            <p class="field-hint">Your group/channel ID. Send /start to your bot then check <code>https://api.telegram.org/bot{TOKEN}/getUpdates</code></p>
          </div>
        </div>

        <!-- Discord config -->
        <div v-if="activeCfg.platform === 'discord'" class="cred-fields">
          <div class="form-row">
            <label>Webhook URL</label>
            <div class="secret-row">
              <input v-model="editForm.discord_webhook_url" :type="showSecrets ? 'text' : 'password'" placeholder="https://discord.com/api/webhooks/…" />
              <button class="eye-btn" @click="showSecrets = !showSecrets">{{ showSecrets ? '🙈' : '👁' }}</button>
            </div>
            <p class="field-hint">In Discord: Channel Settings → Integrations → Webhooks → New Webhook → Copy URL.</p>
          </div>
        </div>

        <!-- Slack config -->
        <div v-if="activeCfg.platform === 'slack'" class="cred-fields">
          <div class="form-row">
            <label>Webhook URL</label>
            <div class="secret-row">
              <input v-model="editForm.slack_webhook_url" :type="showSecrets ? 'text' : 'password'" placeholder="https://hooks.slack.com/services/…" />
              <button class="eye-btn" @click="showSecrets = !showSecrets">{{ showSecrets ? '🙈' : '👁' }}</button>
            </div>
            <p class="field-hint">Create at <a href="https://api.slack.com/apps" target="_blank">api.slack.com</a> → Incoming Webhooks → Activate → Add to Workspace.</p>
          </div>
        </div>

        <button class="btn-primary" @click="saveConfig" :disabled="saving">
          {{ saving ? 'Saving…' : 'Save credentials' }}
        </button>
        <div v-if="saveError" class="alert alert-danger">{{ saveError }}</div>
        <div v-if="saveOk" class="alert alert-success">Saved.</div>

        <!-- Event toggles -->
        <div class="events-section">
          <div class="events-title">Notification events</div>
          <div class="events-grid">
            <label v-for="ev in events" :key="ev.key" class="event-toggle">
              <div class="toggle-wrap sm" :class="{ on: activeCfg.event_toggles[ev.key] }" @click="toggleEvent(ev.key)">
                <div class="toggle-knob"></div>
              </div>
              <span class="ev-label">{{ ev.label }}</span>
            </label>
          </div>
          <button class="btn-ghost btn-sm mt-2" @click="saveEventToggles" :disabled="savingToggles">
            {{ savingToggles ? 'Saving…' : 'Save event settings' }}
          </button>
        </div>
      </div>

    </div>

    <!-- Recent messages log -->
    <div class="messages-section" v-if="!loading">
      <div class="messages-header">
        <div class="messages-title">Recent messages</div>
        <select v-model="msgFilter" class="filter-select">
          <option value="">All platforms</option>
          <option value="telegram">Telegram</option>
          <option value="discord">Discord</option>
          <option value="slack">Slack</option>
        </select>
      </div>
      <div class="messages-table">
        <div v-if="messages.length === 0" class="empty-msg">No messages sent yet</div>
        <div v-for="msg in messages" :key="msg.id" class="msg-row">
          <span class="msg-platform">{{ platformMeta[msg.platform]?.label || msg.platform }}</span>
          <span class="msg-event">{{ msg.event_type }}</span>
          <span class="msg-text">{{ stripHtml(msg.message).slice(0, 90) }}{{ stripHtml(msg.message).length > 90 ? '…' : '' }}</span>
          <span class="msg-status" :class="'ms-' + msg.status">{{ msg.status }}</span>
          <span class="msg-time text-muted">{{ fmtTime(msg.sent_at) }}</span>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import api from '@/utils/api'

const configs          = ref([])
const events           = ref([])
const messages         = ref([])
const loading          = ref(true)
const selectedPlatform = ref('')
const showSecrets      = ref(false)
const testing          = ref(false)
const testResult       = ref(null)
const saving           = ref(false)
const saveError        = ref('')
const saveOk           = ref(false)
const savingToggles    = ref(false)
const msgFilter        = ref('')

const editForm = ref({
  tg_bot_token: '', tg_chat_id: '',
  discord_webhook_url: '', slack_webhook_url: '',
})

const platformMeta = {
  telegram: {
    label: 'Telegram',
    color: '#2AABEE',
    icon: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.894 8.221l-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.447 1.394c-.16.16-.295.295-.605.295l.213-3.053 5.56-5.023c.242-.213-.054-.333-.373-.12l-6.871 4.326-2.962-.924c-.643-.204-.657-.643.136-.953l11.57-4.461c.537-.194 1.006.131.833.941z"/></svg>',
  },
  discord: {
    label: 'Discord',
    color: '#5865F2',
    icon: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M20.317 4.37a19.791 19.791 0 00-4.885-1.515.074.074 0 00-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 00-5.487 0 12.64 12.64 0 00-.617-1.25.077.077 0 00-.079-.037A19.736 19.736 0 003.677 4.37a.07.07 0 00-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 00.031.057 19.9 19.9 0 005.993 3.03.078.078 0 00.084-.028 14.09 14.09 0 001.226-1.994.076.076 0 00-.041-.106 13.107 13.107 0 01-1.872-.892.077.077 0 01-.008-.128 10.2 10.2 0 00.372-.292.074.074 0 01.077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 01.078.01c.12.098.246.198.373.292a.077.077 0 01-.006.127 12.299 12.299 0 01-1.873.892.077.077 0 00-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 00.084.028 19.839 19.839 0 006.002-3.03.077.077 0 00.032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 00-.031-.03z"/></svg>',
  },
  slack: {
    label: 'Slack',
    color: '#4A154B',
    icon: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M5.042 15.165a2.528 2.528 0 01-2.52 2.523A2.528 2.528 0 010 15.165a2.527 2.527 0 012.522-2.52h2.52v2.52zM6.313 15.165a2.527 2.527 0 012.521-2.52 2.527 2.527 0 012.521 2.52v6.313A2.528 2.528 0 018.834 24a2.528 2.528 0 01-2.521-2.522v-6.313zM8.834 5.042a2.528 2.528 0 01-2.521-2.52A2.528 2.528 0 018.834 0a2.528 2.528 0 012.521 2.522v2.52H8.834zM8.834 6.313a2.528 2.528 0 012.521 2.521 2.528 2.528 0 01-2.521 2.521H2.522A2.528 2.528 0 010 8.834a2.528 2.528 0 012.522-2.521h6.312zM18.956 8.834a2.528 2.528 0 012.522-2.521A2.528 2.528 0 0124 8.834a2.528 2.528 0 01-2.522 2.521h-2.522V8.834zM17.688 8.834a2.528 2.528 0 01-2.523 2.521 2.527 2.527 0 01-2.52-2.521V2.522A2.527 2.527 0 0115.165 0a2.528 2.528 0 012.523 2.522v6.312zM15.165 18.956a2.528 2.528 0 012.523 2.522A2.528 2.528 0 0115.165 24a2.527 2.527 0 01-2.52-2.522v-2.522h2.52zM15.165 17.688a2.527 2.527 0 01-2.52-2.523 2.526 2.526 0 012.52-2.52h6.313A2.527 2.527 0 0124 15.165a2.528 2.528 0 01-2.522 2.523h-6.313z"/></svg>',
  },
}

const activeCfg = computed(() => configs.value.find(c => c.platform === selectedPlatform.value))

watch(activeCfg, (cfg) => {
  if (!cfg) return
  editForm.value = {
    tg_bot_token: '',
    tg_chat_id: cfg.tg_chat_id || '',
    discord_webhook_url: '',
    slack_webhook_url: '',
  }
  testResult.value = null
  saveOk.value = false
  saveError.value = ''
})

async function load() {
  try {
    const [cfgRes, evRes] = await Promise.all([
      api.get('/bots/'),
      api.get('/bots/events'),
    ])
    configs.value = cfgRes.data
    events.value  = evRes.data
    // Default to first platform returned by API — not hardcoded 'telegram'
    if (!selectedPlatform.value && configs.value.length > 0) {
      selectedPlatform.value = configs.value[0].platform
    }
    await loadMessages()
  } finally {
    loading.value = false
  }
}

async function loadMessages() {
  try {
    const q = msgFilter.value ? `?platform=${msgFilter.value}&limit=30` : '?limit=30'
    const res = await api.get('/bots/messages' + q)
    messages.value = res.data.items
  } catch {}
}

watch(msgFilter, loadMessages)

async function togglePlatform(cfg) {
  try {
    const res = await api.patch(`/bots/${cfg.platform}`, { is_enabled: !cfg.is_enabled })
    const idx = configs.value.findIndex(c => c.platform === cfg.platform)
    if (idx !== -1) configs.value[idx] = res.data
  } catch {}
}

async function saveConfig() {
  saving.value  = true
  saveError.value = ''
  saveOk.value = false
  try {
    const payload = {}
    if (activeCfg.value.platform === 'telegram') {
      if (editForm.value.tg_bot_token) payload.tg_bot_token = editForm.value.tg_bot_token
      payload.tg_chat_id = editForm.value.tg_chat_id
    } else if (activeCfg.value.platform === 'discord') {
      if (editForm.value.discord_webhook_url) payload.discord_webhook_url = editForm.value.discord_webhook_url
    } else if (activeCfg.value.platform === 'slack') {
      if (editForm.value.slack_webhook_url) payload.slack_webhook_url = editForm.value.slack_webhook_url
    }
    const res = await api.patch(`/bots/${activeCfg.value.platform}`, payload)
    const idx = configs.value.findIndex(c => c.platform === activeCfg.value.platform)
    if (idx !== -1) configs.value[idx] = res.data
    saveOk.value = true
    setTimeout(() => { saveOk.value = false }, 2000)
  } catch (e) {
    saveError.value = e.response?.data?.detail || 'Save failed'
  } finally {
    saving.value = false
  }
}

async function saveEventToggles() {
  savingToggles.value = true
  try {
    await api.patch(`/bots/${activeCfg.value.platform}`, {
      event_toggles: activeCfg.value.event_toggles
    })
  } finally {
    savingToggles.value = false
  }
}

function toggleEvent(key) {
  if (!activeCfg.value) return
  activeCfg.value.event_toggles[key] = !activeCfg.value.event_toggles[key]
}

async function testPlatform() {
  testing.value = true
  testResult.value = null
  try {
    await api.post(`/bots/${activeCfg.value.platform}/test`)
    testResult.value = { ok: true }
    await loadMessages()
  } catch (e) {
    testResult.value = { ok: false, error: e.response?.data?.detail || 'Test failed' }
  } finally {
    testing.value = false
    setTimeout(() => { testResult.value = null }, 5000)
  }
}

function stripHtml(text) {
  if (!text) return ''
  return text
    .replace(/<b>(.*?)<\/b>/gi, '$1')
    .replace(/<i>(.*?)<\/i>/gi, '$1')
    .replace(/<[^>]+>/g, '')
    .trim()
}

function fmtTime(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString()
}

onMounted(load)
</script>

<style scoped>
.bots-page { padding: 24px; max-width: 960px; margin: 0 auto; }
.page-header { margin-bottom: 24px; }
.page-title  { font-size: 22px; font-weight: 700; color: var(--text); margin: 0 0 4px; }
.page-sub    { font-size: 13px; color: var(--text3); margin: 0; }

.loading-state { display: flex; gap: 10px; align-items: center; color: var(--text3); padding: 40px; }
.spinner { width: 20px; height: 20px; border: 2px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: spin 0.7s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.bots-layout { display: grid; grid-template-columns: 240px 1fr; gap: 20px; align-items: start; }
@media (max-width: 700px) { .bots-layout { grid-template-columns: 1fr; } }

/* Platform cards */
.platform-cards { display: flex; flex-direction: column; gap: 8px; }
.platform-card {
  background: var(--bg2); border: 1px solid var(--border); border-radius: var(--radius);
  padding: 14px; cursor: pointer; display: flex; align-items: center; gap: 12px;
  transition: all 0.15s;
}
.platform-card:hover { border-color: var(--accent); }
.platform-card.selected { border-color: var(--accent); background: rgba(99,102,241,.06); }
.pc-icon { width: 36px; height: 36px; border-radius: 10px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.pc-icon svg { width: 18px; height: 18px; }
.pc-info { flex: 1; }
.pc-name { font-size: 13px; font-weight: 600; color: var(--text); }
.pc-status { font-size: 11px; margin-top: 2px; }
.status-on  { color: var(--success); }
.status-off { color: var(--text3); }

/* Toggle */
.toggle-wrap {
  width: 36px; height: 20px; background: var(--bg3); border: 1px solid var(--border);
  border-radius: 10px; cursor: pointer; position: relative; transition: all 0.2s; flex-shrink: 0;
}
.toggle-wrap.on { background: var(--accent); border-color: var(--accent); }
.toggle-knob {
  position: absolute; top: 2px; left: 2px; width: 14px; height: 14px;
  background: var(--text3); border-radius: 50%; transition: all 0.2s;
}
.toggle-wrap.on .toggle-knob { left: 18px; background: #fff; }
.toggle-wrap.sm { width: 28px; height: 16px; border-radius: 8px; }
.toggle-wrap.sm .toggle-knob { width: 10px; height: 10px; top: 2px; left: 2px; }
.toggle-wrap.sm.on .toggle-knob { left: 14px; }

/* Config panel */
.config-panel { background: var(--bg2); border: 1px solid var(--border); border-radius: var(--radius); padding: 20px; display: flex; flex-direction: column; gap: 16px; }
.cp-header { display: flex; align-items: center; justify-content: space-between; }
.cp-title  { font-size: 15px; font-weight: 600; color: var(--text); display: flex; align-items: center; gap: 8px; }
.cp-icon   { display: flex; align-items: center; }
.cp-icon svg { width: 18px; height: 18px; }

.cred-fields { display: flex; flex-direction: column; gap: 14px; }
.form-row { display: flex; flex-direction: column; gap: 5px; }
.form-row label { font-size: 12px; color: var(--text3); font-weight: 500; }
.form-row input {
  background: var(--bg3); border: 1px solid var(--border); border-radius: var(--radius-sm);
  padding: 8px 12px; color: var(--text); font-size: 13px; outline: none; transition: border 0.15s; width: 100%;
}
.form-row input:focus { border-color: var(--accent); }
.field-hint { font-size: 11px; color: var(--text3); margin: 3px 0 0; }
.field-hint a { color: var(--accent); text-decoration: none; }
.field-hint code { font-family: monospace; background: var(--bg3); padding: 0 4px; border-radius: 3px; }

.secret-row { display: flex; gap: 6px; }
.secret-row input { flex: 1; }
.eye-btn { background: var(--bg3); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 0 10px; cursor: pointer; font-size: 14px; }

/* Events section */
.events-section { border-top: 1px solid var(--border); padding-top: 16px; }
.events-title { font-size: 12px; color: var(--text3); font-weight: 600; text-transform: uppercase; letter-spacing: .05em; margin-bottom: 12px; }
.events-grid  { display: flex; flex-direction: column; gap: 8px; }
.event-toggle { display: flex; align-items: center; gap: 10px; cursor: pointer; }
.ev-label { font-size: 13px; color: var(--text2); }

.btn-test { background: var(--bg3); color: var(--text2); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 6px 14px; font-size: 12px; cursor: pointer; transition: all 0.15s; }
.btn-test:hover:not(:disabled) { border-color: var(--accent); color: var(--accent); }
.btn-test:disabled { opacity: 0.5; cursor: not-allowed; }

.test-result { padding: 8px 12px; border-radius: var(--radius-sm); font-size: 12px; }
.test-result.ok   { background: rgba(52,211,153,.1); color: var(--success); border: 1px solid rgba(52,211,153,.25); }
.test-result.fail { background: rgba(239,68,68,.1);  color: var(--danger);  border: 1px solid rgba(239,68,68,.25); }

/* Messages log */
.messages-section { margin-top: 28px; }
.messages-header  { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.messages-title   { font-size: 14px; font-weight: 600; color: var(--text); }
.filter-select    { background: var(--bg2); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 5px 10px; color: var(--text2); font-size: 12px; cursor: pointer; }

.messages-table { background: var(--bg2); border: 1px solid var(--border); border-radius: var(--radius); overflow: hidden; }
.empty-msg  { padding: 20px; text-align: center; color: var(--text3); font-size: 13px; }
.msg-row    { display: flex; align-items: center; gap: 12px; padding: 10px 16px; border-bottom: 1px solid var(--border); font-size: 12px; }
.msg-row:last-child { border-bottom: none; }
.msg-platform { width: 64px; flex-shrink: 0; color: var(--text3); font-weight: 500; }
.msg-event    { width: 130px; flex-shrink: 0; color: var(--text3); }
.msg-text     { flex: 1; color: var(--text2); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.msg-status   { width: 48px; flex-shrink: 0; text-align: center; border-radius: 10px; padding: 2px 6px; }
.ms-sent   { background: rgba(52,211,153,.1); color: var(--success); }
.ms-failed { background: rgba(239,68,68,.1);  color: var(--danger); }
.ms-skipped{ background: rgba(100,116,139,.1); color: var(--text3); }
.msg-time  { width: 140px; flex-shrink: 0; text-align: right; }

/* Alerts */
.alert { border-radius: var(--radius-sm); padding: 8px 12px; font-size: 12px; }
.alert-danger  { background: rgba(239,68,68,.1); color: var(--danger); border: 1px solid rgba(239,68,68,.25); }
.alert-success { background: rgba(52,211,153,.1); color: var(--success); border: 1px solid rgba(52,211,153,.25); }

/* Buttons */
.btn-primary { background: var(--accent); color: #fff; border: none; border-radius: var(--radius-sm); padding: 8px 16px; font-size: 13px; font-weight: 600; cursor: pointer; transition: opacity 0.15s; }
.btn-primary:hover { opacity: .88; }
.btn-primary:disabled { opacity: .5; cursor: not-allowed; }
.btn-ghost { background: transparent; color: var(--text2); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 8px 14px; font-size: 13px; cursor: pointer; transition: all 0.15s; }
.btn-ghost:hover { background: var(--bg3); }
.btn-ghost:disabled { opacity: .5; cursor: not-allowed; }
.btn-sm { padding: 5px 10px; font-size: 12px; }
.mt-2 { margin-top: 8px; }
.text-muted { color: var(--text3); }
</style>
