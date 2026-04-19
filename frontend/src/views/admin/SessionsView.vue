<template>
  <div>
    <div class="page-header">
      <h2 class="page-title">Sessions</h2>
      <div class="flex gap-2">
        <button class="btn-ghost btn-sm" :class="tab==='active'?'active-tab':''" @click="tab='active'">Live</button>
        <button class="btn-ghost btn-sm" :class="tab==='history'?'active-tab':''" @click="tab='history'">History</button>
        <button class="btn-ghost btn-sm" @click="load">Refresh</button>
      </div>
    </div>

    <!-- Live sessions -->
    <div v-if="tab==='active'" class="card">
      <div class="card-title">
        <span class="dot dot-green"></span> Active sessions
        <span class="badge badge-success ml-auto">{{ active.length }}</span>
        <span class="live-badge" :class="wsConnected ? 'live-ws' : 'live-poll'">
          <span class="live-pulse"></span>
          {{ wsConnected ? 'Live' : 'Polling' }}
        </span>
      </div>
      <div v-if="loading && active.length === 0" class="loading"><div class="spinner"></div>Loading…</div>
      <div v-else-if="active.length===0" class="empty">No active sessions right now</div>
      <table v-else>
        <thead>
          <tr>
            <th>User</th><th>Client IP</th><th>Virtual IP</th>
            <th>Country</th><th>Duration</th><th>Data in</th><th>Data out</th><th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in active" :key="s.id">
            <td><span class="mono">{{ s.username }}</span></td>
            <td><span class="mono text-sm">{{ s.client_ip }}</span></td>
            <td><span class="mono text-sm">{{ s.virtual_ip }}</span></td>
            <td>{{ s.country_name }} <span class="text-muted">({{ s.country }})</span></td>
            <td>{{ s.duration }}</td>
            <td class="bytes-cell bytes-in">{{ s.bytes_in }}</td>
            <td class="bytes-cell bytes-out">{{ s.bytes_out }}</td>
            <td>
              <button class="btn-danger btn-sm" @click="disconnect(s.id, s.username)">
                Disconnect
              </button>
            </td>
          </tr>
        </tbody>
      </table>
      <div class="refresh-hint">{{ wsConnected ? "Updates instantly via WebSocket" : "Polling every 5 seconds" }}</div>
    </div>

    <!-- History -->
    <div v-if="tab==='history'" class="card">
      <div class="card-title">
        Connection history
        <span class="text-muted text-sm" style="font-weight:400;margin-left:8px">{{ histTotal }} total</span>
      </div>
      <div class="flex gap-2 mb-3">
        <input v-model="search" placeholder="Filter by user…" style="max-width:220px"
               @input="loadHistory(true)" />
        <button class="btn-ghost btn-sm" @click="loadHistory()">Refresh</button>
      </div>
      <div v-if="loading" class="loading"><div class="spinner"></div>Loading…</div>
      <table v-else>
        <thead>
          <tr>
            <th>User</th><th>Client IP</th><th>Country</th>
            <th>Connected at</th><th>Disconnected</th>
            <th>Data in</th><th>Data out</th><th>Status</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in filteredHistory" :key="s.id">
            <td><span class="mono">{{ s.username }}</span></td>
            <td><span class="mono text-sm">{{ s.client_ip }}</span></td>
            <td>{{ s.country_name }}</td>
            <td class="text-sm">{{ fmtDate(s.connected_at) }}</td>
            <td class="text-sm text-muted">{{ s.disconnected_at ? fmtDate(s.disconnected_at) : '—' }}</td>
            <td class="bytes-cell bytes-in">{{ s.bytes_in }}</td>
            <td class="bytes-cell bytes-out">{{ s.bytes_out }}</td>
            <td>
              <span class="badge" :class="s.is_active ? 'badge-success' : 'badge-gray'">
                {{ s.is_active ? 'Active' : 'Ended' }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="histTotal > 100" class="pagination">
        <button class="btn-ghost btn-sm" :disabled="histPage === 0" @click="histPage--; loadHistory()">← Prev</button>
        <span class="text-muted text-sm">{{ histPage * 100 + 1 }}–{{ Math.min((histPage + 1) * 100, histTotal) }} of {{ histTotal }}</span>
        <button class="btn-ghost btn-sm" :disabled="(histPage + 1) * 100 >= histTotal" @click="histPage++; loadHistory()">Next →</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import api from '@/utils/api'
import { useWebSocket } from '@/composables/useWebSocket'

const tab     = ref('active')
const active  = ref([])
const history = ref([])
const loading = ref(false)
const search    = ref('')
const histPage  = ref(0)
const histTotal = ref(0)

// ── WebSocket live feed for the active tab ─────────────────────────────────
const { snapshot, connected: wsConnected } = useWebSocket()

watch(snapshot, (snap) => {
  if (snap && tab.value === 'active') {
    active.value = snap.active_sessions || []
  }
})

// When switching to active tab, prefer WS data; only REST-poll if WS is down
watch(tab, (t) => {
  if (t === 'history') loadHistory()
  else if (!wsConnected.value) loadActive()
})

const filteredHistory = computed(() => history.value)

async function loadActive() {
  if (active.value.length === 0) loading.value = true
  try { active.value = (await api.get('/stats/active-sessions')).data }
  finally { loading.value = false }
}

async function loadHistory(resetPage = false) {
  if (resetPage) histPage.value = 0
  if (history.value.length === 0) loading.value = true
  try {
    const params = { limit: 100, offset: histPage.value * 100 }
    if (search.value) params.search = search.value
    const { data } = await api.get('/stats/connection-history', { params })
    // Handle both array (legacy) and paginated response shapes
    if (Array.isArray(data)) {
      history.value  = data
      histTotal.value = data.length
    } else {
      history.value  = data.items || []
      histTotal.value = data.total || 0
    }
  } finally { loading.value = false }
}

async function disconnect(id, username) {
  if (!confirm(`Disconnect session for ${username}?`)) return
  await api.post(`/vpn/disconnect/${id}`)
  // WS will push the updated snapshot automatically; also refresh history
  if (tab.value === 'history') loadHistory()
}

function fmtDate(d) {
  if (!d) return "—"
  const dt = new Date(d.endsWith("Z") ? d : d + "Z")
  return dt.toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" })
}

onMounted(() => {
  // Seed active list via REST immediately (WS snapshot arrives within 3 s)
  loadActive()
})
</script>

<style scoped>
.page-header { display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; }
.page-title  { font-size:20px; font-weight:700; }
.active-tab  { background:var(--bg3); color:var(--text); border-color:var(--accent); }
.empty { text-align:center; color:var(--text3); padding:40px 0; font-size:13px; }
.ml-auto { margin-left:auto; }

/* Live badge */
.live-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  margin-left: 10px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  transition: color 0.3s;
}
.live-ws   { color: #10b981; }
.live-poll { color: var(--warning); }
.live-pulse {
  display: inline-block;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: currentColor;
  animation: pulse-ring 1.4s ease-out infinite;
}
@keyframes pulse-ring {
  0%   { box-shadow: 0 0 0 0 rgba(16,185,129,0.6); }
  70%  { box-shadow: 0 0 0 6px rgba(16,185,129,0); }
  100% { box-shadow: 0 0 0 0 rgba(16,185,129,0); }
}

/* Byte counters — subtle colour tint */
.bytes-cell { font-family: monospace; font-size: 12px; }
.bytes-in  { color: #60a5fa; }
.bytes-out { color: #a78bfa; }

.pagination { display:flex; align-items:center; gap:10px; justify-content:center; padding:12px 0 2px; border-top:1px solid var(--border); margin-top:8px; }
.refresh-hint {
  text-align: right;
  font-size: 11px;
  color: var(--text3, #6b7280);
  padding: 8px 4px 2px;
  opacity: 0.6;
}
</style>
