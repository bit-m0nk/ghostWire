<template>
  <div>
    <div class="page-header">
      <h2 class="page-title">Users</h2>
      <button class="btn-primary" @click="openCreate">+ Add User</button>
    </div>

    <div class="card">
      <div class="flex gap-2 mb-3">
        <input v-model="search" placeholder="Search users…" style="max-width:260px" />
      </div>
      <div v-if="loading" class="loading"><div class="spinner"></div>Loading…</div>
      <table v-else>
        <thead>
          <tr>
            <th>Username</th><th>Full name</th><th>Email</th>
            <th>Panel</th><th>VPN</th><th>2FA</th><th>Created</th><th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in filtered" :key="u.id">
            <td><span class="mono">{{ u.username }}</span></td>
            <td>{{ u.full_name }}</td>
            <td class="text-muted">{{ u.email }}</td>
            <td><span class="badge" :class="u.is_active?'badge-success':'badge-danger'">{{ u.is_active?'Active':'Disabled' }}</span></td>
            <td><span class="badge" :class="u.vpn_enabled?'badge-info':'badge-gray'">{{ u.vpn_enabled?'Enabled':'Off' }}</span></td>
            <td><span class="badge" :class="u.totp_enabled?'badge-success':'badge-gray'" :title="u.totp_enabled?'TOTP 2FA active':'No 2FA'">{{ u.totp_enabled?'On':'Off' }}</span></td>
            <td class="text-muted text-sm">{{ fmtDate(u.created_at) }}</td>
            <td>
              <div class="flex gap-1 flex-wrap">
                <button class="btn-ghost btn-sm" @click="openEdit(u)">Edit</button>
                <button class="btn-ghost btn-sm" @click="openResetPanel(u)">Reset Panel PW</button>
                <button class="btn-ghost btn-sm" @click="resetVpn(u)">Reset VPN PW</button>
                <button v-if="u.totp_enabled" class="btn-ghost btn-sm" @click="reset2fa(u)" title="Disable 2FA for this user (e.g. lost phone)">Reset 2FA</button>
                <button class="btn-danger btn-sm" @click="deleteUser(u)" :disabled="u.is_admin">Delete</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Create user modal -->
    <div class="modal-overlay" v-if="showCreate" @click.self="showCreate=false">
      <div class="modal">
        <div class="modal-header">
          <span>Add New User</span>
          <button class="btn-ghost btn-sm" @click="showCreate=false">✕</button>
        </div>
        <div class="form-group">
          <label>Username *</label>
          <input v-model="form.username" placeholder="john" />
        </div>
        <div class="form-group">
          <label>Full name *</label>
          <input v-model="form.full_name" placeholder="John Doe" />
        </div>
        <div class="form-group">
          <label>Email *</label>
          <input v-model="form.email" type="email" placeholder="john@example.com" />
        </div>
        <div class="form-group">
          <label>Panel login password <span class="text-muted text-sm">(leave blank to auto-generate)</span></label>
          <input v-model="form.password" type="password" placeholder="auto-generated if blank" autocomplete="new-password" />
        </div>
        <div class="form-group">
          <label>VPN password <span class="text-muted text-sm">(leave blank to auto-generate)</span></label>
          <input v-model="form.vpn_password" type="text" placeholder="auto-generated if blank — user needs this for config profiles" autocomplete="off" />
          <div class="text-muted text-sm mt-1">User enters this in the VPN portal to download configs. Must be memorable or share securely.</div>
        </div>
        <div class="flex gap-3 mt-2 flex-wrap">
          <label class="check-label"><input type="checkbox" v-model="form.vpn_enabled" /> VPN access</label>
          <label class="check-label"><input type="checkbox" v-model="form.is_admin" /> Admin</label>
          <label class="check-label email-check" :title="smtpConfigured ? '' : 'Configure SMTP in .env to enable'">
            <input type="checkbox" v-model="form.send_email" :disabled="!smtpConfigured" />
            <span>Send credentials via email</span>
            <span v-if="!smtpConfigured" class="smtp-badge"><router-link to="/config" style="color:inherit;text-decoration:underline">SMTP not configured</router-link></span>
          </label>
        </div>
        <div class="form-group mt-2">
          <label>Notes</label>
          <textarea v-model="form.notes" rows="2" placeholder="Optional notes"></textarea>
        </div>

        <div v-if="createResult" class="alert alert-success mt-2">
          <strong>✓ User created!</strong><br>
          Panel username: <span class="mono">{{ createResult.username }}</span><br>
          Panel password: <span class="mono">{{ createResult.panel_password }}</span><br>
          VPN username: <span class="mono">{{ createResult.vpn_username }}</span><br>
          VPN password: <span class="mono">{{ createResult.vpn_password }}</span><br>
          <span class="text-sm" style="color:var(--warning)">⚠ Save these now — they won't be shown again.</span>
          <div v-if="createResult.email_status" class="email-status-row" :class="createResult.email_status.sent ? 'email-sent' : 'email-fail'">
            {{ createResult.email_status.sent ? '📧 ' + createResult.email_status.message : '⚠ ' + createResult.email_status.message }}
          </div>
        </div>
        <div v-if="formError" class="alert alert-danger mt-2">{{ formError }}</div>

        <div class="flex gap-2 mt-3">
          <button class="btn-primary" @click="createUser" :disabled="creating">
            {{ creating ? 'Creating…' : 'Create User' }}
          </button>
          <button class="btn-ghost" @click="showCreate=false">Cancel</button>
        </div>
      </div>
    </div>

    <!-- Edit user modal -->
    <div class="modal-overlay" v-if="editUser" @click.self="editUser=null">
      <div class="modal">
        <div class="modal-header">
          <span>Edit — {{ editUser.username }}</span>
          <button class="btn-ghost btn-sm" @click="editUser=null">✕</button>
        </div>
        <div class="form-group">
          <label>Full name</label>
          <input v-model="editForm.full_name" />
        </div>
        <div class="form-group">
          <label>Email</label>
          <input v-model="editForm.email" type="email" />
        </div>
        <div class="flex gap-3 mt-2 mb-3">
          <label class="check-label"><input type="checkbox" v-model="editForm.is_active" /> Active</label>
          <label class="check-label"><input type="checkbox" v-model="editForm.vpn_enabled" /> VPN access</label>
        </div>
        <div class="form-group">
          <label>Notes</label>
          <textarea v-model="editForm.notes" rows="2"></textarea>
        </div>
        <div v-if="editError" class="alert alert-danger mt-2">{{ editError }}</div>
        <div class="flex gap-2 mt-3">
          <button class="btn-primary" @click="saveEdit">Save changes</button>
          <button class="btn-ghost" @click="editUser=null">Cancel</button>
        </div>
      </div>
    </div>

    <!-- Reset panel password modal -->
    <div class="modal-overlay" v-if="resetPanelUser" @click.self="resetPanelUser=null">
      <div class="modal">
        <div class="modal-header">
          <span>Reset Panel Password — {{ resetPanelUser.username }}</span>
          <button class="btn-ghost btn-sm" @click="resetPanelUser=null">✕</button>
        </div>
        <div class="alert alert-warning mb-3">The user will need this new password to log into the panel.</div>
        <div class="form-group">
          <label>New panel password <span class="text-muted text-sm">(leave blank to auto-generate)</span></label>
          <input v-model="resetPanelPw" type="text" placeholder="auto-generated if blank" autocomplete="off" />
        </div>
        <div class="flex gap-3 mt-2 mb-2">
          <label class="check-label" :title="smtpConfigured ? '' : 'Configure SMTP in Config page to enable'">
            <input type="checkbox" v-model="resetPanelSendPackage" :disabled="!smtpConfigured" />
            <span>Also send connection package email</span>
            <span v-if="!smtpConfigured" class="smtp-badge"><router-link to="/config" style="color:inherit;text-decoration:underline">SMTP not configured</router-link></span>
          </label>
        </div>
        <div v-if="resetPanelResult" class="alert alert-success mt-2">
          New panel password: <span class="mono">{{ resetPanelResult.new_password }}</span><br>
          <span class="text-sm" style="color:var(--warning)">⚠ Share securely — not shown again.</span>
          <div v-if="resetPanelResult.email_status" class="email-status-row mt-1"
               :class="resetPanelResult.email_status.sent ? 'email-sent' : 'email-fail'">
            {{ resetPanelResult.email_status.sent ? '📧 ' + resetPanelResult.email_status.message : '⚠ ' + resetPanelResult.email_status.message }}
          </div>
        </div>
        <div v-if="resetPanelError" class="alert alert-danger mt-2">{{ resetPanelError }}</div>
        <div class="flex gap-2 mt-3">
          <button class="btn-primary" @click="doResetPanel" :disabled="resettingPanel">
            {{ resettingPanel ? 'Resetting…' : 'Reset Password' }}
          </button>
          <button class="btn-ghost" @click="resetPanelUser=null">Close</button>
        </div>
      </div>
    </div>

    <!-- VPN reset result modal -->
    <div class="modal-overlay" v-if="vpnResetResult" @click.self="vpnResetResult=null">
      <div class="modal">
        <div class="modal-header">
          <span>VPN Credentials Reset</span>
          <button class="btn-ghost btn-sm" @click="vpnResetResult=null">✕</button>
        </div>
        <div class="alert alert-warning mb-3">Share these credentials securely with the user.</div>
        <div class="form-group">
          <label>VPN Username</label>
          <input :value="vpnResetResult.vpn_username" readonly class="mono" />
        </div>
        <div class="form-group">
          <label>VPN Password</label>
          <input :value="vpnResetResult.vpn_password" readonly class="mono" />
        </div>
        <div class="text-muted text-sm mb-3">User must re-download their config profiles from the portal.</div>
        <div v-if="vpnResetResult.email_status" class="email-status-row mb-3"
             :class="vpnResetResult.email_status.sent ? 'email-sent' : 'email-fail'">
          {{ vpnResetResult.email_status.sent ? '📧 ' + vpnResetResult.email_status.message : '⚠ ' + vpnResetResult.email_status.message }}
        </div>
        <button class="btn-primary" @click="vpnResetResult=null">Done</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '@/utils/api'

const users      = ref([])
const loading    = ref(true)
const search     = ref('')
const showCreate = ref(false)
const creating   = ref(false)
const createResult = ref(null)
const formError  = ref('')
const editUser   = ref(null)
const editForm   = ref({})
const editError  = ref('')
const vpnResetResult = ref(null)
const resetPanelUser        = ref(null)
const resetPanelPw          = ref('')
const resetPanelResult      = ref(null)
const resetPanelError       = ref('')
const resettingPanel        = ref(false)
const resetPanelSendPackage = ref(false)
const smtpConfigured        = ref(false)

const form = ref({ username:'', full_name:'', email:'', password:'', vpn_password:'', vpn_enabled:true, is_admin:false, send_email:false, notes:'' })

const filtered = computed(() => {
  if (!search.value) return users.value
  const q = search.value.toLowerCase()
  return users.value.filter(u =>
    u.username.toLowerCase().includes(q) ||
    u.full_name.toLowerCase().includes(q) ||
    u.email.toLowerCase().includes(q)
  )
})

async function load() {
  loading.value = true
  try { users.value = (await api.get('/users/')).data }
  finally { loading.value = false }
}

async function checkSmtp() {
  try {
    const { data } = await api.get('/config/status')
    smtpConfigured.value = data.smtp?.configured === true
  } catch (e) {
    smtpConfigured.value = false
  }
}

function openCreate() {
  form.value = { username:'', full_name:'', email:'', password:'', vpn_password:'', vpn_enabled:true, is_admin:false, send_email:false, notes:'' }
  createResult.value = null; formError.value = ''
  showCreate.value = true
}

async function createUser() {
  creating.value = true; formError.value = ''; createResult.value = null
  try {
    const { data } = await api.post('/users/', form.value)
    createResult.value = data
    await load()
  } catch(e) {
    formError.value = e.response?.data?.detail || 'Failed to create user'
  } finally { creating.value = false }
}

function openEdit(u) {
  editUser.value = u
  editForm.value = { full_name: u.full_name, email: u.email, is_active: u.is_active, vpn_enabled: u.vpn_enabled, notes: u.notes || '' }
  editError.value = ''
}

async function saveEdit() {
  editError.value = ''
  try {
    await api.patch(`/users/${editUser.value.id}`, editForm.value)
    editUser.value = null
    await load()
  } catch(e) { editError.value = e.response?.data?.detail || 'Failed to save' }
}

async function deleteUser(u) {
  if (!confirm(`Delete "${u.username}"? Cannot be undone.`)) return
  try { await api.delete(`/users/${u.id}`); await load() }
  catch(e) { alert(e.response?.data?.detail || 'Delete failed') }
}

async function resetVpn(u) {
  if (!confirm(`Reset VPN credentials for "${u.username}"? They must re-download config profiles.`)) return
  try {
    const { data } = await api.post(`/users/${u.id}/reset-vpn-password`)
    vpnResetResult.value = data
  } catch(e) { alert(e.response?.data?.detail || 'VPN reset failed') }
}

async function reset2fa(u) {
  if (!confirm(`Disable 2FA for "${u.username}"? Do this only if they have lost their authenticator device.`)) return
  try {
    await api.post(`/2fa/admin/reset/${u.id}`)
    await load()
  } catch(e) { alert(e.response?.data?.detail || '2FA reset failed') }
}

function openResetPanel(u) {
  resetPanelUser.value = u; resetPanelPw.value = ''
  resetPanelResult.value = null; resetPanelError.value = ''
  resetPanelSendPackage.value = false
}

async function doResetPanel() {
  resettingPanel.value = true; resetPanelError.value = ''; resetPanelResult.value = null
  try {
    const { data } = await api.post(`/users/${resetPanelUser.value.id}/reset-password`, {
      new_password: resetPanelPw.value || null,
      send_connection_package: resetPanelSendPackage.value,
    })
    resetPanelResult.value = data
  } catch(e) { resetPanelError.value = e.response?.data?.detail || 'Reset failed' }
  finally { resettingPanel.value = false }
}

function fmtDate(d) {
  if (!d) return '—'
  // Parse as UTC then show in user's local timezone
  const dt = new Date(d.endsWith('Z') ? d : d + 'Z')
  return dt.toLocaleDateString(undefined, { year:'numeric', month:'short', day:'numeric' })
}

onMounted(() => { load(); checkSmtp() })
</script>

<style scoped>
.page-header { display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; }
.page-title  { font-size:20px; font-weight:700; color:var(--text); }
.flex-wrap   { flex-wrap:wrap; }

.modal-overlay { position:fixed; inset:0; background:rgba(0,0,0,0.75); display:flex; align-items:center; justify-content:center; z-index:1000; padding:16px; }
.modal {
  background:var(--bg2);
  border:1px solid var(--border);
  border-radius:var(--radius);
  padding:24px;
  width:100%;
  max-width:500px;
  max-height:90vh;
  overflow-y:auto;
  color:var(--text);
}
.modal input,
.modal textarea,
.modal select { color:var(--text); background:var(--bg3); }
.modal label { color:var(--text2); }
.modal-header { display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; font-size:15px; font-weight:600; color:var(--text); }
.check-label { display:flex; align-items:center; gap:6px; cursor:pointer; color:var(--text2); font-size:13px; }
.check-label input[type=checkbox] { width:auto; }
.mt-1 { margin-top:4px; }
.email-check { display:flex; align-items:center; gap:6px; }
.smtp-badge { font-size:10px; background:rgba(245,158,11,0.15); color:#f59e0b; border:1px solid rgba(245,158,11,0.3); padding:2px 6px; border-radius:4px; margin-left:4px; }
.email-status-row { margin-top:8px; padding:6px 10px; border-radius:6px; font-size:12px; }
.email-sent { background:rgba(16,185,129,0.1); color:#34d399; border:1px solid rgba(16,185,129,0.2); }
.email-fail { background:rgba(239,68,68,0.1); color:#f87171; border:1px solid rgba(239,68,68,0.2); }
</style>
