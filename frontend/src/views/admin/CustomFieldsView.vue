<template>
  <div>
    <div class="page-header">
      <h2 class="page-title">Custom Profile Fields</h2>
      <button class="btn-primary" @click="addField">+ Add Field</button>
    </div>

    <div class="card mb-4">
      <div class="card-title">
        🗂 Field Schema
        <span class="text-muted text-sm" style="font-weight:400;margin-left:8px">
          Define extra fields shown on every user profile
        </span>
      </div>

      <div v-if="!fields.length" class="empty-state">
        <div class="empty-icon">📋</div>
        <p>No custom fields defined yet.</p>
        <p class="text-muted text-sm">Click "+ Add Field" to create your first field.</p>
      </div>

      <div v-else>
        <div class="field-list">
          <div v-for="(f, i) in fields" :key="i" class="field-row">
            <div class="field-row-content">
              <div class="form-group" style="flex:1;min-width:120px">
                <label>Key <span class="text-muted">(internal)</span></label>
                <input v-model="f.key" placeholder="department" @input="f.key = f.key.toLowerCase().replace(/[^a-z0-9_]/g,'')" />
              </div>
              <div class="form-group" style="flex:1;min-width:120px">
                <label>Label <span class="text-muted">(shown to admin)</span></label>
                <input v-model="f.label" placeholder="Department" />
              </div>
              <div class="form-group" style="width:130px;flex-shrink:0">
                <label>Type</label>
                <select v-model="f.type">
                  <option value="text">Text</option>
                  <option value="textarea">Textarea</option>
                  <option value="select">Select</option>
                  <option value="number">Number</option>
                  <option value="email">Email</option>
                  <option value="url">URL</option>
                  <option value="date">Date</option>
                </select>
              </div>
              <div class="form-group" style="width:90px;flex-shrink:0;display:flex;align-items:flex-end;padding-bottom:2px">
                <label class="check-label" style="margin:0">
                  <input type="checkbox" v-model="f.required" />
                  Required
                </label>
              </div>
              <button class="btn-danger btn-sm field-del" @click="removeField(i)" title="Remove field">✕</button>
            </div>

            <!-- Options editor for select type -->
            <div v-if="f.type === 'select'" class="options-editor">
              <label>Options <span class="text-muted">(one per line)</span></label>
              <textarea
                :value="(f.options||[]).join('\n')"
                @input="f.options = $event.target.value.split('\n').map(s=>s.trim()).filter(Boolean)"
                rows="3"
                placeholder="Basic&#10;Pro&#10;Enterprise"
              ></textarea>
            </div>
          </div>
        </div>

        <div v-if="schemaError" class="alert alert-danger mt-3">{{ schemaError }}</div>
        <div v-if="schemaSaved" class="alert alert-success mt-3">{{ schemaSaved }}</div>

        <div class="flex gap-2 mt-3">
          <button class="btn-primary" @click="saveSchema" :disabled="saving">
            {{ saving ? 'Saving…' : 'Save schema' }}
          </button>
          <button class="btn-ghost" @click="loadSchema">Reset</button>
        </div>
      </div>
    </div>

    <!-- Per-user values editor (shown when a user is selected) -->
    <div class="card" v-if="fields.length">
      <div class="card-title">
        👤 Edit User Values
        <span class="text-muted text-sm" style="font-weight:400;margin-left:8px">
          Select a user to fill their custom field values
        </span>
      </div>
      <div class="flex gap-2 mb-3" style="align-items:center">
        <select v-model="selectedUserId" style="max-width:260px" @change="loadUserFields">
          <option value="">— Select a user —</option>
          <option v-for="u in users" :key="u.id" :value="u.id">
            {{ u.username }} ({{ u.full_name }})
          </option>
        </select>
      </div>

      <div v-if="selectedUserId && userFields">
        <div v-for="f in fields" :key="f.key" class="form-group">
          <label>{{ f.label }} <span v-if="f.required" class="req">*</span></label>

          <textarea v-if="f.type==='textarea'"
            v-model="userFields[f.key]" rows="2"></textarea>
          <select v-else-if="f.type==='select'" v-model="userFields[f.key]">
            <option value="">— select —</option>
            <option v-for="opt in (f.options||[])" :key="opt" :value="opt">{{ opt }}</option>
          </select>
          <input v-else
            v-model="userFields[f.key]"
            :type="f.type"
            :placeholder="f.label" />
        </div>

        <div v-if="valuesError" class="alert alert-danger">{{ valuesError }}</div>
        <div v-if="valuesSaved" class="alert alert-success">{{ valuesSaved }}</div>
        <button class="btn-primary mt-2" @click="saveUserFields" :disabled="savingValues">
          {{ savingValues ? 'Saving…' : 'Save values' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '@/utils/api'

const fields      = ref([])
const saving      = ref(false)
const schemaError = ref('')
const schemaSaved = ref('')

const users          = ref([])
const selectedUserId = ref('')
const userFields     = ref(null)
const savingValues   = ref(false)
const valuesError    = ref('')
const valuesSaved    = ref('')

onMounted(async () => {
  await loadSchema()
  try {
    const { data } = await api.get('/users/')
    users.value = data
  } catch {}
})

async function loadSchema() {
  try {
    const { data } = await api.get('/customfields/schema')
    fields.value = (data.fields || []).map(f => ({ ...f, options: f.options || [] }))
  } catch (e) {
    schemaError.value = 'Failed to load schema'
  }
}

function addField() {
  fields.value.push({ key: '', label: '', type: 'text', required: false, options: [] })
}

function removeField(i) {
  fields.value.splice(i, 1)
}

async function saveSchema() {
  schemaError.value = ''
  schemaSaved.value = ''

  // Client-side validation
  for (const f of fields.value) {
    if (!f.key) { schemaError.value = 'All fields must have a key'; return }
    if (!f.label) { schemaError.value = 'All fields must have a label'; return }
    if (f.type === 'select' && (!f.options || !f.options.length)) {
      schemaError.value = `Field "${f.label}" is type "select" but has no options`; return
    }
  }

  saving.value = true
  try {
    await api.put('/customfields/schema', { fields: fields.value })
    schemaSaved.value = '✓ Schema saved'
    setTimeout(() => schemaSaved.value = '', 3000)
  } catch (e) {
    schemaError.value = e.response?.data?.detail || 'Save failed'
  } finally {
    saving.value = false
  }
}

async function loadUserFields() {
  if (!selectedUserId.value) { userFields.value = null; return }
  try {
    const { data } = await api.get(`/customfields/users/${selectedUserId.value}/fields`)
    const vals = {}
    for (const f of fields.value) vals[f.key] = data.values?.[f.key] ?? ''
    userFields.value = vals
  } catch { userFields.value = {} }
}

async function saveUserFields() {
  savingValues.value = true
  valuesError.value  = ''
  valuesSaved.value  = ''
  try {
    await api.put(`/customfields/users/${selectedUserId.value}/fields`, { values: userFields.value })
    valuesSaved.value = '✓ Values saved'
    setTimeout(() => valuesSaved.value = '', 3000)
  } catch (e) {
    valuesError.value = e.response?.data?.detail || 'Save failed'
  } finally {
    savingValues.value = false
  }
}
</script>

<style scoped>
.page-header { display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; }
.page-title  { font-size:20px; font-weight:700; color:var(--text); }
.empty-state { text-align:center; padding:40px; color:var(--text3); }
.empty-icon  { font-size:32px; margin-bottom:12px; }
.field-list  { display:flex; flex-direction:column; gap:12px; }
.field-row   { background:var(--bg3); border:1px solid var(--border); border-radius:var(--radius-sm); padding:14px; }
.field-row-content { display:flex; gap:12px; flex-wrap:wrap; align-items:flex-start; }
.field-del   { align-self:flex-end; margin-bottom:2px; flex-shrink:0; }
.options-editor { margin-top:10px; border-top:1px solid var(--border); padding-top:10px; }
.req  { color:var(--danger); }
.check-label { display:flex; align-items:center; gap:6px; font-size:13px; color:var(--text2); cursor:pointer; }
.mt-2 { margin-top:8px; }
.mt-3 { margin-top:16px; }
</style>
