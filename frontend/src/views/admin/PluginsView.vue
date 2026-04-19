<template>
  <div class="view-root">
    <div class="view-header">
      <div>
        <h1 class="view-title">Plugin Manager</h1>
        <p class="view-sub">Extend GhostWire with community and custom plugins.</p>
      </div>
      <div class="header-actions">
        <button class="btn-secondary" @click="rescan" :disabled="rescanning">
          <svg viewBox="0 0 24 24"><path d="M17.65 6.35A7.958 7.958 0 0012 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08A5.99 5.99 0 0112 18c-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/></svg>
          {{ rescanning ? 'Scanning…' : 'Rescan' }}
        </button>
        <label class="btn-primary upload-label">
          <svg viewBox="0 0 24 24"><path d="M9 16h6v-6h4l-7-7-7 7h4zm-4 2h14v2H5z"/></svg>
          Install Plugin (.zip)
          <input type="file" accept=".zip" @change="handleUpload" style="display:none" ref="fileInput" />
        </label>
      </div>
    </div>

    <!-- Upload progress -->
    <div v-if="uploading" class="upload-progress">
      <div class="spinner"></div>
      <span>Installing plugin…</span>
    </div>

    <!-- Error banner -->
    <div v-if="uploadError" class="error-banner">
      <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>
      {{ uploadError }}
      <button @click="uploadError = null" class="close-btn">×</button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <span>Loading plugins…</span>
    </div>

    <!-- Empty state -->
    <div v-else-if="plugins.length === 0" class="empty-state">
      <svg viewBox="0 0 24 24"><path d="M20.5 11H19V7c0-1.1-.9-2-2-2h-4V3.5A2.5 2.5 0 0010 1 2.5 2.5 0 007.5 3.5V5H3.5A1.5 1.5 0 002 6.5v3.8h1.5c1.56 0 2.82 1.26 2.82 2.82a2.82 2.82 0 01-2.82 2.82H2v3.58A1.5 1.5 0 003.5 21h4v-1.5a2.5 2.5 0 012.5-2.5 2.5 2.5 0 012.5 2.5V21h4c.83 0 1.5-.67 1.5-1.5v-4h1.5a2.5 2.5 0 002.5-2.5 2.5 2.5 0 00-2.5-2.5z"/></svg>
      <h3>No plugins installed</h3>
      <p>Upload a .zip file to install your first plugin. Each plugin must contain a <code>ghostwire_plugin.json</code> manifest.</p>
    </div>

    <!-- Plugin list -->
    <div v-else class="plugin-list">
      <div v-for="plugin in plugins" :key="plugin.slug" class="plugin-card">
        <div class="plugin-header">
          <div class="plugin-icon">
            {{ plugin.name.charAt(0).toUpperCase() }}
          </div>
          <div class="plugin-meta">
            <div class="plugin-name-row">
              <span class="plugin-name">{{ plugin.name }}</span>
              <span class="plugin-version">v{{ plugin.version }}</span>
              <span class="status-badge" :class="plugin.status">{{ plugin.status }}</span>
            </div>
            <p class="plugin-author" v-if="plugin.author">by {{ plugin.author }}</p>
            <p class="plugin-desc">{{ plugin.description || 'No description provided.' }}</p>
          </div>
          <div class="plugin-actions">
            <template v-if="plugin.status === 'active'">
              <button class="btn-sm danger" @click="deactivate(plugin.slug)" :disabled="toggling === plugin.slug">
                {{ toggling === plugin.slug ? '…' : 'Deactivate' }}
              </button>
            </template>
            <template v-else>
              <button class="btn-sm primary" @click="activate(plugin.slug)" :disabled="toggling === plugin.slug">
                {{ toggling === plugin.slug ? '…' : 'Activate' }}
              </button>
            </template>
            <button class="btn-icon" title="Configure" @click="openConfig(plugin)">
              <svg viewBox="0 0 24 24"><path d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.09.63-.09.94s.02.64.07.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z"/></svg>
            </button>
            <button class="btn-icon danger" title="Uninstall" @click="remove(plugin.slug)" :disabled="plugin.status === 'active'">
              <svg viewBox="0 0 24 24"><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg>
            </button>
          </div>
        </div>

        <!-- Error message -->
        <div v-if="plugin.status === 'error'" class="plugin-error">
          <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>
          {{ plugin.error_msg || 'Unknown error during activation' }}
        </div>

        <!-- Active plugin API endpoints -->
        <div v-if="plugin.status === 'active'" class="plugin-routes">
          <span class="routes-label">API Routes (authenticated):</span>
          <div class="routes-list">
            <a :href="`/api/plugins/${plugin.slug}/status`" target="_blank" class="route-link">
              <code>GET /api/plugins/{{ plugin.slug }}/status</code>
            </a>
            <a :href="`/api/plugins/${plugin.slug}/config`" target="_blank" class="route-link">
              <code>GET /api/plugins/{{ plugin.slug }}/config</code>
            </a>
          </div>
          <p class="routes-hint">Open in browser (while logged in) or call with your API key via <code>Authorization: Bearer &lt;token&gt;</code></p>
        </div>

        <!-- Pip deps -->
        <div v-if="plugin.pip_deps" class="plugin-deps">
          <span class="deps-label">Dependencies:</span>
          <span v-for="dep in plugin.pip_deps.split('\n').filter(Boolean)" :key="dep" class="dep-tag">{{ dep }}</span>
        </div>
      </div>
    </div>

    <!-- How-to info box -->
    <div class="info-box">
      <div class="info-title">
        <svg viewBox="0 0 24 24"><path d="M11 17h2v-6h-2v6zm1-15C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zM11 9h2V7h-2v2z"/></svg>
        Plugin Format &amp; Usage
      </div>
      <p>Plugins are zip files containing a folder with a <code>ghostwire_plugin.json</code> manifest. Optionally include a <code>router.py</code> to add API routes.</p>
      <pre class="code-block">{
  "slug": "my-plugin",
  "name": "My Plugin",
  "version": "1.0.0",
  "author": "You",
  "description": "Does something useful",
  "pip_requirements": ["requests", "pillow"]
}</pre>
      <p style="margin-top:12px"><strong>Accessing plugin routes:</strong> Once a plugin is <span class="status-badge active" style="font-size:10px">active</span>, its <code>router.py</code> routes are live at:</p>
      <pre class="code-block"># Example for the bandwidth-alert plugin:
GET  /api/plugins/bandwidth-alert/status       ← view tracked sessions &amp; cap hits
GET  /api/plugins/bandwidth-alert/config       ← view current config
POST /api/plugins/bandwidth-alert/test-webhook ← fire a test webhook

# All plugin routes require authentication:
curl -H "Authorization: Bearer &lt;your-jwt-token&gt;" \
     http://&lt;your-server&gt;:8080/api/plugins/bandwidth-alert/status</pre>
      <p style="margin-top:8px;font-size:12px;color:var(--text3)">💡 You can also click the route links shown on each active plugin card above, or use an API key from Settings → Security → API Keys.</p>
    </div>

    <!-- Config Modal -->
    <div v-if="showConfig" class="modal-overlay" @click.self="closeConfig">
      <div class="modal">
        <div class="modal-header">
          <h2>Configure — {{ configPlugin?.name }}</h2>
          <button class="btn-icon" @click="closeConfig">
            <svg viewBox="0 0 24 24"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>
          </button>
        </div>
        <div class="modal-body">
          <p class="modal-hint">Edit this plugin's configuration as JSON. Keys depend on the plugin's documentation.</p>
          <textarea class="config-editor" v-model="configJson" rows="12" spellcheck="false"></textarea>
          <p v-if="configError" class="config-err">{{ configError }}</p>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="closeConfig">Cancel</button>
          <button class="btn-primary" @click="saveConfig" :disabled="savingConfig">
            {{ savingConfig ? 'Saving…' : 'Save Config' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '@/utils/api'

const plugins     = ref([])
const loading     = ref(true)
const uploading   = ref(false)
const uploadError = ref(null)
const toggling    = ref(null)
const rescanning  = ref(false)
const fileInput   = ref(null)

const showConfig    = ref(false)
const configPlugin  = ref(null)
const configJson    = ref('{}')
const configError   = ref(null)
const savingConfig  = ref(false)

async function load() {
  try {
    const { data } = await api.get('/plugins/')
    plugins.value = data
  } finally {
    loading.value = false
  }
}

async function handleUpload(e) {
  const file = e.target.files?.[0]
  if (!file) return
  uploading.value = true
  uploadError.value = null
  const form = new FormData()
  form.append('file', file)
  try {
    await api.post('/plugins/upload', form, { headers: { 'Content-Type': 'multipart/form-data' } })
    await load()
  } catch (err) {
    uploadError.value = err.response?.data?.detail || 'Upload failed'
  } finally {
    uploading.value = false
    if (fileInput.value) fileInput.value.value = ''
  }
}

async function activate(slug) {
  toggling.value = slug
  try {
    await api.post(`/plugins/${slug}/activate`)
    await load()
  } catch (err) {
    uploadError.value = err.response?.data?.detail || 'Activation failed'
  } finally {
    toggling.value = null
  }
}

async function deactivate(slug) {
  toggling.value = slug
  try {
    await api.post(`/plugins/${slug}/deactivate`)
    await load()
  } finally {
    toggling.value = null
  }
}

async function remove(slug) {
  if (!confirm(`Uninstall plugin "${slug}"? This will delete its files.`)) return
  try {
    await api.delete(`/plugins/${slug}`)
    await load()
  } catch (err) {
    uploadError.value = err.response?.data?.detail || 'Removal failed'
  }
}

async function rescan() {
  rescanning.value = true
  try {
    await api.post('/plugins/rescan')
    await load()
  } finally {
    rescanning.value = false
  }
}

async function openConfig(plugin) {
  configPlugin.value = plugin
  configError.value = null
  try {
    const { data } = await api.get(`/plugins/${plugin.slug}/config`)
    configJson.value = JSON.stringify(data, null, 2)
  } catch {
    configJson.value = '{}'
  }
  showConfig.value = true
}

function closeConfig() {
  showConfig.value = false
  configPlugin.value = null
}

async function saveConfig() {
  configError.value = null
  let parsed
  try {
    parsed = JSON.parse(configJson.value)
  } catch {
    configError.value = 'Invalid JSON'
    return
  }
  savingConfig.value = true
  try {
    await api.put(`/plugins/${configPlugin.value.slug}/config`, { config: parsed })
    closeConfig()
  } catch (err) {
    configError.value = err.response?.data?.detail || 'Save failed'
  } finally {
    savingConfig.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.view-root { padding: 28px 32px; max-width: 900px; }
.view-header { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 28px; gap: 16px; }
.view-title { font-size: 22px; font-weight: 700; color: var(--text); margin-bottom: 4px; }
.view-sub { font-size: 13px; color: var(--text3); }
.header-actions { display: flex; gap: 10px; align-items: center; flex-shrink: 0; }

.btn-primary { background: var(--accent); color: #fff; border: none; padding: 9px 16px; border-radius: var(--radius-sm); font-size: 13px; font-weight: 600; cursor: pointer; display: flex; align-items: center; gap: 7px; transition: opacity 0.15s; }
.btn-primary:hover { opacity: 0.85; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.upload-label { cursor: pointer; }
.btn-secondary { background: transparent; color: var(--text2); border: 1px solid var(--border); padding: 8px 14px; border-radius: var(--radius-sm); font-size: 13px; cursor: pointer; display: flex; align-items: center; gap: 7px; transition: all 0.15s; }
.btn-secondary svg { width: 15px; height: 15px; fill: currentColor; }
.btn-secondary:hover { border-color: var(--accent); color: var(--accent); }
.btn-secondary:disabled { opacity: 0.5; cursor: not-allowed; }

.upload-progress, .loading-state { display: flex; align-items: center; gap: 12px; color: var(--text3); padding: 16px 0; font-size: 14px; }
.spinner { width: 18px; height: 18px; border: 2px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: spin 0.7s linear infinite; flex-shrink: 0; }
@keyframes spin { to { transform: rotate(360deg); } }

.error-banner { display: flex; align-items: center; gap: 10px; background: rgba(248,113,113,0.1); border: 1px solid rgba(248,113,113,0.3); color: var(--danger); padding: 12px 16px; border-radius: var(--radius-sm); margin-bottom: 20px; font-size: 13px; }
.error-banner svg { width: 18px; height: 18px; fill: currentColor; flex-shrink: 0; }
.close-btn { margin-left: auto; background: none; border: none; color: inherit; font-size: 18px; cursor: pointer; padding: 0 4px; }

.empty-state { text-align: center; padding: 60px 40px; color: var(--text3); border: 1px dashed var(--border); border-radius: var(--radius); }
.empty-state svg { width: 48px; height: 48px; fill: currentColor; margin-bottom: 16px; display: block; margin-inline: auto; }
.empty-state h3 { font-size: 16px; color: var(--text2); margin-bottom: 8px; }
.empty-state code { background: var(--bg3); padding: 2px 6px; border-radius: 4px; font-size: 12px; }

.plugin-list { display: flex; flex-direction: column; gap: 12px; margin-bottom: 24px; }

.plugin-card { background: var(--bg2); border: 1px solid var(--border); border-radius: var(--radius); padding: 18px; }
.plugin-header { display: flex; align-items: flex-start; gap: 16px; }
.plugin-icon { width: 44px; height: 44px; border-radius: 10px; background: var(--accent3); color: var(--accent); font-size: 18px; font-weight: 800; display: flex; align-items: center; justify-content: center; flex-shrink: 0; border: 1px solid rgba(99,102,241,0.2); }
.plugin-meta { flex: 1; min-width: 0; }
.plugin-name-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 2px; }
.plugin-name { font-size: 15px; font-weight: 700; color: var(--text); }
.plugin-version { font-size: 11px; color: var(--text3); background: var(--bg3); border: 1px solid var(--border); border-radius: 10px; padding: 1px 8px; }
.plugin-author { font-size: 12px; color: var(--text3); margin-bottom: 4px; }
.plugin-desc { font-size: 13px; color: var(--text2); line-height: 1.4; }

.status-badge { font-size: 10px; font-weight: 700; border-radius: 10px; padding: 1px 8px; text-transform: uppercase; letter-spacing: 0.05em; }
.status-badge.active   { background: rgba(52,211,153,0.15); color: var(--success); border: 1px solid rgba(52,211,153,0.3); }
.status-badge.inactive { background: rgba(100,116,139,0.15); color: var(--text3); border: 1px solid var(--border); }
.status-badge.error    { background: rgba(248,113,113,0.15); color: var(--danger); border: 1px solid rgba(248,113,113,0.3); }

.plugin-actions { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
.btn-sm { padding: 6px 14px; border-radius: var(--radius-sm); font-size: 12px; font-weight: 600; cursor: pointer; border: none; transition: all 0.15s; }
.btn-sm.primary { background: var(--accent); color: #fff; }
.btn-sm.primary:hover { opacity: 0.85; }
.btn-sm.danger { background: rgba(248,113,113,0.12); color: var(--danger); border: 1px solid rgba(248,113,113,0.25); }
.btn-sm.danger:hover { background: rgba(248,113,113,0.25); }
.btn-sm:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-icon { background: transparent; border: 1px solid var(--border); color: var(--text2); border-radius: var(--radius-sm); width: 30px; height: 30px; display: flex; align-items: center; justify-content: center; cursor: pointer; transition: all 0.15s; }
.btn-icon svg { width: 14px; height: 14px; fill: currentColor; }
.btn-icon:hover { border-color: var(--accent); color: var(--accent); }
.btn-icon.danger:hover { border-color: var(--danger); color: var(--danger); }
.btn-icon:disabled { opacity: 0.3; cursor: not-allowed; }

.plugin-error { margin-top: 12px; padding: 10px 14px; background: rgba(248,113,113,0.08); border: 1px solid rgba(248,113,113,0.2); border-radius: var(--radius-sm); font-size: 12px; color: var(--danger); display: flex; align-items: flex-start; gap: 8px; }
.plugin-error svg { width: 14px; height: 14px; fill: currentColor; flex-shrink: 0; margin-top: 1px; }
.plugin-deps { margin-top: 10px; display: flex; align-items: center; flex-wrap: wrap; gap: 6px; }
.deps-label { font-size: 11px; color: var(--text3); }
.dep-tag { font-size: 11px; background: var(--bg3); border: 1px solid var(--border); color: var(--text2); border-radius: 10px; padding: 2px 8px; font-family: monospace; }

.plugin-routes { margin-top: 12px; padding: 10px 14px; background: rgba(99,102,241,0.05); border: 1px solid rgba(99,102,241,0.15); border-radius: var(--radius-sm); }
.routes-label { font-size: 11px; font-weight: 700; color: var(--accent); display: block; margin-bottom: 6px; }
.routes-list { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 6px; }
.route-link { font-size: 11px; color: var(--accent); text-decoration: none; background: var(--bg3); border: 1px solid rgba(99,102,241,0.2); border-radius: 4px; padding: 2px 8px; transition: all 0.15s; }
.route-link:hover { background: rgba(99,102,241,0.1); border-color: var(--accent); }
.route-link code { font-family: monospace; font-size: 11px; color: inherit; background: none; padding: 0; }
.routes-hint { font-size: 11px; color: var(--text3); margin: 0; line-height: 1.4; }
.routes-hint code { background: var(--bg1); padding: 1px 4px; border-radius: 3px; font-size: 10px; }

.info-box { background: rgba(99,102,241,0.05); border: 1px solid rgba(99,102,241,0.2); border-radius: var(--radius); padding: 18px 20px; margin-top: 8px; }
.info-title { display: flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 700; color: var(--accent); margin-bottom: 8px; }
.info-title svg { width: 16px; height: 16px; fill: currentColor; }
.info-box p { font-size: 13px; color: var(--text2); margin-bottom: 10px; }
.info-box code { background: var(--bg3); padding: 2px 6px; border-radius: 4px; font-size: 12px; font-family: monospace; }
.code-block { background: var(--bg1); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 12px 14px; font-size: 12px; font-family: monospace; color: var(--text2); line-height: 1.6; overflow-x: auto; margin: 0; }

/* Modal */
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.6); display: flex; align-items: center; justify-content: center; z-index: 200; padding: 20px; }
.modal { background: var(--bg2); border: 1px solid var(--border); border-radius: var(--radius); width: 100%; max-width: 520px; }
.modal-header { display: flex; align-items: center; justify-content: space-between; padding: 18px 24px; border-bottom: 1px solid var(--border); }
.modal-header h2 { font-size: 15px; font-weight: 700; color: var(--text); }
.modal-body { padding: 20px 24px; }
.modal-hint { font-size: 12px; color: var(--text3); margin-bottom: 12px; }
.modal-footer { padding: 14px 24px; border-top: 1px solid var(--border); display: flex; justify-content: flex-end; gap: 10px; }

.config-editor { width: 100%; background: var(--bg1); border: 1px solid var(--border); color: var(--text); border-radius: var(--radius-sm); padding: 12px; font-family: monospace; font-size: 12px; line-height: 1.6; resize: vertical; outline: none; box-sizing: border-box; }
.config-editor:focus { border-color: var(--accent); }
.config-err { font-size: 12px; color: var(--danger); margin-top: 8px; }
</style>
