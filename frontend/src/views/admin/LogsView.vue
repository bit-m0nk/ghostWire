<template>
  <div>
    <div class="page-header">
      <h2 class="page-title">Audit Logs</h2>
      <button class="btn-ghost btn-sm" @click="load">Refresh</button>
    </div>

    <div class="card">
      <div class="flex gap-2 mb-3">
        <input v-model="search" placeholder="Search logs…" style="max-width:260px" />
        <select v-model="levelFilter" style="max-width:140px">
          <option value="">All levels</option>
          <option value="info">Info</option>
          <option value="warning">Warning</option>
          <option value="danger">Danger</option>
        </select>
      </div>

      <div v-if="loading" class="loading"><div class="spinner"></div>Loading…</div>
      <table v-else>
        <thead>
          <tr>
            <th>Time</th><th>Level</th><th>Actor</th>
            <th>Action</th><th>Target</th><th>IP</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="l in filtered" :key="l.timestamp + l.action">
            <td class="text-sm text-muted">{{ fmtDate(l.timestamp) }}</td>
            <td>
              <span class="badge" :class="`badge-${l.level === 'info' ? 'info' : l.level === 'warning' ? 'warning' : 'danger'}`">
                {{ l.level }}
              </span>
            </td>
            <td><span class="mono">{{ l.actor }}</span></td>
            <td><span class="mono text-sm">{{ l.action }}</span></td>
            <td class="text-muted">{{ l.target }}</td>
            <td><span class="mono text-sm">{{ l.ip_address }}</span></td>
          </tr>
        </tbody>
      </table>
      <div v-if="!loading && filtered.length === 0" class="empty">No log entries found</div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '@/utils/api'

const logs        = ref([])
const loading     = ref(false)
const search      = ref('')
const levelFilter = ref('')

const filtered = computed(() => {
  let result = logs.value
  if (levelFilter.value) result = result.filter(l => l.level === levelFilter.value)
  if (search.value) {
    const q = search.value.toLowerCase()
    result = result.filter(l =>
      l.actor.toLowerCase().includes(q) ||
      l.action.toLowerCase().includes(q) ||
      l.target.toLowerCase().includes(q)
    )
  }
  return result
})

async function load() {
  loading.value = true
  try { logs.value = (await api.get('/stats/audit-log')).data }
  finally { loading.value = false }
}

function fmtDate(d) {
  if (!d) return "—"
  const dt = new Date(d.endsWith("Z") ? d : d + "Z")
  return dt.toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" })
}

onMounted(load)
</script>

<style scoped>
.page-header { display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; }
.page-title  { font-size:20px; font-weight:700; }
.empty { text-align:center; color:var(--text3); padding:40px; font-size:13px; }
</style>
