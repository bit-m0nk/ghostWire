<template>
  <div class="dashboard">

    <!-- Phase 6: Update available banner -->
    <div v-if="updateInfo && updateInfo.has_update" class="update-banner">
      <div class="update-banner-left">
        <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>
        <div>
          <strong>GhostWire {{ updateInfo.latest_version }} is available</strong>
          <span class="update-sub">You're on {{ updateInfo.current_version }} — {{ updateInfo.release_name }}</span>
        </div>
      </div>
      <div class="update-banner-right">
        <a :href="updateInfo.release_url" target="_blank" rel="noopener" class="update-btn-changelog">View Changelog</a>
        <a href="https://github.com/ghostwire-vpn/ghostwire" target="_blank" rel="noopener" class="update-btn-primary">
          <svg viewBox="0 0 24 24"><path d="M19 12v7H5v-7H3v7c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2v-7h-2zm-6 .67l2.59-2.58L17 11.5l-5 5-5-5 1.41-1.41L11 12.67V3h2z"/></svg>
          Update Now
        </a>
      </div>
    </div>

    <!-- Top bar -->
    <div class="topbar">
      <div>
        <h1 class="topbar-title">{{ brand }}</h1>
        <div class="topbar-sub">
          <span class="dot" :class="vpnRunning ? 'dot-green' : 'dot-red'"></span>
          <span :style="{ color: vpnRunning ? 'var(--success)' : 'var(--danger)', fontSize:'12px' }">
            VPN {{ vpnRunning ? 'online' : 'offline' }}
          </span>
          <span class="sep">·</span>
          <span class="hostname mono">{{ serverHostname }}</span>
        </div>
      </div>
      <div class="topbar-right">
        <div class="ip-pill">
          <span class="ip-label">Current IP</span>
          <span class="ip-val mono">{{ currentIp }}</span>
        </div>
        <!-- WebSocket live indicator -->
        <div class="ws-indicator" :class="wsConnected ? 'ws-live' : 'ws-offline'" :title="wsConnected ? 'Live — WebSocket connected' : 'Polling — WebSocket reconnecting…'">
          <span class="ws-dot"></span>
          <span class="ws-label">{{ wsConnected ? 'Live' : 'Polling' }}</span>
        </div>
        <button class="refresh-btn" @click="load" :class="{ spinning: refreshing }">
          <svg viewBox="0 0 24 24"><path d="M17.65 6.35A7.958 7.958 0 0012 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08A5.99 5.99 0 0112 18c-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/></svg>
        </button>
      </div>
    </div>

    <!-- Stat cards row -->
    <div class="stats-row">
      <div class="stat-card" v-for="s in statCards" :key="s.label">
        <div class="stat-icon" :style="{ background: s.color + '22', color: s.color }">
          <svg viewBox="0 0 24 24" v-html="s.icon"></svg>
        </div>
        <div class="stat-body">
          <div class="stat-val" :style="{ color: s.color }">{{ s.value }}</div>
          <div class="stat-label">{{ s.label }}</div>
          <div class="stat-sub" v-if="s.sub">{{ s.sub }}</div>
        </div>
      </div>
    </div>

    <!-- Main grid: chart + live sessions -->
    <div class="main-grid">

      <!-- Live sessions panel -->
      <div class="panel sessions-panel">
        <div class="panel-header">
          <div class="panel-title">
            <span class="pulse-dot"></span>
            Live sessions
            <span class="count-badge">{{ sessions.length }}</span>
          </div>
          <span class="text-sm text-muted">Updates every 15s</span>
        </div>

        <div v-if="sessions.length === 0" class="empty-state">
          <div class="empty-icon">
            <svg viewBox="0 0 24 24"><path d="M1 9l2 2c4.97-4.97 13.03-4.97 18 0l2-2C16.93 2.93 7.08 2.93 1 9zm8 8l3 3 3-3c-1.65-1.66-4.34-1.66-6 0zm-4-4l2 2c2.76-2.76 7.24-2.76 10 0l2-2C15.14 9.14 8.87 9.14 5 13z"/></svg>
          </div>
          <div>No active sessions</div>
          <div class="text-sm" style="margin-top:4px">Waiting for connections…</div>
        </div>

        <div class="session-list" v-else>
          <div class="session-row" v-for="s in sessions" :key="s.id">
            <div class="session-avatar">{{ s.username[0].toUpperCase() }}</div>
            <div class="session-info">
              <div class="session-user">{{ s.username }}</div>
              <div class="session-meta">
                <span class="flag">{{ s.country }}</span>
                {{ s.country_name }}
                <span class="sep">·</span>
                <span class="mono text-sm">{{ s.client_ip }}</span>
              </div>
            </div>
            <div class="session-stats">
              <div class="session-bytes">↓ {{ s.bytes_in }}</div>
              <div class="session-bytes">↑ {{ s.bytes_out }}</div>
              <div class="session-duration">{{ s.duration }}</div>
            </div>
            <button class="kick-btn" @click="disconnect(s.id)" title="Disconnect">✕</button>
          </div>
        </div>
      </div>

      <!-- Traffic chart -->
      <div class="panel chart-panel">
        <div class="panel-header">
          <div class="panel-title">Traffic overview</div>
          <div class="chart-legend">
            <span class="legend-dot" style="background:#4f8ef7"></span><span>In</span>
            <span class="legend-dot" style="background:#7c5ef7"></span><span>Out</span>
          </div>
        </div>
        <div class="chart-wrap">
          <canvas id="trafficChart"></canvas>
        </div>
        <div class="traffic-totals">
          <div class="traffic-total">
            <span class="tt-label">Total received</span>
            <span class="tt-val" style="color:#4f8ef7">{{ stats?.total_in || '—' }}</span>
          </div>
          <div class="traffic-total">
            <span class="tt-label">Total sent</span>
            <span class="tt-val" style="color:#7c5ef7">{{ stats?.total_out || '—' }}</span>
          </div>
        </div>
      </div>

    </div>

    <!-- Second row: System resources + Activity log -->
    <div class="second-grid">

      <!-- System resources -->
      <div class="panel resources-panel">
        <div class="panel-header">
          <div class="panel-title">System resources</div>
          <span class="uptime-badge">Up {{ sysInfo?.uptime || '…' }}</span>
        </div>
        <div class="resources" v-if="sysInfo">
          <div class="resource-item" v-for="r in resources" :key="r.label">
            <div class="resource-header">
              <span class="resource-label">{{ r.label }}</span>
              <span class="resource-pct" :style="{ color: r.color }">{{ r.pct }}%</span>
            </div>
            <div class="resource-track">
              <div class="resource-bar"
                :style="{ width: r.pct + '%', background: r.color }"
                :class="{ 'bar-pulse': r.pct > 85 }">
              </div>
            </div>
            <div class="resource-detail">{{ r.detail }}</div>
          </div>
        </div>
        <div class="loading" v-else><div class="spinner"></div></div>

        <!-- Service status pills -->
        <div class="services" v-if="services">
          <div class="service-pill" v-for="(status, name) in services" :key="name"
            :class="status === 'active' ? 'pill-ok' : 'pill-err'">
            <span class="pill-dot"></span>
            {{ shortName(name) }}
          </div>
        </div>
      </div>

      <!-- Recent activity -->
      <div class="panel activity-panel">
        <div class="panel-header">
          <div class="panel-title">Recent activity</div>
          <a href="/logs" class="view-all">View all →</a>
        </div>
        <div class="activity-list">
          <div class="activity-item" v-for="l in recentLogs" :key="l.timestamp + l.action">
            <div class="activity-line" :class="`line-${l.level}`"></div>
            <div class="activity-body">
              <div class="activity-top">
                <span class="activity-action">{{ l.action }}</span>
                <span class="activity-badge" :class="`badge-${l.level}`">{{ l.level }}</span>
              </div>
              <div class="activity-meta">
                <span class="mono">{{ l.actor }}</span>
                <span class="sep">·</span>
                {{ fmtAgo(l.timestamp) }}
              </div>
            </div>
          </div>
          <div class="empty-state" v-if="recentLogs.length === 0">No recent activity</div>
        </div>
      </div>

      <!-- Top countries -->
      <div class="panel countries-panel">
        <div class="panel-header">
          <div class="panel-title">Top countries</div>
        </div>
        <div class="countries" v-if="topCountries.length">
          <div class="country-row" v-for="(c, i) in topCountries" :key="c.country">
            <span class="country-rank">#{{ i + 1 }}</span>
            <span class="country-name">{{ c.country }}</span>
            <div class="country-bar-wrap">
              <div class="country-bar"
                :style="{ width: (c.count / topCountries[0].count * 100) + '%' }">
              </div>
            </div>
            <span class="country-count">{{ c.count }}</span>
          </div>
        </div>
        <div class="empty-state" v-else>No connection data yet</div>
      </div>

    </div>

    <!-- Phase 3: DNS blocking summary row -->
    <div class="dns-row" v-if="dnsSummary">
      <div class="panel dns-summary-panel">
        <div class="panel-header">
          <div class="panel-title">
            <svg viewBox="0 0 24 24" style="width:14px;height:14px;fill:var(--accent)"><path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4z"/></svg>
            DNS Blocking — last 24h
          </div>
          <router-link to="/analytics" class="panel-link">View analytics →</router-link>
        </div>
        <div class="dns-stats">
          <div class="dns-stat">
            <div class="dns-stat-val">{{ fmtNum(dnsSummary.total_queries) }}</div>
            <div class="dns-stat-label">Total queries</div>
          </div>
          <div class="dns-stat blocked">
            <div class="dns-stat-val">{{ fmtNum(dnsSummary.blocked_count) }}</div>
            <div class="dns-stat-label">Blocked</div>
          </div>
          <div class="dns-stat allowed">
            <div class="dns-stat-val">{{ fmtNum(dnsSummary.allowed_count) }}</div>
            <div class="dns-stat-label">Allowed</div>
          </div>
          <div class="dns-stat rate">
            <div class="dns-stat-val">{{ dnsSummary.block_rate }}%</div>
            <div class="dns-stat-label">Block rate</div>
          </div>
          <div class="dns-rate-bar-wrap">
            <div class="dns-rate-bar"
              :style="{ width: dnsSummary.block_rate + '%' }"
              :title="`${dnsSummary.block_rate}% of queries blocked`">
            </div>
          </div>
        </div>
      </div>
      <div class="panel dns-top-panel">
        <div class="panel-header">
          <div class="panel-title">Top blocked today</div>
          <router-link to="/dns-blocking" class="panel-link">Manage →</router-link>
        </div>
        <div v-if="dnsTopDomains.length === 0" class="empty-state" style="padding:16px">No blocked queries yet</div>
        <div v-else class="dns-top-list">
          <div v-for="(d, i) in dnsTopDomains.slice(0, 6)" :key="d.domain" class="dns-top-row">
            <span class="dns-rank">{{ i + 1 }}</span>
            <span class="dns-domain">{{ d.domain }}</span>
            <span class="dns-count">{{ fmtNum(d.count) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Phase 4: Fleet overview row -->
    <div class="fleet-row" v-if="fleet && fleet.total > 1">
      <div class="panel fleet-panel">
        <div class="panel-header">
          <div class="panel-title">
            <svg viewBox="0 0 24 24" style="width:14px;height:14px;fill:var(--accent)"><path d="M20 3H4v10c0 2.21 1.79 4 4 4h6c2.21 0 4-1.79 4-4v-3h2c1.11 0 2-.89 2-2V5c0-1.11-.89-2-2-2zm0 5h-2V5h2v3zM4 19h16v2H4z"/></svg>
            Server Fleet
          </div>
          <router-link to="/nodes" class="panel-link">Manage nodes →</router-link>
        </div>
        <div class="fleet-stats">
          <div class="fleet-stat">
            <div class="fleet-stat-val">{{ fleet.total }}</div>
            <div class="fleet-stat-label">Nodes</div>
          </div>
          <div class="fleet-stat" style="color:var(--success)">
            <div class="fleet-stat-val">{{ fleet.online }}</div>
            <div class="fleet-stat-label">Online</div>
          </div>
          <div class="fleet-stat" v-if="fleet.offline" style="color:var(--danger)">
            <div class="fleet-stat-val">{{ fleet.offline }}</div>
            <div class="fleet-stat-label">Offline</div>
          </div>
          <div class="fleet-stat" v-if="fleet.degraded" style="color:var(--warning)">
            <div class="fleet-stat-val">{{ fleet.degraded }}</div>
            <div class="fleet-stat-label">Degraded</div>
          </div>
          <div class="fleet-divider"></div>
          <div class="fleet-stat">
            <div class="fleet-stat-val">{{ fleet.total_active_sessions }}</div>
            <div class="fleet-stat-label">Fleet sessions</div>
          </div>
          <div class="fleet-stat">
            <div class="fleet-stat-val">{{ fleet.total_users }}</div>
            <div class="fleet-stat-label">Total users</div>
          </div>
          <!-- Node health dots -->
          <div class="fleet-dots">
            <span class="fleet-online-bar" :style="{ width: fleet.total ? (fleet.online / fleet.total * 100) + '%' : '0%' }"></span>
          </div>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import api from '@/utils/api'
import { useWebSocket } from '@/composables/useWebSocket'

const stats       = ref(null)
const sessions    = ref([])
const recentLogs  = ref([])
const sysInfo     = ref(null)
const services    = ref(null)
const vpnRunning  = ref(true)
const refreshing  = ref(false)
const brand       = ref('GhostWire')
const serverHostname = ref('')
const currentIp   = ref('…')
const topCountries = ref([])
const dnsSummary    = ref(null)
const dnsTopDomains = ref([])
const fleet         = ref(null)   // Phase 4
const updateInfo    = ref(null)   // Phase 6

// ── Live WebSocket ─────────────────────────────────────────────────────────────
const { snapshot, lastEvent, connected: wsConnected } = useWebSocket()

// When the WS pushes a snapshot, update live counters + session list directly
watch(snapshot, (snap) => {
  if (!snap) return
  sessions.value = snap.active_sessions || []
  // Merge live counts into stats (keep REST-fetched history/totals)
  if (stats.value) {
    stats.value.active_now  = snap.session_count
    stats.value.total_in    = snap.total_bytes_in  ?? stats.value.total_in
    stats.value.total_out   = snap.total_bytes_out ?? stats.value.total_out
  } else {
    // Stats not loaded yet — create minimal stub so cards render
    stats.value = {
      active_now:      snap.session_count,
      total_users:     snap.total_users ?? '—',
      vpn_users:       snap.vpn_users ?? '—',
      total_in:        snap.total_bytes_in ?? '—',
      total_out:       snap.total_bytes_out ?? '—',
      connections_30d: 0,
    }
  }
})

// When a VPN event arrives via WS, trigger a lightweight REST refresh for counts
watch(lastEvent, async (evt) => {
  if (!evt) return
  if (['vpn_connect', 'vpn_disconnect', 'user_created', 'user_deleted'].includes(evt.event)) {
    try {
      const d = await api.get('/stats/dashboard')
      stats.value      = d.data
      recentLogs.value = (d.data.recent_logs || []).slice(0, 12)
      topCountries.value = (d.data.top_countries || []).slice(0, 5)
    } catch {}
  }
})

let slowTimer, chart

// ── Stat cards computed ───────────────────────────────────────────────────────
const statCards = computed(() => [
  {
    label: 'Active now',
    value: stats.value?.active_now ?? '—',
    sub:   'live connections',
    color: '#34d399',
    icon:  '<path d="M1 9l2 2c4.97-4.97 13.03-4.97 18 0l2-2C16.93 2.93 7.08 2.93 1 9zm8 8l3 3 3-3c-1.65-1.66-4.34-1.66-6 0zm-4-4l2 2c2.76-2.76 7.24-2.76 10 0l2-2C15.14 9.14 8.87 9.14 5 13z"/>',
  },
  {
    label: 'Total users',
    value: stats.value?.total_users ?? '—',
    sub:   `${stats.value?.vpn_users ?? 0} with VPN`,
    color: '#4f8ef7',
    icon:  '<path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z"/>',
  },
  {
    label: 'Connections (30d)',
    value: stats.value?.connections_30d ?? '—',
    sub:   'last 30 days',
    color: '#7c5ef7',
    icon:  '<path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zM9 17H7v-7h2v7zm4 0h-2V7h2v10zm4 0h-2v-4h2v4z"/>',
  },
  {
    label: 'Data in',
    value: stats.value?.total_in ?? '—',
    sub:   `Out: ${stats.value?.total_out ?? '—'}`,
    color: '#fbbf24',
    icon:  '<path d="M4 6h16v2H4zm0 5h16v2H4zm0 5h16v2H4z"/>',
  },
])

// ── Resource bars ─────────────────────────────────────────────────────────────
const resources = computed(() => {
  if (!sysInfo.value) return []
  const s = sysInfo.value
  return [
    {
      label:  'CPU',
      pct:    s.cpu_percent,
      detail: `${s.cpu_percent}% used`,
      color:  barColor(s.cpu_percent),
    },
    {
      label:  'Memory',
      pct:    s.memory_percent,
      detail: `${s.memory_used_mb} MB / ${s.memory_total_mb} MB`,
      color:  barColor(s.memory_percent),
    },
    {
      label:  'Disk',
      pct:    s.disk_percent,
      detail: `${s.disk_used_gb} GB / ${s.disk_total_gb} GB`,
      color:  barColor(s.disk_percent),
    },
  ]
})

// ── Helpers ───────────────────────────────────────────────────────────────────
function barColor(p) {
  if (p < 60) return '#34d399'
  if (p < 85) return '#fbbf24'
  return '#f87171'
}

function shortName(name) {
  const m = {
    'strongswan-starter': 'strongSwan',
    'strongswan':         'strongSwan',
    'ghostwire-backend':      'Backend',
    'ghostwire-ddns':         'DDNS',
    'ghostwire-monitor':      'Monitor',
    'fail2ban':           'fail2ban',
  }
  return m[name] || name
}

function fmtAgo(d) {
  const s = Math.floor((Date.now() - new Date(d)) / 1000)
  if (s < 60)   return `${s}s ago`
  if (s < 3600) return `${Math.floor(s/60)}m ago`
  if (s < 86400) return `${Math.floor(s/3600)}h ago`
  return `${Math.floor(s/86400)}d ago`
}

// ── Chart ─────────────────────────────────────────────────────────────────────
function initChart(labels, dataIn, dataOut) {
  const el = document.getElementById('trafficChart')
  if (!el) return
  if (chart) { chart.destroy(); chart = null }

  // Dynamically load Chart.js from CDN since we're not in a Node environment on Pi
  if (!window.Chart) return

  chart = new window.Chart(el, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'In',
          data: dataIn,
          borderColor: '#4f8ef7',
          backgroundColor: 'rgba(79,142,247,0.08)',
          borderWidth: 2,
          tension: 0.4,
          fill: true,
          pointRadius: 3,
          pointBackgroundColor: '#4f8ef7',
        },
        {
          label: 'Out',
          data: dataOut,
          borderColor: '#7c5ef7',
          backgroundColor: 'rgba(124,94,247,0.08)',
          borderWidth: 2,
          tension: 0.4,
          fill: true,
          pointRadius: 3,
          pointBackgroundColor: '#7c5ef7',
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#1a1d27',
          borderColor: '#2e3451',
          borderWidth: 1,
          titleColor: '#e2e8f0',
          bodyColor: '#94a3b8',
        },
      },
      scales: {
        x: {
          grid:  { color: 'rgba(46,52,81,0.5)' },
          ticks: { color: '#64748b', font: { size: 11 } },
        },
        y: {
          grid:  { color: 'rgba(46,52,81,0.5)' },
          ticks: { color: '#64748b', font: { size: 11 } },
          beginAtZero: true,
        },
      },
    },
  })
}

// Generate mock-but-plausible sparkline from connection count
function buildChartData(total) {
  const now = new Date()
  const labels = [], dataIn = [], dataOut = []
  for (let i = 6; i >= 0; i--) {
    const d = new Date(now); d.setDate(d.getDate() - i)
    labels.push(d.toLocaleDateString('en', { weekday: 'short' }))
    const base = Math.max(1, Math.floor(total / 7))
    dataIn.push(base + Math.floor(Math.random() * base * 0.4))
    dataOut.push(Math.floor(base * 0.6 + Math.random() * base * 0.3))
  }
  return { labels, dataIn, dataOut }
}

// ── Data loading ──────────────────────────────────────────────────────────────
// ``load`` fetches slow/static data (dashboard stats, system info, DNS, fleet).
// It does NOT fetch active-sessions — those come from the WebSocket snapshot.
async function load() {
  refreshing.value = true
  try {
    const [d, sys, svc] = await Promise.all([
      api.get('/stats/dashboard'),
      api.get('/system/info'),
      api.get('/system/services'),
    ])
    stats.value      = d.data
    recentLogs.value = (d.data.recent_logs || []).slice(0, 12)
    topCountries.value = (d.data.top_countries || []).slice(0, 5)
    sysInfo.value    = sys.data
    services.value   = svc.data
    vpnRunning.value = sys.data.vpn_running
    brand.value      = sys.data.brand || 'GhostWire'
    serverHostname.value = sys.data.server_hostname
    currentIp.value  = sys.data.current_ip

    // If WS hasn't delivered a snapshot yet, fetch sessions via REST as fallback
    if (!sessions.value.length) {
      try {
        const s = await api.get('/stats/active-sessions')
        sessions.value = s.data
        stats.value.active_now = s.data.length
      } catch {}
    }

    await nextTick()
    if (window.Chart) {
      const cd = buildChartData(d.data.connections_30d || 30)
      initChart(cd.labels, cd.dataIn, cd.dataOut)
    }
    // Phase 3: DNS stats (best-effort — don't break dashboard if DNS not running)
    try {
      const [dnsS, dnsT] = await Promise.all([
        api.get('/dns/stats/summary', { params: { hours: 24 } }),
        api.get('/dns/stats/top-domains', { params: { hours: 24, limit: 6 } }),
      ])
      dnsSummary.value    = dnsS.data
      dnsTopDomains.value = dnsT.data
    } catch { /* DNS domain not yet active or no data */ }
    // Phase 4: fleet summary (best-effort)
    try {
      const fleetRes = await api.get('/nodes/fleet')
      fleet.value = fleetRes.data
    } catch { /* nodes not yet populated */ }
    // Phase 6: update check (best-effort — non-blocking)
    try {
      const updRes = await api.get('/updates/status')
      updateInfo.value = updRes.data
    } catch { /* update check failed silently */ }
  } catch {
    vpnRunning.value = false
  } finally {
    refreshing.value = false
  }
}

async function disconnect(id) {
  if (!confirm('Disconnect this session?')) return
  await api.post(`/vpn/disconnect/${id}`)
  // Session list will self-update via WS; trigger a REST stats refresh for counts
  try { const d = await api.get('/stats/dashboard'); stats.value = d.data } catch {}
}

onMounted(() => {
  // Load Chart.js from CDN
  if (!window.Chart) {
    const s = document.createElement('script')
    s.src = 'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js'
    s.onload = () => load()
    document.head.appendChild(s)
  } else {
    load()
  }
  // Slow poll for system info / logs (60 s is fine — live data comes from WS)
  slowTimer = setInterval(load, 60000)
})

onUnmounted(() => {
  clearInterval(slowTimer)
  if (chart) chart.destroy()
})

function fmtNum(n) { return (n || 0).toLocaleString() }
</script>

<style scoped>
/* ── Layout ──────────────────────────────────────────────────────────────────*/
.dashboard { display:flex; flex-direction:column; gap:20px; padding-bottom:32px; }

/* ── Top bar ─────────────────────────────────────────────────────────────────*/
.topbar { display:flex; justify-content:space-between; align-items:center; }
.topbar-title { font-size:22px; font-weight:800; color:var(--text); letter-spacing:-0.5px; }
.topbar-sub { display:flex; align-items:center; gap:6px; margin-top:2px; }
.hostname { font-size:12px; color:var(--text3); }
.sep { color:var(--border); }
.topbar-right { display:flex; align-items:center; gap:10px; }

.ip-pill { display:flex; flex-direction:column; background:var(--bg2); border:1px solid var(--border); border-radius:var(--radius-sm); padding:6px 12px; }
.ip-label { font-size:10px; color:var(--text3); text-transform:uppercase; letter-spacing:0.06em; }
.ip-val { font-size:13px; color:var(--accent); }

.refresh-btn { width:32px; height:32px; border-radius:8px; background:var(--bg2); border:1px solid var(--border); display:flex; align-items:center; justify-content:center; color:var(--text2); transition:all 0.2s; }
.refresh-btn:hover { background:var(--bg3); color:var(--text); }
.refresh-btn svg { width:16px; height:16px; fill:currentColor; }
.refresh-btn.spinning svg { animation:spin 1s linear infinite; }
/* WebSocket live indicator */
.ws-indicator { display:flex; align-items:center; gap:5px; padding:3px 10px; border-radius:20px; font-size:11px; font-weight:600; letter-spacing:0.03em; border:1px solid; transition:all 0.4s; }
.ws-live    { background:rgba(52,211,153,0.1); color:var(--success); border-color:rgba(52,211,153,0.25); }
.ws-offline { background:rgba(251,191,36,0.1); color:var(--warning); border-color:rgba(251,191,36,0.25); }
.ws-dot { width:6px; height:6px; border-radius:50%; background:currentColor; }
.ws-live .ws-dot { animation:pulse-dot 1.6s ease-in-out infinite; }
@keyframes pulse-dot { 0%,100%{opacity:1} 50%{opacity:0.3} }
@keyframes spin { to { transform:rotate(360deg); } }

/* ── Stat cards ──────────────────────────────────────────────────────────────*/
.stats-row { display:grid; grid-template-columns:repeat(4,1fr); gap:14px; }
@media(max-width:900px){ .stats-row { grid-template-columns:repeat(2,1fr); } }

.stat-card { background:var(--bg2); border:1px solid var(--border); border-radius:var(--radius); padding:18px; display:flex; gap:14px; align-items:flex-start; transition:border-color 0.2s; }
.stat-card:hover { border-color:rgba(79,142,247,0.3); }

.stat-icon { width:42px; height:42px; border-radius:10px; display:flex; align-items:center; justify-content:center; flex-shrink:0; }
.stat-icon svg { width:20px; height:20px; fill:currentColor; }
.stat-body { min-width:0; }
.stat-val   { font-size:26px; font-weight:800; line-height:1; }
.stat-label { font-size:12px; color:var(--text2); margin-top:4px; }
.stat-sub   { font-size:11px; color:var(--text3); margin-top:2px; }

/* ── Main grid ───────────────────────────────────────────────────────────────*/
.main-grid { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
@media(max-width:900px){ .main-grid { grid-template-columns:1fr; } }

/* ── Panel base ──────────────────────────────────────────────────────────────*/
.panel { background:var(--bg2); border:1px solid var(--border); border-radius:var(--radius); overflow:hidden; }
.panel-header { display:flex; justify-content:space-between; align-items:center; padding:16px 18px 12px; border-bottom:1px solid var(--border); }
.panel-title { display:flex; align-items:center; gap:8px; font-size:14px; font-weight:600; color:var(--text); }
.view-all { font-size:12px; color:var(--accent); text-decoration:none; }
.view-all:hover { text-decoration:underline; }

/* ── Live sessions ───────────────────────────────────────────────────────────*/
.sessions-panel { display:flex; flex-direction:column; }
.pulse-dot { width:8px; height:8px; border-radius:50%; background:var(--success); box-shadow:0 0 0 0 rgba(52,211,153,0.4); animation:pulse 2s infinite; }
@keyframes pulse { 0%{box-shadow:0 0 0 0 rgba(52,211,153,0.4)} 70%{box-shadow:0 0 0 6px rgba(52,211,153,0)} 100%{box-shadow:0 0 0 0 rgba(52,211,153,0)} }
.count-badge { background:rgba(52,211,153,0.15); color:var(--success); font-size:11px; font-weight:700; padding:1px 7px; border-radius:10px; }

.session-list { flex:1; overflow-y:auto; max-height:280px; }
.session-row { display:flex; align-items:center; gap:12px; padding:10px 18px; border-bottom:1px solid rgba(46,52,81,0.4); transition:background 0.15s; }
.session-row:last-child { border-bottom:none; }
.session-row:hover { background:rgba(255,255,255,0.02); }

.session-avatar { width:34px; height:34px; border-radius:50%; background:linear-gradient(135deg,var(--accent),var(--accent2)); display:flex; align-items:center; justify-content:center; font-weight:700; font-size:13px; color:#fff; flex-shrink:0; }
.session-info { flex:1; min-width:0; }
.session-user { font-size:13px; font-weight:600; color:var(--text); }
.session-meta { font-size:11px; color:var(--text3); display:flex; align-items:center; gap:4px; margin-top:2px; flex-wrap:wrap; }
.flag { font-size:12px; }

.session-stats { text-align:right; flex-shrink:0; }
.session-bytes { font-size:11px; color:var(--text3); font-family:monospace; }
.session-duration { font-size:11px; color:var(--accent); margin-top:2px; }

.kick-btn { width:24px; height:24px; border-radius:6px; background:transparent; border:1px solid transparent; color:var(--text3); font-size:11px; display:flex; align-items:center; justify-content:center; transition:all 0.15s; flex-shrink:0; }
.kick-btn:hover { background:rgba(248,113,113,0.15); border-color:var(--danger); color:var(--danger); }

/* ── Chart panel ─────────────────────────────────────────────────────────────*/
.chart-panel { display:flex; flex-direction:column; }
.chart-legend { display:flex; align-items:center; gap:10px; font-size:12px; color:var(--text2); }
.legend-dot { width:8px; height:8px; border-radius:2px; }
.chart-wrap { flex:1; padding:16px 18px 8px; min-height:180px; position:relative; }
.chart-wrap canvas { max-height:180px; }
.traffic-totals { display:grid; grid-template-columns:1fr 1fr; gap:0; border-top:1px solid var(--border); }
.traffic-total { padding:12px 18px; display:flex; flex-direction:column; gap:3px; }
.traffic-total:first-child { border-right:1px solid var(--border); }
.tt-label { font-size:11px; color:var(--text3); text-transform:uppercase; letter-spacing:0.05em; }
.tt-val { font-size:18px; font-weight:700; }

/* ── Second row ──────────────────────────────────────────────────────────────*/
.second-grid { display:grid; grid-template-columns:1fr 1fr 1fr; gap:16px; }
@media(max-width:1100px){ .second-grid { grid-template-columns:1fr 1fr; } }
@media(max-width:700px) { .second-grid { grid-template-columns:1fr; } }

/* ── Resources panel ─────────────────────────────────────────────────────────*/
.resources { padding:14px 18px; display:flex; flex-direction:column; gap:14px; }
.resource-item { display:flex; flex-direction:column; gap:5px; }
.resource-header { display:flex; justify-content:space-between; align-items:center; }
.resource-label { font-size:12px; color:var(--text2); }
.resource-pct { font-size:12px; font-weight:700; }
.resource-track { height:5px; background:var(--bg3); border-radius:3px; overflow:hidden; }
.resource-bar { height:100%; border-radius:3px; transition:width 0.8s ease; }
.resource-bar.bar-pulse { animation:bar-pulse 1.5s ease-in-out infinite; }
@keyframes bar-pulse { 0%,100%{opacity:1} 50%{opacity:0.6} }
.resource-detail { font-size:11px; color:var(--text3); }

.services { display:flex; flex-wrap:wrap; gap:6px; padding:0 18px 14px; }
.service-pill { display:flex; align-items:center; gap:5px; padding:4px 10px; border-radius:20px; font-size:11px; font-weight:500; }
.pill-ok  { background:rgba(52,211,153,0.1);  color:var(--success); border:1px solid rgba(52,211,153,0.2);  }
.pill-err { background:rgba(248,113,113,0.1); color:var(--danger);  border:1px solid rgba(248,113,113,0.2); }
.pill-dot { width:6px; height:6px; border-radius:50%; background:currentColor; }
.uptime-badge { font-size:11px; color:var(--success); background:rgba(52,211,153,0.1); padding:3px 8px; border-radius:10px; }

/* ── Activity panel ──────────────────────────────────────────────────────────*/
.activity-list { display:flex; flex-direction:column; overflow-y:auto; max-height:300px; }
.activity-item { display:flex; gap:0; border-bottom:1px solid rgba(46,52,81,0.4); }
.activity-item:last-child { border-bottom:none; }
.activity-line { width:3px; flex-shrink:0; }
.line-info    { background:var(--accent); }
.line-warning { background:var(--warning); }
.line-danger  { background:var(--danger); }
.activity-body { flex:1; padding:10px 16px; }
.activity-top { display:flex; align-items:center; justify-content:space-between; gap:8px; }
.activity-action { font-size:12px; font-weight:600; color:var(--text); font-family:monospace; }
.activity-badge { font-size:10px; padding:1px 6px; border-radius:10px; font-weight:600; }
.badge-info    { background:rgba(79,142,247,0.15);  color:var(--accent); }
.badge-warning { background:rgba(251,191,36,0.15);  color:var(--warning); }
.badge-danger  { background:rgba(248,113,113,0.15); color:var(--danger); }
.activity-meta { font-size:11px; color:var(--text3); display:flex; gap:4px; align-items:center; margin-top:3px; }

/* ── Countries panel ─────────────────────────────────────────────────────────*/
.countries { padding:14px 18px; display:flex; flex-direction:column; gap:12px; }
.country-row { display:flex; align-items:center; gap:10px; }
.country-rank { font-size:11px; color:var(--text3); min-width:24px; }
.country-name { font-size:12px; color:var(--text2); min-width:80px; flex-shrink:0; }
.country-bar-wrap { flex:1; height:5px; background:var(--bg3); border-radius:3px; overflow:hidden; }
.country-bar { height:100%; background:linear-gradient(90deg,var(--accent),var(--accent2)); border-radius:3px; transition:width 0.8s ease; }
.country-count { font-size:12px; color:var(--text2); min-width:24px; text-align:right; }

/* ── Empty state ─────────────────────────────────────────────────────────────*/
.empty-state { display:flex; flex-direction:column; align-items:center; justify-content:center; padding:32px; color:var(--text3); font-size:13px; gap:8px; }
.empty-icon { width:40px; height:40px; border-radius:12px; background:var(--bg3); display:flex; align-items:center; justify-content:center; }
.empty-icon svg { width:20px; height:20px; fill:var(--text3); }

/* ── Phase 3: DNS blocking row ───────────────────────────────────────────────*/
.dns-row { display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-top:16px; }
@media(max-width:900px){ .dns-row { grid-template-columns:1fr; } }

.dns-summary-panel, .dns-top-panel { background:var(--bg2); border:1px solid var(--border); border-radius:var(--radius); padding:16px; }

.panel-link { font-size:11px; color:var(--accent); text-decoration:none; }
.panel-link:hover { text-decoration:underline; }

.dns-stats { display:flex; align-items:center; gap:24px; flex-wrap:wrap; margin-top:8px; }
.dns-stat { display:flex; flex-direction:column; gap:2px; }
.dns-stat-val { font-size:22px; font-weight:700; color:var(--text); }
.dns-stat-label { font-size:10px; color:var(--text3); text-transform:uppercase; letter-spacing:.05em; }
.dns-stat.blocked .dns-stat-val { color:var(--danger); }
.dns-stat.allowed .dns-stat-val { color:var(--success); }
.dns-stat.rate .dns-stat-val { color:var(--warning); }
.dns-rate-bar-wrap { flex:1; min-width:80px; height:6px; background:var(--bg3); border-radius:3px; overflow:hidden; align-self:center; }
.dns-rate-bar { height:100%; background: linear-gradient(90deg, var(--success), var(--warning), var(--danger)); border-radius:3px; transition:width .4s; }

.dns-top-list { display:flex; flex-direction:column; gap:5px; margin-top:4px; }
.dns-top-row { display:flex; align-items:center; gap:8px; padding:3px 0; }
.dns-rank { font-size:10px; color:var(--text3); width:14px; text-align:right; flex-shrink:0; }
.dns-domain { font-size:12px; font-family:monospace; color:var(--text2); flex:1; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; min-width:0; }
.dns-count { font-size:11px; color:var(--danger); flex-shrink:0; opacity:.8; }

/* ── Phase 4: Fleet row ──────────────────────────────────────────────────── */
.fleet-row { margin-top: 20px; }
.fleet-panel { padding: 16px 20px; }
.fleet-stats { display: flex; align-items: center; gap: 24px; flex-wrap: wrap; margin-top: 12px; }
.fleet-stat  { display: flex; flex-direction: column; align-items: center; }
.fleet-stat-val   { font-size: 22px; font-weight: 700; color: inherit; line-height: 1; }
.fleet-stat-label { font-size: 11px; color: var(--text3); margin-top: 2px; }
.fleet-divider    { width: 1px; height: 32px; background: var(--border); }
.fleet-dots { flex: 1; height: 6px; background: rgba(239,68,68,.25); border-radius: 3px; overflow: hidden; min-width: 80px; }
.fleet-online-bar { display: block; height: 100%; background: var(--success); border-radius: 3px; transition: width 0.4s; }

/* ── Phase 6: Update banner ───────────────────────────────────────────────── */
.update-banner { display:flex; align-items:center; justify-content:space-between; gap:16px; background:linear-gradient(135deg,rgba(99,102,241,.12),rgba(79,70,229,.08)); border:1px solid rgba(99,102,241,.3); border-radius:var(--radius); padding:14px 20px; flex-wrap:wrap; }
.update-banner-left { display:flex; align-items:center; gap:12px; }
.update-banner-left svg { width:22px; height:22px; fill:var(--accent); flex-shrink:0; }
.update-banner-left strong { display:block; font-size:14px; color:var(--text); font-weight:700; }
.update-sub { font-size:12px; color:var(--text3); }
.update-banner-right { display:flex; align-items:center; gap:10px; flex-shrink:0; }
.update-btn-changelog { font-size:12px; color:var(--accent); text-decoration:none; padding:7px 14px; border:1px solid rgba(99,102,241,.3); border-radius:var(--radius-sm); transition:all .15s; }
.update-btn-changelog:hover { background:rgba(99,102,241,.1); }
.update-btn-primary { display:flex; align-items:center; gap:7px; background:var(--accent); color:#fff; text-decoration:none; padding:8px 16px; border-radius:var(--radius-sm); font-size:13px; font-weight:600; transition:opacity .15s; }
.update-btn-primary svg { width:14px; height:14px; fill:currentColor; }
.update-btn-primary:hover { opacity:.85; }
</style>
