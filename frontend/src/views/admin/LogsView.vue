<template>
  <div>
    <div class="page-header">
      <div>
        <h2 class="page-title">Audit Logs</h2>
        <p class="page-sub">Full activity trail — every admin action, login, and VPN event</p>
      </div>
      <div class="header-actions">
        <button class="btn-ghost btn-sm" @click="exportCsv">
          <svg viewBox="0 0 24 24" width="13" height="13" fill="currentColor" style="margin-right:4px"><path d="M19 12v7H5v-7H3v7c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2v-7h-2zm-6 .67l2.59-2.58L17 11.5l-5 5-5-5 1.41-1.41L11 12.67V3h2z"/></svg>
          Export CSV
        </button>
        <button class="btn-ghost btn-sm" @click="load(true)">Refresh</button>
      </div>
    </div>

    <div v-if="liveEvents.length" class="live-ticker">
      <span class="ticker-label"><span class="live-dot"></span> Live</span>
      <transition-group name="ticker" tag="div" class="ticker-items">
        <div v-for="e in liveEvents" :key="e.id" class="ticker-item">
          <span class="badge" :class="levelBadge(e.level)">{{ e.level }}</span>
          <span class="mono text-sm">{{ e.actor }}</span>
          <span class="text-muted">&rarr;</span>
          <span class="mono text-sm">{{ e.action }}</span>
          <span class="ticker-ago">just now</span>
        </div>
      </transition-group>
    </div>

    <div class="card">
      <div class="filters">
        <input v-model="search" placeholder="Search actor, action, target…" class="filter-search" @input="onFilterChange" />
        <select v-model="levelFilter" class="filter-select" @change="onFilterChange">
          <option value="">All levels</option>
          <option value="info">Info</option>
          <option value="warning">Warning</option>
          <option value="danger">Danger</option>
        </select>
        <div class="filter-count text-muted text-sm">{{ total }} entries</div>
      </div>

      <div v-if="loading && logs.length === 0" class="loading"><div class="spinner"></div>Loading…</div>

      <table v-else>
        <thead>
          <tr>
            <th style="width:130px">Time</th>
            <th style="width:80px">Level</th>
            <th style="width:120px">Actor</th>
            <th>Action</th>
            <th>Target</th>
            <th style="width:110px">IP</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="l in logs" :key="l.timestamp + l.action + l.actor" :class="rowClass(l.level)">
            <td class="text-sm text-muted mono">{{ fmtDate(l.timestamp) }}</td>
            <td><span class="badge" :class="levelBadge(l.level)">{{ l.level }}</span></td>
            <td><span class="mono text-sm">{{ l.actor }}</span></td>
            <td><span class="mono text-sm action-cell">{{ l.action }}</span></td>
            <td class="text-muted text-sm">{{ l.target }}</td>
            <td><span class="mono text-sm">{{ l.ip_address || '—' }}</span></td>
          </tr>
        </tbody>
      </table>

      <div v-if="!loading && logs.length === 0" class="empty">No log entries match the current filters</div>

      <div v-if="total > pageSize" class="pagination">
        <button class="btn-ghost btn-sm" :disabled="page === 0" @click="page--; load()">← Prev</button>
        <span class="page-info text-muted text-sm">
          {{ page * pageSize + 1 }}–{{ Math.min((page + 1) * pageSize, total) }} of {{ total }}
        </span>
        <button class="btn-ghost btn-sm" :disabled="(page + 1) * pageSize >= total" @click="page++; load()">Next →</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { useWebSocket } from '@/composables/useWebSocket'
import api from '@/utils/api'

const logs        = ref([])
const total       = ref(0)
const loading     = ref(false)
const search      = ref('')
const levelFilter = ref('')
const page        = ref(0)
const pageSize    = 100
const liveEvents  = ref([])
let liveTimer = null

const { lastEvent } = useWebSocket()

watch(lastEvent, (evt) => {
  if (!evt) return
  const entry = {
    id:     Date.now(),
    level:  evt.event === 'login_failed' ? 'warning' : 'info',
    actor:  evt.data?.username || evt.data?.actor || '—',
    action: evt.event.toUpperCase().replace(/_/g, ' '),
    target: evt.data?.username || evt.data?.name || '',
  }
  liveEvents.value.unshift(entry)
  if (liveEvents.value.length > 5) liveEvents.value.pop()
  clearTimeout(liveTimer)
  liveTimer = setTimeout(() => { liveEvents.value = [] }, 15000)
})

async function load(resetPage = false) {
  if (resetPage) page.value = 0
  loading.value = true
  try {
    const params = {
      limit:  pageSize,
      offset: page.value * pageSize,
    }
    if (levelFilter.value) params.level  = levelFilter.value
    if (search.value)      params.search = search.value
    const { data } = await api.get('/stats/audit-log', { params })
    // Handle both paginated ({total, items}) and legacy array shapes
    if (Array.isArray(data)) {
      logs.value  = data
      total.value = data.length
    } else {
      logs.value  = data.items || []
      total.value = data.total || 0
    }
  } finally { loading.value = false }
}

function onFilterChange() { page.value = 0; load() }

function fmtDate(d) {
  if (!d) return '—'
  const dt = new Date(d.endsWith('Z') ? d : d + 'Z')
  return dt.toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'medium' })
}

function levelBadge(level) {
  return { info: 'badge-info', warning: 'badge-warning', danger: 'badge-danger' }[level] || 'badge-gray'
}

function rowClass(level) {
  if (level === 'danger')  return 'row-danger'
  if (level === 'warning') return 'row-warning'
  return ''
}

async function exportCsv() {
  loading.value = true
  try {
    const { data } = await api.get('/stats/audit-log', { params: { limit: 2000 } })
    const rows = Array.isArray(data) ? data : (data.items || [])
    const cols = ['timestamp','level','actor','action','target','ip_address','detail']
    const esc  = v => `"${String(v ?? '').replace(/"/g, '""')}"`
    const csv  = [cols.join(','), ...rows.map(r => cols.map(c => esc(r[c])).join(','))].join('\r\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url  = URL.createObjectURL(blob)
    const a    = document.createElement('a')
    a.href = url
    a.download = `ghostwire-audit-${new Date().toISOString().slice(0,10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
  } finally { loading.value = false }
}

onMounted(() => load())
</script>

<style scoped>
.page-header    { display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:20px; }
.page-title     { font-size:20px; font-weight:700; }
.page-sub       { font-size:12px; color:var(--text3); margin-top:2px; }
.header-actions { display:flex; gap:8px; }
.live-ticker    { background:var(--bg2); border:1px solid var(--border); border-radius:var(--radius); padding:10px 14px; margin-bottom:12px; display:flex; align-items:flex-start; gap:10px; }
.ticker-label   { display:flex; align-items:center; gap:5px; font-size:11px; font-weight:700; color:var(--success); white-space:nowrap; padding-top:2px; }
.live-dot       { width:6px; height:6px; border-radius:50%; background:var(--success); animation:blink 1.2s ease-in-out infinite; }
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0.2} }
.ticker-items   { display:flex; flex-direction:column; gap:4px; flex:1; }
.ticker-item    { display:flex; align-items:center; gap:6px; font-size:12px; }
.ticker-ago     { color:var(--text3); font-size:11px; margin-left:auto; }
.ticker-enter-active { animation:slide-in 0.3s ease; }
@keyframes slide-in { from{opacity:0;transform:translateY(-4px)} to{opacity:1;transform:none} }
.filters        { display:flex; align-items:center; gap:8px; margin-bottom:14px; flex-wrap:wrap; }
.filter-search  { max-width:260px; }
.filter-select  { max-width:150px; width:auto; }
.filter-count   { margin-left:auto; }
.action-cell    { color:var(--text); }
.row-warning td { background:rgba(251,191,36,0.04); }
.row-danger  td { background:rgba(248,113,113,0.06); }
.empty          { text-align:center; color:var(--text3); padding:40px; font-size:13px; }
.pagination     { display:flex; align-items:center; gap:10px; justify-content:center; padding:14px 0 4px; border-top:1px solid var(--border); margin-top:8px; }
.page-info      { min-width:120px; text-align:center; }
</style>
