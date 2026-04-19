<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">
          <svg viewBox="0 0 24 24" class="title-icon"><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5 11h-2V8h2v6zm-4 4H8V8h2v10zm8-8h-2v4h2v-4z"/></svg>
          Analytics
        </h1>
        <p class="page-sub">DNS query analytics — blocked vs allowed traffic</p>
      </div>
      <div class="header-controls">
        <select v-model="selectedHours" @change="loadAll" class="hours-select">
          <option value="6">Last 6 hours</option>
          <option value="24">Last 24 hours</option>
          <option value="48">Last 48 hours</option>
          <option value="168">Last 7 days</option>
          <option value="720">Last 30 days</option>
        </select>
        <select v-if="isAdmin" v-model="selectedUser" @change="loadAll" class="hours-select">
          <option value="">All users</option>
          <option v-for="u in users" :key="u.id" :value="u.id">{{ u.username }}</option>
        </select>
      </div>
    </div>

    <!-- Empty state hint when no DNS data exists yet -->
    <div v-if="summary && summary.total_queries === 0" class="empty-analytics-banner">
      <div class="eab-icon">📊</div>
      <div class="eab-body">
        <strong>No DNS analytics data yet</strong>
        <p>Analytics populate once VPN clients connect and DNS queries are logged. Make sure
        <code>log-queries</code> is set in <code>/etc/dnsmasq.conf</code> and the query log
        is being written to <code>/var/log/dnsmasq/query.log</code>.</p>
        <p style="margin-top:6px">You can also verify dnsmasq is running:
        <code>sudo systemctl status dnsmasq</code></p>
      </div>
    </div>

    <!-- Summary stat cards -->
    <div class="stat-grid" style="margin-bottom:20px" v-if="summary">
      <div class="stat-card">
        <div class="stat-label">Total Queries</div>
        <div class="stat-value">{{ fmtNum(summary.total_queries) }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Blocked</div>
        <div class="stat-value" style="color:var(--danger)">{{ fmtNum(summary.blocked_count) }}</div>
        <div class="stat-sub">{{ summary.block_rate }}% of total</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Allowed</div>
        <div class="stat-value" style="color:var(--success)">{{ fmtNum(summary.allowed_count) }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Block Rate</div>
        <div class="stat-value">
          <span :style="{ color: blockRateColor }">{{ summary.block_rate }}%</span>
        </div>
        <div class="stat-sub">{{ summary.block_rate > 20 ? 'high ad traffic' : 'normal' }}</div>
      </div>
    </div>

    <div class="two-col" style="margin-bottom:20px">
      <!-- Hourly chart -->
      <div class="card chart-card">
        <div class="card-title">Query Traffic (Hourly)</div>
        <div v-if="loadingChart" class="loading"><div class="spinner"></div></div>
        <div v-else-if="hourlyData.length === 0" class="empty-chart">No data for this period</div>
        <div v-else class="bar-chart" ref="chartEl">
          <div class="chart-legend">
            <span class="legend-dot blocked"></span> Blocked
            <span class="legend-dot allowed"></span> Allowed
          </div>
          <div class="bars">
            <div
              v-for="(bucket, i) in chartBuckets"
              :key="i"
              class="bar-group"
              :title="`${bucket.label}\nBlocked: ${bucket.blocked}\nAllowed: ${bucket.allowed}`"
            >
              <div class="bar-pair">
                <div class="bar bar-blocked" :style="{ height: pct(bucket.blocked) }"></div>
                <div class="bar bar-allowed" :style="{ height: pct(bucket.allowed) }"></div>
              </div>
              <div class="bar-label">{{ bucket.shortLabel }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Top blocked domains -->
      <div class="card">
        <div class="card-title">Top Blocked Domains</div>
        <div v-if="loadingTop" class="loading"><div class="spinner"></div></div>
        <div v-else-if="topDomains.length === 0" class="empty-chart">No blocked queries yet</div>
        <div v-else class="domain-list">
          <div v-for="(d, i) in topDomains" :key="d.domain" class="domain-row">
            <span class="domain-rank">{{ i + 1 }}</span>
            <span class="domain-name">{{ d.domain }}</span>
            <div class="domain-bar-wrap">
              <div class="domain-bar" :style="{ width: (d.count / topDomains[0].count * 100) + '%' }"></div>
            </div>
            <span class="domain-count">{{ fmtNum(d.count) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Per-user breakdown (admin only) -->
    <div v-if="isAdmin && !selectedUser" class="card" style="margin-bottom:20px">
      <div class="card-title">Per-User Breakdown</div>
      <div v-if="loadingUsers" class="loading"><div class="spinner"></div></div>
      <div v-else-if="userSummaries.length === 0" class="empty-chart">No data</div>
      <table v-else>
        <thead>
          <tr>
            <th>User</th>
            <th>Total Queries</th>
            <th>Blocked</th>
            <th>Allowed</th>
            <th>Block Rate</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in userSummaries" :key="u.user_id">
            <td><span style="font-weight:600;color:var(--text)">{{ u.username }}</span></td>
            <td>{{ fmtNum(u.total_queries) }}</td>
            <td style="color:var(--danger)">{{ fmtNum(u.blocked_count) }}</td>
            <td style="color:var(--success)">{{ fmtNum(u.total_queries - u.blocked_count) }}</td>
            <td>
              <div class="rate-bar-wrap">
                <div class="rate-bar" :style="{ width: u.block_rate + '%', background: rateColor(u.block_rate) }"></div>
                <span class="rate-label">{{ u.block_rate }}%</span>
              </div>
            </td>
            <td>
              <button class="btn-ghost btn-sm" @click="drillUser(u.user_id)">View →</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Recent events log -->
    <div class="card">
      <div class="card-title" style="justify-content:space-between">
        <span>Recent Events</span>
        <div style="display:flex;gap:8px">
          <select v-model="eventFilter" class="hours-select" style="width:130px">
            <option value="">All actions</option>
            <option value="blocked">Blocked only</option>
            <option value="allowed">Allowed only</option>
          </select>
          <input v-model="domainFilter" placeholder="filter domain…" class="domain-filter-input" @input="loadEvents" />
        </div>
      </div>
      <div v-if="loadingEvents" class="loading"><div class="spinner"></div></div>
      <div v-else-if="events.length === 0" class="empty-chart">No events</div>
      <table v-else>
        <thead>
          <tr>
            <th>Time</th>
            <th>Domain</th>
            <th>Type</th>
            <th>Action</th>
            <th>Reason</th>
            <th v-if="isAdmin">User</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="e in events" :key="e.id">
            <td style="white-space:nowrap;font-size:12px;color:var(--text3)">{{ fmtTime(e.timestamp) }}</td>
            <td style="font-family:monospace;font-size:12px">{{ e.domain }}</td>
            <td><span class="badge badge-gray">{{ e.qtype }}</span></td>
            <td>
              <span :class="['badge', e.action === 'blocked' ? 'badge-danger' : 'badge-success']">
                {{ e.action }}
              </span>
            </td>
            <td style="font-size:11px;color:var(--text3)">{{ e.reason || '—' }}</td>
            <td v-if="isAdmin" style="font-size:12px;color:var(--text2)">{{ e.user_id ? e.user_id.slice(0,8) + '…' : '—' }}</td>
          </tr>
        </tbody>
      </table>
      <div class="pagination" v-if="totalEvents > eventLimit">
        <button class="btn-ghost btn-sm" :disabled="eventOffset === 0" @click="prevPage">← Prev</button>
        <span class="page-info">{{ eventOffset + 1 }}–{{ Math.min(eventOffset + eventLimit, totalEvents) }} of {{ fmtNum(totalEvents) }}</span>
        <button class="btn-ghost btn-sm" :disabled="eventOffset + eventLimit >= totalEvents" @click="nextPage">Next →</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '@/utils/api'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const isAdmin = computed(() => auth.isAdmin)

const selectedHours = ref('24')
const selectedUser  = ref('')
const eventFilter   = ref('')
const domainFilter  = ref('')
const eventOffset   = ref(0)
const eventLimit    = 50

const summary      = ref(null)
const hourlyData   = ref([])
const topDomains   = ref([])
const userSummaries = ref([])
const events       = ref([])
const totalEvents  = ref(0)
const users        = ref([])

const loadingChart  = ref(true)
const loadingTop    = ref(true)
const loadingUsers  = ref(true)
const loadingEvents = ref(true)

onMounted(async () => {
  if (isAdmin.value) {
    try { users.value = (await api.get('/users')).data } catch {}
  }
  loadAll()
})

async function loadAll() {
  eventOffset.value = 0
  await Promise.all([loadSummary(), loadHourly(), loadTop(), loadUserSummaries(), loadEvents()])
}

function userParams() {
  const p = { hours: selectedHours.value }
  if (selectedUser.value) p.user_id = selectedUser.value
  return p
}

async function loadSummary() {
  try { summary.value = (await api.get('/dns/stats/summary', { params: userParams() })).data }
  catch {}
}

async function loadHourly() {
  loadingChart.value = true
  try { hourlyData.value = (await api.get('/dns/stats/hourly', { params: { hours: selectedHours.value, ...(selectedUser.value && { user_id: selectedUser.value }) } })).data }
  catch {}
  loadingChart.value = false
}

async function loadTop() {
  loadingTop.value = true
  try { topDomains.value = (await api.get('/dns/stats/top-domains', { params: { ...userParams(), limit: 10 } })).data }
  catch {}
  loadingTop.value = false
}

async function loadUserSummaries() {
  if (!isAdmin.value) return
  loadingUsers.value = true
  try {
    const res = await api.post('/graphql', {
      query: `{ userSummaries(hours: ${selectedHours.value}) {
        userId username totalQueries blockedCount blockRate
      }}`
    })
    const raw = res.data?.data?.userSummaries || []
    // Strawberry returns camelCase — normalise to snake_case for the template
    userSummaries.value = raw.map(u => ({
      user_id:       u.userId       ?? u.user_id       ?? '',
      username:      u.username     ?? '',
      total_queries: u.totalQueries ?? u.total_queries ?? 0,
      blocked_count: u.blockedCount ?? u.blocked_count ?? 0,
      block_rate:    u.blockRate    ?? u.block_rate    ?? 0,
    }))
  } catch {
    userSummaries.value = []
  }
  loadingUsers.value = false
}

async function loadEvents() {
  loadingEvents.value = true
  try {
    const params = { limit: eventLimit, offset: eventOffset.value }
    if (eventFilter.value) params.action = eventFilter.value
    if (domainFilter.value) params.domain = domainFilter.value
    // Only pass user_id when actually filtering — never pass undefined/empty
    if (selectedUser.value) params.user_id = selectedUser.value
    else if (!isAdmin.value) params.user_id = 'me'
    const resp = (await api.get('/dns/events', { params })).data
    events.value      = Array.isArray(resp.items) ? resp.items : []
    totalEvents.value = resp.total ?? 0
  } catch (e) {
    events.value = []
    totalEvents.value = 0
  }
  loadingEvents.value = false
}

// Drill into a specific user
function drillUser(uid) {
  selectedUser.value = uid
  loadAll()
}

function prevPage() { eventOffset.value = Math.max(0, eventOffset.value - eventLimit); loadEvents() }
function nextPage() { eventOffset.value += eventLimit; loadEvents() }

// ── Chart helpers ─────────────────────────────────────────────────────────
const chartBuckets = computed(() => {
  if (!hourlyData.value.length) return []
  // Build a map: hour → {blocked, allowed}
  const map = {}
  for (const row of hourlyData.value) {
    if (!map[row.hour]) map[row.hour] = { blocked: 0, allowed: 0 }
    map[row.hour][row.action] = row.count
  }
  const hours = Object.keys(map).sort()
  // Show last N buckets to fit the chart
  const visible = hours.slice(-24)
  return visible.map(h => {
    const d = new Date(h)
    return {
      label:      d.toLocaleString(),
      shortLabel: d.getHours() + ':00',
      blocked:    map[h].blocked || 0,
      allowed:    map[h].allowed || 0,
    }
  })
})

const chartMax = computed(() =>
  Math.max(1, ...chartBuckets.value.map(b => b.blocked + b.allowed))
)

function pct(n) {
  const p = Math.round((n / chartMax.value) * 100)
  return Math.max(1, p) + '%'
}

// ── Color helpers ─────────────────────────────────────────────────────────
const blockRateColor = computed(() => {
  if (!summary.value) return 'var(--text)'
  const r = summary.value.block_rate
  if (r > 40) return 'var(--danger)'
  if (r > 20) return 'var(--warning)'
  return 'var(--success)'
})

function rateColor(r) {
  if (r > 40) return 'var(--danger)'
  if (r > 20) return 'var(--warning)'
  return 'var(--success)'
}

// ── Formatters ────────────────────────────────────────────────────────────
function fmtNum(n) { return (n || 0).toLocaleString() }
function fmtTime(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}
</script>

<style scoped>
.page { padding: 28px 32px; max-width: 1280px; margin: 0 auto; }
.page-header { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 24px; gap: 16px; flex-wrap: wrap; }
.page-title { font-size: 20px; font-weight: 700; color: var(--text); display: flex; align-items: center; gap: 10px; }
.title-icon { width: 22px; height: 22px; fill: var(--accent); }
.page-sub { font-size: 13px; color: var(--text3); margin-top: 4px; }
.header-controls { display: flex; gap: 8px; flex-wrap: wrap; }

.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
@media (max-width: 900px) { .two-col { grid-template-columns: 1fr; } }

.hours-select { background: var(--bg3); border: 1px solid var(--border); color: var(--text); border-radius: var(--radius-sm); padding: 6px 10px; font-size: 12px; width: auto; }

/* Chart */
.chart-card { display: flex; flex-direction: column; }
.empty-chart { color: var(--text3); font-size: 13px; text-align: center; padding: 40px 0; }
.bar-chart { flex: 1; display: flex; flex-direction: column; gap: 12px; }
.chart-legend { display: flex; gap: 16px; font-size: 11px; color: var(--text3); }
.legend-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; margin-right: 4px; }
.legend-dot.blocked { background: var(--danger); }
.legend-dot.allowed { background: var(--success); }
.bars { display: flex; align-items: flex-end; gap: 3px; height: 140px; overflow: hidden; }
.bar-group { flex: 1; display: flex; flex-direction: column; align-items: center; min-width: 0; }
.bar-pair { display: flex; align-items: flex-end; gap: 1px; width: 100%; height: 120px; }
.bar { flex: 1; border-radius: 2px 2px 0 0; min-height: 1px; transition: height 0.3s; }
.bar-blocked { background: var(--danger); opacity: 0.8; }
.bar-allowed { background: var(--success); opacity: 0.7; }
.bar-label { font-size: 9px; color: var(--text3); margin-top: 4px; white-space: nowrap; overflow: hidden; max-width: 100%; text-align: center; }

/* Top domains */
.domain-list { display: flex; flex-direction: column; gap: 6px; }
.domain-row { display: flex; align-items: center; gap: 8px; }
.domain-rank { font-size: 11px; color: var(--text3); width: 16px; text-align: right; flex-shrink: 0; }
.domain-name { font-size: 12px; font-family: monospace; color: var(--text); min-width: 0; flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.domain-bar-wrap { width: 80px; height: 6px; background: var(--bg3); border-radius: 3px; flex-shrink: 0; overflow: hidden; }
.domain-bar { height: 100%; background: var(--danger); border-radius: 3px; opacity: 0.7; transition: width 0.3s; }
.domain-count { font-size: 11px; color: var(--text3); width: 40px; text-align: right; flex-shrink: 0; }

/* Rate bar */
.rate-bar-wrap { display: flex; align-items: center; gap: 8px; }
.rate-bar { height: 6px; border-radius: 3px; min-width: 2px; transition: width 0.3s; }
.rate-label { font-size: 11px; color: var(--text3); white-space: nowrap; }

/* Pagination */
.pagination { display: flex; align-items: center; justify-content: center; gap: 12px; padding-top: 14px; border-top: 1px solid var(--border); margin-top: 12px; }
.page-info { font-size: 12px; color: var(--text3); }

.domain-filter-input { width: 160px !important; }

/* Empty analytics banner */
.empty-analytics-banner {
  display: flex; align-items: flex-start; gap: 14px;
  padding: 16px 20px; margin-bottom: 20px;
  background: rgba(99,102,241,.06); border: 1px solid rgba(99,102,241,.22);
  border-radius: var(--radius);
}
.eab-icon { font-size: 26px; flex-shrink: 0; margin-top: 2px; }
.eab-body strong { font-size: 14px; color: var(--text); display: block; margin-bottom: 6px; }
.eab-body p { font-size: 12px; color: var(--text2); margin: 0; line-height: 1.6; }
.eab-body code {
  font-family: monospace; font-size: 11px;
  background: rgba(99,102,241,.12); color: var(--accent);
  padding: 1px 5px; border-radius: 3px;
}
</style>
