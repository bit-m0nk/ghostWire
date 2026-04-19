<template>
  <div class="nodes-page">

    <!-- Header -->
    <div class="page-header">
      <div>
        <h1 class="page-title">Server Nodes</h1>
        <p class="page-sub">Monitor and manage your GhostWire server fleet</p>
      </div>
      <div class="header-actions">
        <button class="btn-ghost btn-sm" @click="checkAll" :disabled="checkingAll">
          <svg viewBox="0 0 24 24"><path d="M17.65 6.35A7.958 7.958 0 0012 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08A5.99 5.99 0 0112 18c-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/></svg>
          {{ checkingAll ? 'Checking…' : 'Check All' }}
        </button>
        <button class="btn-primary btn-sm" @click="showAddModal = true">
          <svg viewBox="0 0 24 24"><path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/></svg>
          Add Node
        </button>
      </div>
    </div>

    <!-- Fleet summary strip -->
    <div class="fleet-strip" v-if="fleet">
      <div class="fleet-stat">
        <span class="fs-val">{{ fleet.total }}</span>
        <span class="fs-label">Total nodes</span>
      </div>
      <div class="fleet-stat fleet-online">
        <span class="fs-val">{{ fleet.online }}</span>
        <span class="fs-label">Online</span>
      </div>
      <div class="fleet-stat fleet-offline" v-if="fleet.offline">
        <span class="fs-val">{{ fleet.offline }}</span>
        <span class="fs-label">Offline</span>
      </div>
      <div class="fleet-stat fleet-degraded" v-if="fleet.degraded">
        <span class="fs-val">{{ fleet.degraded }}</span>
        <span class="fs-label">Degraded</span>
      </div>
      <div class="fleet-divider"></div>
      <div class="fleet-stat">
        <span class="fs-val">{{ fleet.total_active_sessions }}</span>
        <span class="fs-label">Active sessions</span>
      </div>
      <div class="fleet-stat">
        <span class="fs-val">{{ fleet.total_users }}</span>
        <span class="fs-label">Total users</span>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <span>Loading nodes…</span>
    </div>

    <!-- Node grid -->
    <div v-else class="node-grid">
      <div
        v-for="node in nodes"
        :key="node.id"
        class="node-card"
        :class="['status-' + node.status]"
        @click="openDetail(node)"
      >
        <!-- Card header -->
        <div class="nc-header">
          <div class="nc-flag">{{ node.flag }}</div>
          <div class="nc-info">
            <div class="nc-name">{{ node.name }}</div>
            <div class="nc-host mono">{{ node.hostname }}:{{ node.port }}</div>
          </div>
          <div class="nc-status-badge" :class="'badge-' + node.status">
            <span class="status-dot"></span>
            {{ node.status }}
          </div>
        </div>

        <!-- Stats row -->
        <div class="nc-stats">
          <div class="nc-stat">
            <span class="ncs-val">{{ node.active_sessions ?? '—' }}</span>
            <span class="ncs-label">Sessions</span>
          </div>
          <div class="nc-stat">
            <span class="ncs-val">{{ node.total_users ?? '—' }}</span>
            <span class="ncs-label">Users</span>
          </div>
          <div class="nc-stat" v-if="node.latency_ms != null">
            <span class="ncs-val">{{ node.latency_ms }}ms</span>
            <span class="ncs-label">Latency</span>
          </div>
          <div class="nc-stat" v-if="node.cpu_percent != null">
            <span class="ncs-val">{{ node.cpu_percent.toFixed(1) }}%</span>
            <span class="ncs-label">CPU</span>
          </div>
          <div class="nc-stat" v-if="node.mem_percent != null">
            <span class="ncs-val">{{ node.mem_percent.toFixed(1) }}%</span>
            <span class="ncs-label">RAM</span>
          </div>
        </div>

        <!-- Resource bars (if data available) -->
        <div class="nc-bars" v-if="node.cpu_percent != null || node.mem_percent != null">
          <div v-if="node.cpu_percent != null" class="nc-bar-row">
            <span class="bar-label">CPU</span>
            <div class="bar-track">
              <div class="bar-fill" :style="{ width: node.cpu_percent + '%', background: barColor(node.cpu_percent) }"></div>
            </div>
            <span class="bar-val">{{ node.cpu_percent.toFixed(0) }}%</span>
          </div>
          <div v-if="node.mem_percent != null" class="nc-bar-row">
            <span class="bar-label">RAM</span>
            <div class="bar-track">
              <div class="bar-fill" :style="{ width: node.mem_percent + '%', background: barColor(node.mem_percent) }"></div>
            </div>
            <span class="bar-val">{{ node.mem_percent.toFixed(0) }}%</span>
          </div>
        </div>

        <!-- Footer -->
        <div class="nc-footer">
          <span class="nc-location" v-if="node.location">{{ node.location }}</span>
          <span class="nc-seen text-muted" v-if="node.last_seen">
            {{ node.is_primary ? 'Primary' : ('Last seen ' + timeAgo(node.last_seen)) }}
          </span>
          <span class="nc-primary-badge" v-if="node.is_primary">PRIMARY</span>
          <div class="nc-actions" @click.stop>
            <button v-if="!node.is_primary" class="icon-btn" title="Ping now" @click="checkNode(node)">
              <svg viewBox="0 0 24 24"><path d="M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6z"/></svg>
            </button>
            <button v-if="!node.is_primary" class="icon-btn danger" title="Remove" @click="confirmRemove(node)">
              <svg viewBox="0 0 24 24"><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg>
            </button>
          </div>
        </div>

        <!-- Error message -->
        <div v-if="node.error_message && node.status !== 'online'" class="nc-error">
          {{ node.error_message }}
        </div>
      </div>

      <!-- Empty state -->
      <div v-if="nodes.length === 0" class="empty-state">
        <div class="empty-icon">🖥</div>
        <div class="empty-title">No nodes registered</div>
        <div class="empty-sub">Add a remote GhostWire node to start managing your fleet</div>
        <button class="btn-primary mt-3" @click="showAddModal = true">Add your first node</button>
      </div>
    </div>

    <!-- ── Add Node Modal ──────────────────────────────────────────────── -->
    <div v-if="showAddModal" class="modal-overlay" @click.self="showAddModal = false">
      <div class="modal">
        <div class="modal-header">
          <h3>Add Node</h3>
          <button class="modal-close" @click="showAddModal = false">×</button>
        </div>
        <div class="modal-body">
          <div class="form-row">
            <label>Node name *</label>
            <input v-model="addForm.name" placeholder="Frankfurt-01" />
          </div>
          <div class="form-row two-col">
            <div>
              <label>Hostname / IP *</label>
              <input v-model="addForm.hostname" placeholder="192.168.1.100" />
            </div>
            <div>
              <label>Port</label>
              <input v-model.number="addForm.port" type="number" placeholder="8080" />
            </div>
          </div>
          <div class="form-row">
            <label>API Key (JWT from remote node)</label>
            <input v-model="addForm.api_key" type="password" placeholder="Leave blank if same JWT secret" />
          </div>
          <div class="form-row two-col">
            <div>
              <label>Location</label>
              <input v-model="addForm.location" placeholder="Germany" />
            </div>
            <div>
              <label>Flag emoji</label>
              <input v-model="addForm.flag" placeholder="🇩🇪" maxlength="4" />
            </div>
          </div>
          <div class="form-row">
            <label>Notes</label>
            <textarea v-model="addForm.notes" rows="2" placeholder="Optional notes…"></textarea>
          </div>
          <div v-if="addError" class="alert alert-danger">{{ addError }}</div>
        </div>
        <div class="modal-footer">
          <button class="btn-ghost" @click="showAddModal = false">Cancel</button>
          <button class="btn-primary" @click="addNode" :disabled="adding">
            {{ adding ? 'Adding…' : 'Add Node' }}
          </button>
        </div>
      </div>
    </div>

    <!-- ── Node Detail Modal ───────────────────────────────────────────── -->
    <div v-if="detailNode" class="modal-overlay" @click.self="detailNode = null">
      <div class="modal modal-wide">
        <div class="modal-header">
          <h3>{{ detailNode.flag }} {{ detailNode.name }}</h3>
          <button class="modal-close" @click="detailNode = null">×</button>
        </div>
        <div class="modal-body">
          <div class="detail-grid">
            <div class="detail-item"><span class="dl">Hostname</span><code>{{ detailNode.hostname }}:{{ detailNode.port }}</code></div>
            <div class="detail-item"><span class="dl">Status</span><span class="nc-status-badge" :class="'badge-' + detailNode.status"><span class="status-dot"></span>{{ detailNode.status }}</span></div>
            <div class="detail-item"><span class="dl">Location</span><span>{{ detailNode.location || '—' }}</span></div>
            <div class="detail-item"><span class="dl">Latency</span><span>{{ detailNode.latency_ms != null ? detailNode.latency_ms + 'ms' : '—' }}</span></div>
            <div class="detail-item"><span class="dl">Active sessions</span><span>{{ detailNode.active_sessions ?? '—' }}</span></div>
            <div class="detail-item"><span class="dl">Total users</span><span>{{ detailNode.total_users ?? '—' }}</span></div>
            <div class="detail-item"><span class="dl">CPU</span><span>{{ detailNode.cpu_percent != null ? detailNode.cpu_percent.toFixed(1) + '%' : '—' }}</span></div>
            <div class="detail-item"><span class="dl">Memory</span><span>{{ detailNode.mem_percent != null ? detailNode.mem_percent.toFixed(1) + '%' : '—' }}</span></div>
            <div class="detail-item"><span class="dl">Uptime</span><span>{{ formatUptime(detailNode.uptime_seconds) }}</span></div>
            <div class="detail-item"><span class="dl">Last check</span><span>{{ detailNode.last_check_at ? new Date(detailNode.last_check_at).toLocaleString() : '—' }}</span></div>
          </div>
          <div v-if="detailNode.notes" class="detail-notes">{{ detailNode.notes }}</div>

          <!-- Health history chart -->
          <div class="history-section" v-if="!detailNode.is_primary">
            <div class="history-title">Latency history (last 48 checks)</div>
            <div class="latency-chart" v-if="nodeHistory.length">
              <div
                v-for="(h, i) in nodeHistory"
                :key="i"
                class="latency-bar"
                :style="{ height: latencyBarH(h.latency_ms) + 'px', background: h.status === 'online' ? 'var(--accent)' : 'var(--danger)' }"
                :title="h.checked_at ? (new Date(h.checked_at).toLocaleTimeString() + ' — ' + (h.latency_ms ?? 'offline') + 'ms') : ''"
              ></div>
            </div>
            <div v-else class="text-muted text-sm">No history yet</div>
          </div>
        </div>
        <div class="modal-footer" v-if="!detailNode.is_primary">
          <button class="btn-ghost btn-sm" @click="checkNode(detailNode)">Ping Now</button>
          <button class="btn-ghost btn-sm danger" @click="confirmRemove(detailNode); detailNode = null">Remove</button>
        </div>
      </div>
    </div>

    <!-- Confirm remove -->
    <div v-if="removeTarget" class="modal-overlay" @click.self="removeTarget = null">
      <div class="modal modal-sm">
        <div class="modal-header"><h3>Remove Node</h3></div>
        <div class="modal-body">
          <p>Remove <strong>{{ removeTarget.name }}</strong>? This cannot be undone.</p>
          <div v-if="removeError" class="alert alert-danger mt-2">{{ removeError }}</div>
        </div>
        <div class="modal-footer">
          <button class="btn-ghost" @click="removeTarget = null">Cancel</button>
          <button class="btn-danger" @click="removeNode" :disabled="removing">{{ removing ? 'Removing…' : 'Remove' }}</button>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import api from '@/utils/api'

const nodes       = ref([])
const fleet       = ref(null)
const loading     = ref(true)
const checkingAll = ref(false)

const showAddModal = ref(false)
const addForm      = ref({ name: '', hostname: '', port: 8080, api_key: '', location: '', flag: '🌐', notes: '' })
const addError     = ref('')
const adding       = ref(false)

const detailNode   = ref(null)
const nodeHistory  = ref([])

const removeTarget = ref(null)
const removeError  = ref('')
const removing     = ref(false)

let pollTimer = null

async function load() {
  try {
    const [nodesRes, fleetRes] = await Promise.all([
      api.get('/nodes/'),
      api.get('/nodes/fleet'),
    ])
    nodes.value = nodesRes.data
    fleet.value = fleetRes.data
  } catch (e) {
    console.error('Failed to load nodes', e)
  } finally {
    loading.value = false
  }
}

async function checkAll() {
  checkingAll.value = true
  try {
    await api.post('/nodes/check-all')
    setTimeout(load, 3000)  // refresh after checks run
  } finally {
    setTimeout(() => { checkingAll.value = false }, 3500)
  }
}

async function checkNode(node) {
  await api.post(`/nodes/${node.id}/check`)
  setTimeout(load, 2500)
}

async function addNode() {
  addError.value = ''
  if (!addForm.value.name || !addForm.value.hostname) {
    addError.value = 'Name and hostname are required'
    return
  }
  adding.value = true
  const savedHostname = addForm.value.hostname  // save before reset
  try {
    await api.post('/nodes/', addForm.value)
    showAddModal.value = false
    addForm.value = { name: '', hostname: '', port: 8080, api_key: '', location: '', flag: '🌐', notes: '' }
    await load()
    // Trigger a health check on the newly added node
    const newNode = nodes.value.find(n => n.hostname === savedHostname)
    if (newNode) checkNode(newNode)
  } catch (e) {
    addError.value = e.response?.data?.detail || 'Failed to add node'
  } finally {
    adding.value = false
  }
}

async function openDetail(node) {
  detailNode.value = node
  nodeHistory.value = []
  if (!node.is_primary) {
    try {
      const res = await api.get(`/nodes/${node.id}/history?limit=48`)
      nodeHistory.value = res.data
    } catch {}
  }
}

function confirmRemove(node) {
  removeTarget.value = node
  removeError.value  = ''
}

async function removeNode() {
  removing.value = true
  removeError.value = ''
  try {
    await api.delete(`/nodes/${removeTarget.value.id}`)
    removeTarget.value = null
    await load()
  } catch (e) {
    removeError.value = e.response?.data?.detail || 'Failed to remove node'
  } finally {
    removing.value = false
  }
}

function timeAgo(iso) {
  const diff = Math.floor((Date.now() - new Date(iso)) / 1000)
  if (diff < 60)   return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff/60)}m ago`
  return `${Math.floor(diff/3600)}h ago`
}

function formatUptime(secs) {
  if (!secs) return '—'
  const d = Math.floor(secs / 86400)
  const h = Math.floor((secs % 86400) / 3600)
  const m = Math.floor((secs % 3600) / 60)
  if (d) return `${d}d ${h}h`
  if (h) return `${h}h ${m}m`
  return `${m}m`
}

function barColor(pct) {
  if (pct < 60) return 'var(--success)'
  if (pct < 85) return 'var(--warning)'
  return 'var(--danger)'
}

function latencyBarH(ms) {
  if (!ms) return 4
  return Math.min(48, Math.max(4, ms / 5))
}

onMounted(() => {
  load()
  pollTimer = setInterval(load, 30000) // refresh every 30s
})
onUnmounted(() => clearInterval(pollTimer))
</script>

<style scoped>
.nodes-page { padding: 24px; max-width: 1200px; margin: 0 auto; }

.page-header { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 20px; gap: 12px; flex-wrap: wrap; }
.page-title  { font-size: 22px; font-weight: 700; color: var(--text); margin: 0 0 4px; }
.page-sub    { font-size: 13px; color: var(--text3); margin: 0; }
.header-actions { display: flex; gap: 8px; align-items: center; }

/* Fleet strip */
.fleet-strip { display: flex; align-items: center; gap: 24px; padding: 14px 20px; background: var(--bg2); border: 1px solid var(--border); border-radius: var(--radius); margin-bottom: 20px; flex-wrap: wrap; }
.fleet-stat  { display: flex; flex-direction: column; align-items: center; }
.fs-val   { font-size: 20px; font-weight: 700; color: var(--text); line-height: 1; }
.fs-label { font-size: 11px; color: var(--text3); margin-top: 2px; }
.fleet-online .fs-val  { color: var(--success); }
.fleet-offline .fs-val { color: var(--danger); }
.fleet-degraded .fs-val { color: var(--warning); }
.fleet-divider { width: 1px; height: 32px; background: var(--border); }

/* Node grid */
.node-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; }

.node-card {
  background: var(--bg2); border: 1px solid var(--border); border-radius: var(--radius);
  padding: 16px; cursor: pointer; transition: all 0.15s;
  display: flex; flex-direction: column; gap: 12px;
}
.node-card:hover { border-color: var(--accent); transform: translateY(-1px); }
.node-card.status-offline  { border-left: 3px solid var(--danger); }
.node-card.status-degraded { border-left: 3px solid var(--warning); }
.node-card.status-online   { border-left: 3px solid var(--success); }

.nc-header { display: flex; align-items: center; gap: 10px; }
.nc-flag   { font-size: 24px; flex-shrink: 0; }
.nc-info   { flex: 1; min-width: 0; }
.nc-name   { font-weight: 600; font-size: 14px; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.nc-host   { font-size: 11px; color: var(--text3); margin-top: 2px; }

.nc-status-badge { display: flex; align-items: center; gap: 5px; border-radius: 20px; padding: 3px 10px; font-size: 11px; font-weight: 600; text-transform: capitalize; }
.badge-online  { background: rgba(52,211,153,.15); color: var(--success); border: 1px solid rgba(52,211,153,.3); }
.badge-offline { background: rgba(239,68,68,.15);  color: var(--danger);  border: 1px solid rgba(239,68,68,.3); }
.badge-degraded{ background: rgba(251,191,36,.15); color: var(--warning); border: 1px solid rgba(251,191,36,.3); }
.badge-unknown { background: rgba(100,116,139,.15);color: var(--text3);   border: 1px solid var(--border); }

.status-dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; flex-shrink: 0; }

.nc-stats { display: flex; gap: 16px; flex-wrap: wrap; }
.nc-stat  { display: flex; flex-direction: column; }
.ncs-val  { font-size: 15px; font-weight: 700; color: var(--text); }
.ncs-label{ font-size: 10px; color: var(--text3); margin-top: 1px; }

.nc-bars { display: flex; flex-direction: column; gap: 6px; }
.nc-bar-row { display: flex; align-items: center; gap: 8px; }
.bar-label { font-size: 10px; color: var(--text3); width: 28px; }
.bar-track { flex: 1; height: 4px; background: var(--bg3); border-radius: 2px; overflow: hidden; }
.bar-fill  { height: 100%; border-radius: 2px; transition: width 0.3s; }
.bar-val   { font-size: 10px; color: var(--text3); width: 30px; text-align: right; }

.nc-footer { display: flex; align-items: center; gap: 8px; font-size: 11px; }
.nc-location { color: var(--text3); }
.nc-seen   { color: var(--text3); flex: 1; }
.nc-primary-badge { background: rgba(99,102,241,.15); color: var(--accent); border: 1px solid rgba(99,102,241,.3); border-radius: 10px; padding: 1px 8px; font-size: 10px; font-weight: 700; }
.nc-actions { display: flex; gap: 4px; margin-left: auto; }
.icon-btn   { background: transparent; border: 1px solid var(--border); border-radius: 6px; width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; cursor: pointer; transition: all 0.15s; color: var(--text3); }
.icon-btn svg { width: 14px; height: 14px; fill: currentColor; }
.icon-btn:hover { background: var(--bg3); color: var(--text); }
.icon-btn.danger:hover { background: rgba(239,68,68,.1); color: var(--danger); border-color: var(--danger); }

.nc-error { font-size: 11px; color: var(--danger); background: rgba(239,68,68,.08); border-radius: 6px; padding: 6px 10px; }

/* Loading */
.loading-state { display: flex; align-items: center; gap: 10px; color: var(--text3); padding: 40px; }
.spinner { width: 20px; height: 20px; border: 2px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: spin 0.7s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* Empty state */
.empty-state { grid-column: 1/-1; text-align: center; padding: 60px 20px; color: var(--text3); }
.empty-icon  { font-size: 40px; margin-bottom: 12px; }
.empty-title { font-size: 16px; font-weight: 600; color: var(--text); margin-bottom: 6px; }
.empty-sub   { font-size: 13px; }
.mt-3 { margin-top: 16px; }

/* Modals */
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.6); display: flex; align-items: center; justify-content: center; z-index: 1000; padding: 20px; }
.modal { background: var(--bg2); border: 1px solid var(--border); border-radius: var(--radius); width: 100%; max-width: 480px; }
.modal-wide { max-width: 640px; }
.modal-sm   { max-width: 360px; }
.modal-header { display: flex; align-items: center; justify-content: space-between; padding: 16px 20px; border-bottom: 1px solid var(--border); }
.modal-header h3 { font-size: 15px; font-weight: 600; color: var(--text); margin: 0; }
.modal-close { background: none; border: none; color: var(--text3); cursor: pointer; font-size: 20px; padding: 0; line-height: 1; }
.modal-body { padding: 20px; display: flex; flex-direction: column; gap: 14px; max-height: 70vh; overflow-y: auto; }
.modal-footer { display: flex; justify-content: flex-end; gap: 8px; padding: 14px 20px; border-top: 1px solid var(--border); }

.form-row { display: flex; flex-direction: column; gap: 5px; }
.form-row label { font-size: 12px; color: var(--text3); }
.form-row input, .form-row textarea { background: var(--bg3); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 8px 12px; color: var(--text); font-size: 13px; outline: none; transition: border 0.15s; }
.form-row input:focus, .form-row textarea:focus { border-color: var(--accent); }
.form-row textarea { resize: vertical; font-family: inherit; }
.two-col { flex-direction: row; gap: 12px; }
.two-col > div { flex: 1; display: flex; flex-direction: column; gap: 5px; }

.detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.detail-item { display: flex; flex-direction: column; gap: 3px; }
.dl { font-size: 11px; color: var(--text3); }
.detail-item span, .detail-item code { font-size: 13px; color: var(--text); }
.detail-notes { background: var(--bg3); border-radius: var(--radius-sm); padding: 10px 12px; font-size: 12px; color: var(--text3); }

.history-section { margin-top: 4px; }
.history-title { font-size: 12px; color: var(--text3); margin-bottom: 10px; }
.latency-chart { display: flex; align-items: flex-end; gap: 3px; height: 52px; padding: 4px 0; }
.latency-bar { min-width: 6px; border-radius: 2px; flex: 1; transition: height 0.2s; }

.alert { border-radius: var(--radius-sm); padding: 8px 12px; font-size: 12px; }
.alert-danger { background: rgba(239,68,68,.1); color: var(--danger); border: 1px solid rgba(239,68,68,.25); }
.mt-2 { margin-top: 8px; }

/* Buttons */
.btn-primary { background: var(--accent); color: #fff; border: none; border-radius: var(--radius-sm); padding: 8px 16px; font-size: 13px; font-weight: 600; cursor: pointer; display: flex; align-items: center; gap: 6px; transition: opacity 0.15s; }
.btn-primary svg { width: 14px; height: 14px; fill: currentColor; }
.btn-primary:hover { opacity: 0.88; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-ghost { background: transparent; color: var(--text2); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 8px 14px; font-size: 13px; cursor: pointer; display: flex; align-items: center; gap: 6px; transition: all 0.15s; }
.btn-ghost svg { width: 14px; height: 14px; fill: currentColor; }
.btn-ghost:hover { background: var(--bg3); color: var(--text); }
.btn-ghost:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-ghost.danger:hover { background: rgba(239,68,68,.1); color: var(--danger); border-color: var(--danger); }
.btn-danger { background: var(--danger); color: #fff; border: none; border-radius: var(--radius-sm); padding: 8px 16px; font-size: 13px; font-weight: 600; cursor: pointer; transition: opacity 0.15s; }
.btn-danger:hover { opacity: 0.88; }
.btn-danger:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-sm { padding: 6px 12px; font-size: 12px; }

.mono { font-family: monospace; }
.text-muted { color: var(--text3); }
.text-sm { font-size: 12px; }
</style>
