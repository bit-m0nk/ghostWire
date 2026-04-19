<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">
          <svg viewBox="0 0 24 24" class="title-icon"><path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm-1 14H9V9h2v6zm0-8H9V5h2v2zm4 8h-2V9h2v6zm0-8h-2V5h2v2z"/></svg>
          DNS Ad Blocking
        </h1>
        <p class="page-sub">Block ads and trackers for all VPN users via dnsmasq</p>
      </div>
      <button class="btn-primary" @click="triggerSync" :disabled="syncing">
        <span v-if="syncing" class="spinner-inline"></span>
        {{ syncing ? 'Syncing…' : '↻ Sync Blocklists' }}
      </button>
    </div>

    <!-- Status bar -->
    <div class="stat-grid" style="margin-bottom:20px" v-if="status">
      <div class="stat-card">
        <div class="stat-label">Active Sources</div>
        <div class="stat-value">{{ status.active_sources }}</div>
        <div class="stat-sub">of {{ status.total_sources }} total</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Blocked Domains</div>
        <div class="stat-value">{{ fmtNum(status.total_domains) }}</div>
        <div class="stat-sub">in merged blocklist</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Last Sync</div>
        <div class="stat-value" style="font-size:15px">{{ fmtDate(status.last_sync) }}</div>
        <div class="stat-sub">auto-syncs daily</div>
      </div>
    </div>

    <div class="two-col">
      <!-- LEFT: Blocklist sources -->
      <div>
        <div class="card">
          <div class="card-title">
            <svg viewBox="0 0 24 24"><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-7 3c1.93 0 3.5 1.57 3.5 3.5S13.93 13 12 13s-3.5-1.57-3.5-3.5S10.07 6 12 6zm7 13H5v-.23c0-.62.28-1.2.76-1.58C7.47 15.82 9.64 15 12 15s4.53.82 6.24 2.19c.48.38.76.97.76 1.58V19z"/></svg>
            Blocklist Sources
          </div>

          <div v-if="loadingSources" class="loading"><div class="spinner"></div> Loading…</div>
          <div v-else>
            <div v-for="src in sources" :key="src.id" class="source-row">
              <div class="source-info">
                <div class="source-name">{{ src.name }}</div>
                <div class="source-meta">
                  <span v-if="src.last_synced" class="badge badge-success">
                    {{ fmtNum(src.domain_count) }} domains
                  </span>
                  <span v-else class="badge badge-gray">not synced</span>
                  <span v-if="src.last_error" class="badge badge-danger" :title="src.last_error">error</span>
                  <span class="source-url">{{ truncUrl(src.url) }}</span>
                </div>
              </div>
              <div class="source-actions">
                <label class="toggle-switch" :title="src.is_active ? 'Disable' : 'Enable'">
                  <input type="checkbox" :checked="src.is_active" @change="toggleSource(src)" />
                  <span class="toggle-slider"></span>
                </label>
                <button class="btn-ghost btn-sm" @click="deleteSource(src)">✕</button>
              </div>
            </div>

            <!-- Add source -->
            <div class="add-source" v-if="!showAddSource">
              <button class="btn-ghost btn-sm" @click="showAddSource = true">+ Add custom source</button>
            </div>
            <div v-else class="add-source-form">
              <div class="form-group">
                <label>Name</label>
                <input v-model="newSource.name" placeholder="My blocklist" />
              </div>
              <div class="form-group">
                <label>URL (hosts format or plain domain list)</label>
                <input v-model="newSource.url" placeholder="https://…" />
              </div>
              <div style="display:flex;gap:8px">
                <button class="btn-primary btn-sm" @click="addSource">Add</button>
                <button class="btn-ghost btn-sm" @click="showAddSource = false">Cancel</button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- RIGHT: Global overrides -->
      <div>
        <div class="card">
          <div class="card-title">
            <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>
            Global Overrides
          </div>
          <p class="helper-text">Override the merged blocklist for specific domains (all users).</p>

          <div class="override-tabs">
            <button :class="['tab-btn', overrideTab === 'block' && 'active']" @click="overrideTab = 'block'">
              Blocked <span class="tab-count">{{ overridesByType.block.length }}</span>
            </button>
            <button :class="['tab-btn', overrideTab === 'allow' && 'active']" @click="overrideTab = 'allow'">
              Whitelisted <span class="tab-count">{{ overridesByType.allow.length }}</span>
            </button>
          </div>

          <div class="override-list">
            <div v-if="overridesByType[overrideTab].length === 0" class="empty-state-sm">
              No {{ overrideTab === 'block' ? 'blocked' : 'whitelisted' }} domains
            </div>
            <div v-for="ov in overridesByType[overrideTab]" :key="ov.id" class="override-row">
              <span class="override-domain">{{ ov.domain }}</span>
              <span v-if="ov.reason" class="override-reason">{{ ov.reason }}</span>
              <button class="btn-ghost btn-sm" @click="deleteOverride(ov.id)">✕</button>
            </div>
          </div>

          <div class="add-override">
            <input v-model="newOverride.domain" placeholder="example.com" @keyup.enter="addOverride" />
            <input v-model="newOverride.reason" placeholder="reason (optional)" @keyup.enter="addOverride" />
            <div style="display:flex;gap:6px">
              <button class="btn-danger btn-sm" @click="addOverrideAs('block')">Block</button>
              <button class="btn-success btn-sm" @click="addOverrideAs('allow')">Whitelist</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Per-user DNS settings table -->
    <div class="card" style="margin-top:20px">
      <div class="card-title">
        <svg viewBox="0 0 24 24"><path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z"/></svg>
        Per-User Settings
      </div>
      <div v-if="loadingUsers" class="loading"><div class="spinner"></div></div>
      <table v-else>
        <thead>
          <tr>
            <th>User</th>
            <th>Blocking</th>
            <th>Whitelist</th>
            <th>Blacklist</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in usersWithSettings" :key="u.id">
            <td>
              <div style="font-weight:600;color:var(--text)">{{ u.username }}</div>
              <div style="font-size:11px;color:var(--text3)">{{ u.email }}</div>
            </td>
            <td>
              <label class="toggle-switch">
                <input type="checkbox" :checked="u.settings?.blocking_enabled ?? true"
                       @change="toggleUserBlocking(u)" />
                <span class="toggle-slider"></span>
              </label>
            </td>
            <td>
              <span class="badge badge-success">{{ (u.settings?.custom_whitelist || []).length }} entries</span>
            </td>
            <td>
              <span class="badge badge-danger">{{ (u.settings?.custom_blacklist || []).length }} entries</span>
            </td>
            <td>
              <button class="btn-ghost btn-sm" @click="openUserModal(u)">Edit lists</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- User list modal -->
    <div v-if="editingUser" class="modal-backdrop" @click.self="editingUser = null">
      <div class="modal">
        <div class="modal-header">
          <span>DNS Settings — {{ editingUser.username }}</span>
          <button class="modal-close" @click="editingUser = null">✕</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label>Custom Whitelist (always allow — one domain per line)</label>
            <textarea v-model="editWhitelist" rows="5" placeholder="ads.example.com&#10;tracker.io"></textarea>
          </div>
          <div class="form-group">
            <label>Custom Blacklist (always block — one domain per line)</label>
            <textarea v-model="editBlacklist" rows="5" placeholder="badsite.com"></textarea>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-ghost" @click="editingUser = null">Cancel</button>
          <button class="btn-primary" @click="saveUserLists">Save</button>
        </div>
      </div>
    </div>

    <div v-if="toast" class="toast" :class="toast.type">{{ toast.msg }}</div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '@/utils/api'

const status       = ref(null)
const sources      = ref([])
const overrides    = ref([])
const usersRaw     = ref([])
const userSettings = ref({})

const loadingSources = ref(true)
const loadingUsers   = ref(true)
const syncing        = ref(false)
const showAddSource  = ref(false)
const overrideTab    = ref('block')
const editingUser    = ref(null)
const editWhitelist  = ref('')
const editBlacklist  = ref('')
const toast          = ref(null)

const newSource   = ref({ name: '', url: '' })
const newOverride = ref({ domain: '', reason: '' })

onMounted(() => {
  loadAll()
})

async function loadAll() {
  await Promise.all([loadStatus(), loadSources(), loadOverrides(), loadUsers()])
}

async function loadStatus() {
  try { status.value = (await api.get('/dns/status')).data } catch {}
}

async function loadSources() {
  loadingSources.value = true
  try { sources.value = (await api.get('/dns/blocklists')).data } catch {}
  loadingSources.value = false
}

async function loadOverrides() {
  try { overrides.value = (await api.get('/dns/overrides')).data } catch {}
}

async function loadUsers() {
  loadingUsers.value = true
  try {
    const [usersResp] = await Promise.all([api.get('/users')])
    usersRaw.value = usersResp.data
    // Load settings for each user in parallel (best-effort)
    await Promise.allSettled(
      usersRaw.value.map(u =>
        api.get(`/dns/settings/${u.id}`)
           .then(r => { userSettings.value[u.id] = r.data })
           .catch(() => {})
      )
    )
  } catch {}
  loadingUsers.value = false
}

const usersWithSettings = computed(() =>
  usersRaw.value.map(u => ({ ...u, settings: userSettings.value[u.id] }))
)

const overridesByType = computed(() => ({
  block: overrides.value.filter(o => o.action === 'block'),
  allow: overrides.value.filter(o => o.action === 'allow'),
}))

async function triggerSync() {
  syncing.value = true
  try {
    await api.post('/dns/sync')
    showToast('Sync started in background — refresh in a moment', 'success')
    setTimeout(() => { loadStatus(); loadSources() }, 4000)
  } catch { showToast('Sync failed', 'danger') }
  syncing.value = false
}

async function toggleSource(src) {
  try {
    await api.patch(`/dns/blocklists/${src.id}`, { is_active: !src.is_active })
    src.is_active = !src.is_active
  } catch { showToast('Update failed', 'danger') }
}

async function deleteSource(src) {
  if (!confirm(`Remove blocklist "${src.name}"?`)) return
  try {
    await api.delete(`/dns/blocklists/${src.id}`)
    sources.value = sources.value.filter(s => s.id !== src.id)
    loadStatus()
  } catch { showToast('Delete failed', 'danger') }
}

async function addSource() {
  if (!newSource.value.name || !newSource.value.url) return
  try {
    await api.post('/dns/blocklists', newSource.value)
    newSource.value = { name: '', url: '' }
    showAddSource.value = false
    loadSources()
    showToast('Blocklist added', 'success')
  } catch (e) { showToast(e.response?.data?.detail || 'Failed', 'danger') }
}

async function addOverrideAs(action) {
  if (!newOverride.value.domain) return
  try {
    await api.post('/dns/overrides', { ...newOverride.value, action })
    newOverride.value = { domain: '', reason: '' }
    loadOverrides()
    overrideTab.value = action
    showToast('Override added', 'success')
  } catch (e) { showToast(e.response?.data?.detail || 'Failed', 'danger') }
}

async function deleteOverride(id) {
  try {
    await api.delete(`/dns/overrides/${id}`)
    overrides.value = overrides.value.filter(o => o.id !== id)
  } catch { showToast('Delete failed', 'danger') }
}

async function toggleUserBlocking(u) {
  const current = u.settings?.blocking_enabled ?? true
  try {
    const resp = await api.put(`/dns/settings/${u.id}`, { blocking_enabled: !current })
    userSettings.value[u.id] = resp.data
    showToast(`Blocking ${!current ? 'enabled' : 'disabled'} for ${u.username}`, 'success')
  } catch { showToast('Update failed', 'danger') }
}

function openUserModal(u) {
  editingUser.value = u
  const s = userSettings.value[u.id]
  editWhitelist.value = (s?.custom_whitelist || []).join('\n')
  editBlacklist.value = (s?.custom_blacklist || []).join('\n')
}

async function saveUserLists() {
  const uid   = editingUser.value.id
  const wl    = editWhitelist.value.split('\n').map(d => d.trim()).filter(Boolean)
  const bl    = editBlacklist.value.split('\n').map(d => d.trim()).filter(Boolean)
  try {
    const resp = await api.put(`/dns/settings/${uid}`, {
      custom_whitelist: wl,
      custom_blacklist: bl,
    })
    userSettings.value[uid] = resp.data
    editingUser.value = null
    showToast('Lists saved', 'success')
  } catch { showToast('Save failed', 'danger') }
}

function showToast(msg, type = 'info') {
  toast.value = { msg, type }
  setTimeout(() => { toast.value = null }, 3000)
}

function fmtNum(n) { return (n || 0).toLocaleString() }
function fmtDate(d) { return d ? new Date(d).toLocaleDateString() : 'Never' }
function truncUrl(url) {
  try { const u = new URL(url); return u.hostname + (u.pathname.length > 30 ? '…' : u.pathname) }
  catch { return url.slice(0, 40) }
}
function addOverride() { /* enter key on field — do nothing, use buttons */ }
</script>

<style scoped>
/* Card-title inline icons — constrain to 16px so they don't blow up */
.card-title svg { width: 16px; height: 16px; fill: var(--accent); flex-shrink: 0; }
.page { padding: 28px 32px; max-width: 1200px; margin: 0 auto; }
.page-header { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 24px; gap: 16px; }
.page-title { font-size: 20px; font-weight: 700; color: var(--text); display: flex; align-items: center; gap: 10px; }
.title-icon { width: 22px; height: 22px; fill: var(--accent); }
.page-sub { font-size: 13px; color: var(--text3); margin-top: 4px; }

.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
@media (max-width: 900px) { .two-col { grid-template-columns: 1fr; } }

.source-row { display: flex; align-items: center; justify-content: space-between; padding: 12px 0; border-bottom: 1px solid var(--border); }
.source-row:last-of-type { border-bottom: none; }
.source-info { flex: 1; min-width: 0; }
.source-name { font-size: 13px; font-weight: 600; color: var(--text); }
.source-meta { display: flex; align-items: center; gap: 6px; margin-top: 3px; flex-wrap: wrap; }
.source-url { font-size: 11px; color: var(--text3); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 180px; }
.source-actions { display: flex; align-items: center; gap: 8px; flex-shrink: 0; margin-left: 12px; }

.add-source { padding: 12px 0 4px; }
.add-source-form { padding: 12px; background: var(--bg3); border-radius: var(--radius-sm); margin-top: 10px; }

.helper-text { font-size: 12px; color: var(--text3); margin-bottom: 14px; margin-top: -6px; }

.override-tabs { display: flex; gap: 4px; margin-bottom: 12px; }
.tab-btn { background: transparent; border: 1px solid var(--border); color: var(--text2); padding: 5px 14px; border-radius: 20px; font-size: 12px; cursor: pointer; transition: all 0.15s; }
.tab-btn.active { background: rgba(99,102,241,0.15); color: var(--accent); border-color: var(--accent); }
.tab-count { font-size: 10px; background: var(--bg); border-radius: 10px; padding: 0 5px; margin-left: 4px; }
.override-list { min-height: 80px; margin-bottom: 12px; }
.override-row { display: flex; align-items: center; gap: 8px; padding: 6px 0; border-bottom: 1px solid var(--border); }
.override-domain { font-size: 13px; color: var(--text); flex: 1; font-family: monospace; }
.override-reason { font-size: 11px; color: var(--text3); flex-shrink: 0; }
.empty-state-sm { color: var(--text3); font-size: 12px; padding: 16px 0; text-align: center; }

.add-override { display: flex; flex-direction: column; gap: 6px; padding-top: 10px; border-top: 1px solid var(--border); }

/* Toggle switch */
.toggle-switch { position: relative; display: inline-block; width: 36px; height: 20px; flex-shrink: 0; }
.toggle-switch input { opacity: 0; width: 0; height: 0; }
.toggle-slider { position: absolute; inset: 0; background: var(--bg3); border: 1px solid var(--border); border-radius: 20px; cursor: pointer; transition: .2s; }
.toggle-slider::before { content: ''; position: absolute; width: 14px; height: 14px; left: 2px; bottom: 2px; background: var(--text3); border-radius: 50%; transition: .2s; }
.toggle-switch input:checked + .toggle-slider { background: rgba(99,102,241,0.25); border-color: var(--accent); }
.toggle-switch input:checked + .toggle-slider::before { transform: translateX(16px); background: var(--accent); }

/* Modal */
.modal-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,0.6); z-index: 200; display: flex; align-items: center; justify-content: center; padding: 20px; }
.modal { background: var(--bg2); border: 1px solid var(--border); border-radius: var(--radius); width: 100%; max-width: 500px; }
.modal-header { display: flex; justify-content: space-between; align-items: center; padding: 16px 20px; border-bottom: 1px solid var(--border); font-weight: 600; font-size: 14px; }
.modal-close { background: none; color: var(--text3); font-size: 16px; padding: 0; line-height: 1; }
.modal-body { padding: 20px; }
.modal-footer { padding: 14px 20px; border-top: 1px solid var(--border); display: flex; justify-content: flex-end; gap: 8px; }

.spinner-inline { display: inline-block; width: 12px; height: 12px; border: 2px solid rgba(255,255,255,0.3); border-top-color: #fff; border-radius: 50%; animation: spin 0.8s linear infinite; margin-right: 6px; vertical-align: middle; }
@keyframes spin { to { transform: rotate(360deg); } }

.toast { position: fixed; bottom: 24px; right: 24px; padding: 10px 18px; border-radius: var(--radius-sm); font-size: 13px; z-index: 999; animation: fadeIn 0.2s; }
.toast.success { background: rgba(52,211,153,0.15); border: 1px solid var(--success); color: var(--success); }
.toast.danger  { background: rgba(248,113,113,0.15); border: 1px solid var(--danger);  color: var(--danger); }
.toast.info    { background: rgba(99,102,241,0.15);  border: 1px solid var(--accent);  color: var(--accent); }
@keyframes fadeIn { from { opacity:0; transform:translateY(8px) } to { opacity:1; transform:none } }
</style>
