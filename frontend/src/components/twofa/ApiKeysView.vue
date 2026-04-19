<template>
  <div class="apikeys-section">
    <div class="section-header">
      <div>
        <h3>🔑 API Keys</h3>
        <p class="text-muted text-sm">Generate keys for programmatic access to your account data.</p>
      </div>
      <button class="btn-ghost btn-sm" @click="showCreate = true" :disabled="keys.length >= 10">
        + New key
      </button>
    </div>

    <div v-if="loading" class="loading"><div class="spinner"></div>Loading…</div>

    <div v-else-if="!keys.length" class="empty-keys">
      <p class="text-muted text-sm">No API keys yet. Create one to get started.</p>
    </div>

    <table v-else>
      <thead>
        <tr>
          <th>Name</th>
          <th>Prefix</th>
          <th>Created</th>
          <th>Last used</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="k in keys" :key="k.id">
          <td>{{ k.name }}</td>
          <td><code class="mono">{{ k.key_prefix }}…</code></td>
          <td class="text-muted text-sm">{{ fmtDate(k.created_at) }}</td>
          <td class="text-muted text-sm">{{ k.last_used ? fmtDate(k.last_used) : 'Never' }}</td>
          <td>
            <button class="btn-danger btn-sm" @click="revokeKey(k)">Revoke</button>
          </td>
        </tr>
      </tbody>
    </table>

    <div v-if="revokeError" class="alert alert-danger mt-2">{{ revokeError }}</div>

    <!-- Create modal -->
    <div class="modal-overlay" v-if="showCreate" @click.self="showCreate=false">
      <div class="modal">
        <div class="modal-header">
          <span>Create API Key</span>
          <button class="btn-ghost btn-sm" @click="showCreate=false">✕</button>
        </div>

        <div v-if="!createdKey">
          <div class="form-group mt-2">
            <label>Key name <span class="text-muted text-sm">(helps you identify it later)</span></label>
            <input v-model="newKeyName" placeholder="Home script, Monitoring, etc." maxlength="64" />
          </div>
          <div v-if="createError" class="alert alert-danger">{{ createError }}</div>
          <button class="btn-primary w-full mt-2" @click="createKey" :disabled="creating || !newKeyName.trim()">
            {{ creating ? 'Creating…' : 'Create key' }}
          </button>
        </div>

        <!-- Key revealed once -->
        <div v-else class="key-reveal">
          <div class="reveal-header">
            <div class="reveal-icon">✓</div>
            <h4>Key created — copy it now</h4>
            <p class="text-muted text-sm">This key will not be shown again. Store it somewhere safe.</p>
          </div>
          <div class="key-box">
            <code>{{ createdKey }}</code>
            <button class="btn-ghost btn-sm" @click="copyKey">
              {{ copied ? '✓ Copied' : 'Copy' }}
            </button>
          </div>
          <button class="btn-primary w-full mt-3" @click="closeCreate">Done</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '@/utils/api'

const keys        = ref([])
const loading     = ref(true)
const showCreate  = ref(false)
const newKeyName  = ref('')
const creating    = ref(false)
const createError = ref('')
const createdKey  = ref('')
const copied      = ref(false)
const revokeError = ref('')

onMounted(fetchKeys)

async function fetchKeys() {
  loading.value = true
  try {
    const { data } = await api.get('/apikeys/my-keys')
    keys.value = data
  } catch {} finally {
    loading.value = false
  }
}

async function createKey() {
  creating.value    = true
  createError.value = ''
  try {
    const { data } = await api.post('/apikeys/my-keys', { name: newKeyName.value.trim() })
    createdKey.value = data.key
    await fetchKeys()
  } catch (e) {
    createError.value = e.response?.data?.detail || 'Failed to create key'
  } finally {
    creating.value = false
  }
}

async function revokeKey(k) {
  if (!confirm(`Revoke key "${k.name}"? Any scripts using it will stop working.`)) return
  revokeError.value = ''
  try {
    await api.delete(`/apikeys/my-keys/${k.id}`)
    await fetchKeys()
  } catch (e) {
    revokeError.value = e.response?.data?.detail || 'Revoke failed'
  }
}

function copyKey() {
  navigator.clipboard?.writeText(createdKey.value).then(() => {
    copied.value = true
    setTimeout(() => copied.value = false, 2000)
  })
}

function closeCreate() {
  showCreate.value  = false
  createdKey.value  = ''
  newKeyName.value  = ''
  createError.value = ''
  copied.value      = false
}

function fmtDate(d) {
  if (!d) return '—'
  return new Date(d).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}
</script>

<style scoped>
.apikeys-section { }
.section-header { display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:16px; }
.section-header h3 { font-size:15px; font-weight:600; color:var(--text); margin-bottom:4px; }
.empty-keys { padding:20px 0; }
.modal-header { display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; font-size:15px; font-weight:600; }
.key-reveal { text-align:center; }
.reveal-header { margin-bottom:16px; }
.reveal-icon { font-size:32px; margin-bottom:8px; }
.reveal-header h4 { font-size:15px; font-weight:700; color:var(--success); margin-bottom:4px; }
.key-box { display:flex; align-items:center; gap:8px; background:var(--bg3);
           border:1px solid var(--border); border-radius:6px; padding:10px 12px; }
.key-box code { font-family:monospace; font-size:11px; color:var(--accent2); flex:1; word-break:break-all; }
.mt-2 { margin-top:8px; }
.mt-3 { margin-top:16px; }
</style>
