<template>
  <div>
    <div class="page-header">
      <h2 class="page-title">System</h2>
      <button class="btn-ghost btn-sm" @click="load">Refresh</button>
    </div>

    <!-- System Resources -->
    <div class="card mb-3" v-if="info">
      <div class="card-title">System Resources</div>
      <div class="resources-grid">
        <!-- CPU -->
        <div class="res-card">
          <div class="res-icon">⚡</div>
          <div class="res-label">CPU Usage</div>
          <div class="res-value">{{ info.cpu_percent }}%</div>
          <div class="res-bar"><div class="res-fill" :style="{width:info.cpu_percent+'%'}" :class="barColor(info.cpu_percent)"></div></div>
        </div>
        <!-- CPU Temperature -->
        <div class="res-card">
          <div class="res-icon">🌡️</div>
          <div class="res-label">CPU Temp</div>
          <div class="res-value" :class="tempColor(info.cpu_temp_c)">
            {{ info.cpu_temp_c != null ? info.cpu_temp_c + '°C' : 'N/A' }}
          </div>
          <div class="res-bar" v-if="info.cpu_temp_c != null">
            <div class="res-fill" :style="{width:Math.min(info.cpu_temp_c/85*100,100)+'%'}" :class="tempBarColor(info.cpu_temp_c)"></div>
          </div>
          <div class="res-bar" v-else><div class="res-fill" style="width:0%"></div></div>
        </div>
        <!-- RAM -->
        <div class="res-card">
          <div class="res-icon">💾</div>
          <div class="res-label">Memory</div>
          <div class="res-value">{{ info.memory_percent }}%</div>
          <div class="res-sub">{{ info.memory_used_mb }}MB / {{ info.memory_total_mb }}MB</div>
          <div class="res-bar"><div class="res-fill" :style="{width:info.memory_percent+'%'}" :class="barColor(info.memory_percent)"></div></div>
        </div>
        <!-- Disk -->
        <div class="res-card">
          <div class="res-icon">💿</div>
          <div class="res-label">Disk</div>
          <div class="res-value">{{ info.disk_percent }}%</div>
          <div class="res-sub">{{ info.disk_used_gb }}GB / {{ info.disk_total_gb }}GB</div>
          <div class="res-bar"><div class="res-fill" :style="{width:info.disk_percent+'%'}" :class="barColor(info.disk_percent)"></div></div>
        </div>
      </div>
      <div class="uptime-row"><span class="text-muted text-sm">⏱ Uptime:</span> <code>{{ info.uptime }}</code></div>
    </div>

    <div class="grid-2 mb-3">
      <!-- Server info -->
      <div class="card">
        <div class="card-title">Server info</div>
        <div v-if="info" class="info-list">
          <div class="info-row"><span>Hostname / IP</span><code>{{ info.server_hostname }}</code></div>
          <div class="info-row"><span>Current public IP</span>
            <div class="flex items-center gap-2">
              <code>{{ info.current_ip }}</code>
              <button class="btn-ghost btn-sm" @click="refreshIp">Check</button>
            </div>
          </div>
          <div class="info-row"><span>DDNS</span>
            <span class="badge" :class="info.ddns_enabled ? 'badge-success' : 'badge-gray'">
              {{ info.ddns_enabled ? 'Enabled' : 'Disabled' }}
            </span>
          </div>
          <div class="info-row"><span>VPN subnet</span><code>{{ info.vpn_subnet }}</code></div>
          <div class="info-row"><span>Admin port</span><code>{{ info.panel_port }}</code></div>
          <div class="info-row"><span>VPN status</span>
            <span class="badge" :class="info.vpn_running ? 'badge-success' : 'badge-danger'">
              {{ info.vpn_running ? 'Running' : 'Stopped' }}
            </span>
          </div>
        </div>
      </div>

      <!-- Service status -->
      <div class="card">
        <div class="card-title">Services</div>
        <div v-if="services" class="info-list">
          <div class="info-row" v-for="(status, name) in services" :key="name">
            <span class="mono text-sm">{{ name }}</span>
            <span class="badge" :class="status === 'active' ? 'badge-success' : 'badge-danger'">{{ status }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- VPN actions -->
    <div class="card mb-3">
      <div class="card-title">VPN Controls</div>
      <div class="flex gap-2">
        <button class="btn-ghost" @click="restartVpn">Restart VPN</button>
        <button class="btn-ghost" @click="reloadSecrets">Reload Secrets</button>
      </div>
      <div v-if="actionMsg" class="alert mt-2" :class="`alert-${actionMsgType}`">{{ actionMsg }}</div>
    </div>

    <!-- No-DDNS: regenerate certs -->
    <div class="card mb-3" v-if="info && !info.ddns_enabled">
      <div class="card-title" style="color:var(--warning)">IP Changed? Regenerate Certificates</div>
      <p class="text-muted text-sm mb-3">
        Your current public IP is <code>{{ info.current_ip }}</code>. If this has changed, enter the new IP below and regenerate.
      </p>
      <div class="flex gap-2 items-center">
        <input v-model="newIp" placeholder="New public IP" style="max-width:240px" />
        <button class="btn-primary" @click="regenerateCerts" :disabled="regen.loading">
          {{ regen.loading ? 'Regenerating…' : 'Regenerate' }}
        </button>
      </div>
      <div v-if="regen.msg" class="alert mt-2" :class="`alert-${regen.type}`">{{ regen.msg }}</div>
    </div>

    <!-- Connection guide -->
    <div class="card">
      <div class="card-title">Manual connection reference</div>
      <div class="info-list" v-if="info">
        <div class="info-row"><span>Server address</span><code>{{ info.server_hostname }}</code></div>
        <div class="info-row"><span>Protocol</span><code>IKEv2 / IPSec</code></div>
        <div class="info-row"><span>Ports</span><code>UDP 500, UDP 4500</code></div>
        <div class="info-row"><span>iOS type</span><code>IKEv2 or IPSec</code></div>
        <div class="info-row"><span>Android type</span><code>IKEv2/IPSec MSCHAPv2</code></div>
        <div class="info-row"><span>Windows type</span><code>IKEv2 (built-in)</code></div>
        <div class="info-row"><span>Auth method</span><code>Username + Password</code></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '@/utils/api'

const info     = ref(null)
const services = ref(null)
const newIp    = ref('')
const actionMsg     = ref('')
const actionMsgType = ref('info')
const regen = ref({ loading: false, msg: '', type: 'info' })

function barColor(pct) {
  if (pct > 85) return 'fill-danger'
  if (pct > 65) return 'fill-warn'
  return 'fill-ok'
}
function tempColor(t) {
  if (t == null) return 'text-muted'
  if (t > 75) return 'temp-hot'
  if (t > 60) return 'temp-warm'
  return 'temp-ok'
}
function tempBarColor(t) {
  if (t > 75) return 'fill-danger'
  if (t > 60) return 'fill-warn'
  return 'fill-ok'
}

async function load() {
  try {
    const [i, s] = await Promise.all([
      api.get('/system/info'),
      api.get('/system/services'),
    ])
    info.value = i.data
    services.value = s.data
    newIp.value = i.data.current_ip
  } catch {}
}

async function refreshIp() {
  const { data } = await api.get('/system/current-ip')
  if (info.value) info.value.current_ip = data.ip
}

async function restartVpn() {
  try {
    await api.post('/vpn/restart')
    actionMsg.value = 'VPN restarted successfully'; actionMsgType.value = 'success'
  } catch(e) {
    actionMsg.value = 'Restart failed: ' + (e.response?.data?.detail || e.message)
    actionMsgType.value = 'danger'
  }
  setTimeout(() => actionMsg.value = '', 5000)
}

async function reloadSecrets() {
  await api.post('/vpn/reload-secrets')
  actionMsg.value = 'Secrets reloaded'; actionMsgType.value = 'success'
  setTimeout(() => actionMsg.value = '', 3000)
}

async function regenerateCerts() {
  if (!newIp.value) return
  regen.value.loading = true; regen.value.msg = ''
  try {
    const { data } = await api.post('/system/regenerate-certs', { new_ip: newIp.value })
    regen.value.msg  = data.message + ' — ' + data.note
    regen.value.type = 'success'
    await load()
  } catch(e) {
    regen.value.msg  = e.response?.data?.detail || 'Regeneration failed'
    regen.value.type = 'danger'
  } finally { regen.value.loading = false }
}

onMounted(load)
</script>

<style scoped>
.page-header { display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; }
.page-title  { font-size:20px; font-weight:700; }
.grid-2 { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
@media(max-width:900px){ .grid-2 { grid-template-columns:1fr; } }

.resources-grid {
  display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-bottom:12px;
}
@media(max-width:800px){ .resources-grid { grid-template-columns:1fr 1fr; } }
@media(max-width:480px){ .resources-grid { grid-template-columns:1fr; } }

.res-card {
  background:var(--bg3); border:1px solid var(--border); border-radius:10px;
  padding:14px; display:flex; flex-direction:column; gap:4px;
}
.res-icon { font-size:20px; margin-bottom:2px; }
.res-label { font-size:11px; font-weight:600; letter-spacing:.8px; text-transform:uppercase; color:var(--text2); }
.res-value { font-size:22px; font-weight:700; color:var(--text1); line-height:1.2; }
.res-sub { font-size:11px; color:var(--text2); }
.res-bar { height:4px; background:rgba(255,255,255,0.08); border-radius:2px; margin-top:6px; overflow:hidden; }
.res-fill { height:100%; border-radius:2px; transition:width .6s ease; }
.fill-ok { background:linear-gradient(90deg,#10b981,#34d399); }
.fill-warn { background:linear-gradient(90deg,#f59e0b,#fbbf24); }
.fill-danger { background:linear-gradient(90deg,#ef4444,#f87171); }

.temp-ok   { color:#34d399; }
.temp-warm { color:#fbbf24; }
.temp-hot  { color:#f87171; }

.uptime-row { display:flex; align-items:center; gap:8px; padding-top:8px; border-top:1px solid var(--border); }

.info-list { display:flex; flex-direction:column; }
.info-row { display:flex; justify-content:space-between; align-items:center; padding:9px 0; border-bottom:1px solid rgba(46,52,81,0.5); font-size:13px; }
.info-row:last-child { border-bottom:none; }
.info-row > span:first-child { color:var(--text2); }
code { background:var(--bg3); padding:2px 8px; border-radius:4px; font-family:monospace; font-size:12px; color:var(--accent); }
</style>
