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
        <span class="live-badge">
          <span class="live-pulse"></span> Live
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
      <div class="refresh-hint">Updates every 5 seconds</div>
    </div>

    <!-- History -->
    <div v-if="tab==='history'" class="card">
      <div class="card-title">Connection history</div>
      <div class="flex gap-2 mb-3">
        <input v-model="search" placeholder="Filter by user…" style="max-width:220px" />
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
            <td>{{ s.bytes_in }}</td>
            <td>{{ s.bytes_out }}</td>
            <td>
              <span class="badge" :class="s.is_active ? 'badge-success' : 'badge-gray'">
                {{ s.is_active ? 'Active' : 'Ended' }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import api from '@/utils/api'

const tab     = ref('active')
const active  = ref([])
const history = ref([])
const loading = ref(false)
const search  = ref('')
let timer

const filteredHistory = computed(() => {
  if (!search.value) return history.value
  const q = search.value.toLowerCase()
  return history.value.filter(s => s.username.toLowerCase().includes(q))
})

async function load() {
  // Don't show full spinner on background refreshes — only when list is empty
  if (tab.value === 'active' && active.value.length === 0) loading.value = true
  if (tab.value === 'history' && history.value.length === 0) loading.value = true
  try {
    if (tab.value === 'active') {
      active.value = (await api.get('/stats/active-sessions')).data
    } else {
      history.value = (await api.get('/stats/connection-history')).data
    }
  } finally { loading.value = false }
}

async function disconnect(id, username) {
  if (!confirm(`Disconnect session for ${username}?`)) return
  await api.post(`/vpn/disconnect/${id}`)
  await load()
}

function fmtDate(d) {
  if (!d) return "—"
  const dt = new Date(d.endsWith("Z") ? d : d + "Z")
  return dt.toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" })
}

function startTimer() {
  stopTimer()
  timer = setInterval(() => { if (tab.value === 'active') load() }, 5000)
}

function stopTimer() {
  if (timer) { clearInterval(timer); timer = null }
}

watch(tab, () => { load(); startTimer() })
onMounted(() => { load(); startTimer() })
onUnmounted(() => stopTimer())
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
  color: #10b981;
  letter-spacing: 0.5px;
  text-transform: uppercase;
}
.live-pulse {
  display: inline-block;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #10b981;
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

.refresh-hint {
  text-align: right;
  font-size: 11px;
  color: var(--text3, #6b7280);
  padding: 8px 4px 2px;
  opacity: 0.6;
}
</style>
