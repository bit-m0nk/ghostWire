<template>
  <div class="view-root">
    <div class="view-header">
      <div>
        <h1 class="view-title">Theming Engine</h1>
        <p class="view-sub">Customize the dashboard appearance. Changes apply instantly.</p>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <span>Loading themes…</span>
    </div>

    <template v-else>
      <!-- Built-in theme selector -->
      <div class="section-label">Built-in Themes</div>
      <div class="themes-grid">
        <div
          v-for="theme in builtinThemes"
          :key="theme.slug"
          class="theme-card"
          :class="{ active: theme.is_active, previewing: previewSlug === theme.slug }"
          @mouseenter="startPreview(theme)"
          @mouseleave="endPreview"
        >
          <div class="theme-preview" :style="previewStyle(theme)">
            <div class="preview-sidebar">
              <div class="preview-logo" :style="{ background: theme.variables['--accent'] }"></div>
              <div class="preview-nav-item" v-for="i in 5" :key="i" :style="i === 2 ? { background: theme.variables['--accent3'] } : {}"></div>
            </div>
            <div class="preview-content">
              <div class="preview-card" :style="{ background: theme.variables['--bg2'], borderColor: theme.variables['--border'] }">
                <div class="preview-card-title" :style="{ background: theme.variables['--text'] }"></div>
                <div class="preview-stat" :style="{ background: theme.variables['--accent'] }"></div>
              </div>
              <div class="preview-card" :style="{ background: theme.variables['--bg2'], borderColor: theme.variables['--border'] }">
                <div class="preview-card-title" :style="{ background: theme.variables['--text'] }"></div>
                <div class="preview-stat" :style="{ background: theme.variables['--success'] }"></div>
              </div>
            </div>
          </div>
          <div class="theme-info">
            <div class="theme-name-row">
              <span class="theme-name">{{ theme.name }}</span>
              <span v-if="theme.is_active" class="badge-active">Active</span>
            </div>
            <p class="theme-desc">{{ theme.description }}</p>
            <button
              v-if="!theme.is_active"
              class="btn-activate"
              :disabled="activating === theme.slug"
              @click="activate(theme.slug)"
            >
              {{ activating === theme.slug ? 'Applying…' : 'Apply Theme' }}
            </button>
            <div v-else class="active-indicator">
              <svg viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
              Currently Active
            </div>
          </div>
        </div>
      </div>

      <!-- Custom themes -->
      <div class="section-header">
        <div class="section-label">Custom Themes</div>
        <button class="btn-secondary" @click="openCustomBuilder(null)">
          <svg viewBox="0 0 24 24"><path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/></svg>
          New Theme
        </button>
      </div>

      <div v-if="customThemes.length === 0" class="empty-state">
        <svg viewBox="0 0 24 24"><path d="M12 3c-4.97 0-9 4.03-9 9s4.03 9 9 9 9-4.03 9-9-4.03-9-9-9zm0 2c.76 0 1.48.11 2.17.3L5.47 13.69C5.17 12.98 5 12.21 5 11.41 5 6.82 8.13 5 12 5zm0 14c-.76 0-1.48-.11-2.17-.3l8.7-8.39c.3.71.47 1.48.47 2.28C19 17.18 15.87 19 12 19z"/></svg>
        <p>No custom themes yet. Create one to get started.</p>
      </div>

      <div v-else class="themes-grid">
        <div
          v-for="theme in customThemes"
          :key="theme.slug"
          class="theme-card"
          :class="{ active: theme.is_active }"
          @mouseenter="startPreview(theme)"
          @mouseleave="endPreview"
        >
          <div class="theme-preview" :style="previewStyle(theme)">
            <div class="preview-sidebar">
              <div class="preview-logo" :style="{ background: theme.variables['--accent'] }"></div>
              <div class="preview-nav-item" v-for="i in 5" :key="i" :style="i === 2 ? { background: theme.variables['--accent3'] } : {}"></div>
            </div>
            <div class="preview-content">
              <div class="preview-card" :style="{ background: theme.variables['--bg2'], borderColor: theme.variables['--border'] }">
                <div class="preview-card-title" :style="{ background: theme.variables['--text'] }"></div>
                <div class="preview-stat" :style="{ background: theme.variables['--accent'] }"></div>
              </div>
            </div>
          </div>
          <div class="theme-info">
            <div class="theme-name-row">
              <span class="theme-name">{{ theme.name }}</span>
              <span v-if="theme.is_active" class="badge-active">Active</span>
            </div>
            <p class="theme-desc">{{ theme.description || 'Custom theme' }}</p>
            <div class="theme-actions">
              <button
                v-if="!theme.is_active"
                class="btn-activate"
                :disabled="activating === theme.slug"
                @click="activate(theme.slug)"
              >{{ activating === theme.slug ? 'Applying…' : 'Apply' }}</button>
              <div v-else class="active-indicator">
                <svg viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
                Active
              </div>
              <button class="btn-icon" title="Edit" @click="openCustomBuilder(theme)">
                <svg viewBox="0 0 24 24"><path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zm17.71-10.21a1 1 0 000-1.41l-2.34-2.34a1 1 0 00-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/></svg>
              </button>
              <button class="btn-icon danger" title="Delete" @click="deleteCustomTheme(theme.slug)" :disabled="theme.is_active">
                <svg viewBox="0 0 24 24"><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg>
              </button>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- Custom Theme Builder Modal -->
    <div v-if="showBuilder" class="modal-overlay" @click.self="closeBuilder">
      <div class="modal-lg">
        <div class="modal-header">
          <h2>{{ editingTheme ? 'Edit Theme' : 'Create Custom Theme' }}</h2>
          <button class="btn-icon" @click="closeBuilder">
            <svg viewBox="0 0 24 24"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>
          </button>
        </div>

        <div class="builder-layout">
          <!-- Left: controls -->
          <div class="builder-controls">
            <div class="form-group">
              <label>Theme Name</label>
              <input v-model="draft.name" class="form-input" placeholder="My Dark Theme" />
            </div>
            <div class="form-group" v-if="!editingTheme">
              <label>Slug (URL-safe identifier)</label>
              <input v-model="draft.slug" class="form-input" placeholder="my-dark-theme" />
            </div>
            <div class="form-group">
              <label>Description</label>
              <input v-model="draft.description" class="form-input" placeholder="Optional description" />
            </div>

            <div class="color-grid">
              <div v-for="(label, key) in colorVars" :key="key" class="color-row">
                <label class="color-label">{{ label }}</label>
                <div class="color-input-wrap">
                  <input
                    type="color"
                    :value="draft.variables[key] || '#000000'"
                    @input="draft.variables[key] = $event.target.value"
                    class="color-swatch"
                  />
                  <input
                    type="text"
                    :value="draft.variables[key] || ''"
                    @input="draft.variables[key] = $event.target.value"
                    class="color-hex"
                    placeholder="#000000"
                  />
                </div>
              </div>
            </div>

            <div class="form-group" style="margin-top:16px">
              <label>Base on existing theme</label>
              <select class="form-input" @change="copyFrom($event.target.value)">
                <option value="">— select to copy values —</option>
                <option v-for="t in allThemes" :key="t.slug" :value="t.slug">{{ t.name }}</option>
              </select>
            </div>
          </div>

          <!-- Right: live preview -->
          <div class="builder-preview">
            <div class="preview-label">Live Preview</div>
            <div class="live-preview" :style="livePreviewStyle">
              <div class="lp-sidebar">
                <div class="lp-logo" :style="{ background: draft.variables['--accent'] }">GW</div>
                <div v-for="(item, i) in ['Dashboard','Users','DNS','Analytics','Nodes']" :key="item" class="lp-nav" :style="i === 0 ? { background: draft.variables['--accent3'], color: draft.variables['--accent'] } : { color: draft.variables['--text2'] }">
                  {{ item }}
                </div>
              </div>
              <div class="lp-content">
                <div class="lp-topbar" :style="{ borderColor: draft.variables['--border'] }">
                  <span :style="{ color: draft.variables['--text'] }">Dashboard</span>
                </div>
                <div class="lp-cards">
                  <div v-for="(card, i) in previewCards" :key="i" class="lp-card" :style="{ background: draft.variables['--bg2'], borderColor: draft.variables['--border'] }">
                    <div class="lp-card-val" :style="{ color: card.color }">{{ card.val }}</div>
                    <div class="lp-card-label" :style="{ color: draft.variables['--text3'] }">{{ card.label }}</div>
                  </div>
                </div>
                <div class="lp-table" :style="{ background: draft.variables['--bg2'], borderColor: draft.variables['--border'] }">
                  <div class="lp-row header" :style="{ borderColor: draft.variables['--border'], color: draft.variables['--text3'] }">
                    <span>User</span><span>Status</span><span>IP</span>
                  </div>
                  <div v-for="i in 3" :key="i" class="lp-row" :style="{ borderColor: draft.variables['--border'], color: draft.variables['--text2'] }">
                    <span>user_{{ i }}</span>
                    <span :style="{ color: draft.variables['--success'] }">● Online</span>
                    <span>10.6.0.{{ i }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="modal-footer">
          <button class="btn-secondary" @click="closeBuilder">Cancel</button>
          <button class="btn-primary" :disabled="saving" @click="saveTheme">
            {{ saving ? 'Saving…' : (editingTheme ? 'Update Theme' : 'Create Theme') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import api from '@/utils/api'

const themes      = ref([])
const loading     = ref(true)
const activating  = ref(null)
const previewSlug = ref(null)
const showBuilder = ref(false)
const editingTheme = ref(null)
const saving      = ref(false)

const colorVars = {
  '--bg1':     'Background (deepest)',
  '--bg2':     'Background (cards)',
  '--bg3':     'Background (hover)',
  '--border':  'Border colour',
  '--text':    'Primary text',
  '--text2':   'Secondary text',
  '--text3':   'Muted text',
  '--accent':  'Accent / primary',
  '--accent2': 'Accent (darker)',
  '--success': 'Success green',
  '--warning': 'Warning amber',
  '--danger':  'Danger red',
  '--info':    'Info blue',
}

const defaultDraft = () => ({
  name: '',
  slug: '',
  description: '',
  variables: {
    '--bg1': '#0a0c14', '--bg2': '#111827', '--bg3': '#1a2035',
    '--border': '#1e2a3a', '--text': '#e2e8f0', '--text2': '#94a3b8',
    '--text3': '#64748b', '--accent': '#6366f1', '--accent2': '#4f46e5',
    '--accent3': 'rgba(99,102,241,0.15)',
    '--success': '#34d399', '--warning': '#fbbf24',
    '--danger': '#f87171', '--info': '#60a5fa',
  }
})

const draft = ref(defaultDraft())

const previewCards = computed(() => [
  { val: '12', label: 'Users', color: draft.value.variables['--accent'] },
  { val: '8',  label: 'Online', color: draft.value.variables['--success'] },
  { val: '43', label: 'Blocked', color: draft.value.variables['--warning'] },
])

const builtinThemes = computed(() => themes.value.filter(t => t.is_builtin))
const customThemes  = computed(() => themes.value.filter(t => !t.is_builtin))
const allThemes     = computed(() => themes.value)

let _previewOriginal = null
let _previewTimer    = null

async function load() {
  try {
    const { data } = await api.get('/themes/')
    themes.value = data
  } finally {
    loading.value = false
  }
}

function previewStyle(theme) {
  return { background: theme.variables['--bg1'] }
}

function startPreview(theme) {
  previewSlug.value = theme.slug
  clearTimeout(_previewTimer)
  if (!_previewOriginal) {
    _previewOriginal = _snapshotVars()
  }
  _applyVars(theme.variables)
}

function endPreview() {
  previewSlug.value = null
  if (_previewOriginal) {
    _applyVars(_previewOriginal)
  }
}

async function activate(slug) {
  activating.value = slug
  // Clear hover preview before applying permanent one
  if (_previewOriginal) {
    _previewOriginal = null
  }
  try {
    await api.post(`/themes/activate/${slug}`)
    await load()
    const active = themes.value.find(t => t.slug === slug)
    if (active) _applyVars(active.variables)
  } catch (e) {
    console.error(e)
  } finally {
    activating.value = null
  }
}

// ── Custom builder ────────────────────────────────────────────────────────────

function openCustomBuilder(theme) {
  if (theme) {
    editingTheme.value = theme
    draft.value = {
      name: theme.name,
      slug: theme.slug,
      description: theme.description || '',
      variables: { ...theme.variables },
    }
  } else {
    editingTheme.value = null
    draft.value = defaultDraft()
  }
  showBuilder.value = true
}

function closeBuilder() {
  showBuilder.value = false
  editingTheme.value = null
}

function copyFrom(slug) {
  if (!slug) return
  const t = themes.value.find(t => t.slug === slug)
  if (t) draft.value.variables = { ...t.variables }
}

const livePreviewStyle = computed(() => ({
  background: draft.value.variables['--bg1'],
  '--lp-bg2':    draft.value.variables['--bg2'],
  '--lp-border': draft.value.variables['--border'],
  '--lp-text':   draft.value.variables['--text'],
  '--lp-text2':  draft.value.variables['--text2'],
  '--lp-accent': draft.value.variables['--accent'],
}))

async function saveTheme() {
  if (!draft.value.name.trim()) return
  saving.value = true
  try {
    if (editingTheme.value) {
      await api.put(`/themes/${editingTheme.value.slug}`, {
        name: draft.value.name,
        description: draft.value.description,
        variables: draft.value.variables,
      })
    } else {
      if (!draft.value.slug.trim()) return
      await api.post('/themes/', {
        slug: draft.value.slug.toLowerCase().replace(/[^a-z0-9-]/g, '-'),
        name: draft.value.name,
        description: draft.value.description,
        variables: draft.value.variables,
      })
    }
    await load()
    closeBuilder()
  } catch (e) {
    console.error(e)
  } finally {
    saving.value = false
  }
}

async function deleteCustomTheme(slug) {
  if (!confirm('Delete this theme?')) return
  try {
    await api.delete(`/themes/${slug}`)
    await load()
  } catch (e) { console.error(e) }
}

// ── CSS var helpers ───────────────────────────────────────────────────────────

function _applyVars(vars) {
  const root = document.documentElement
  for (const [k, v] of Object.entries(vars)) {
    root.style.setProperty(k, v)
  }
}

function _snapshotVars() {
  const style = getComputedStyle(document.documentElement)
  const snap = {}
  for (const k of Object.keys(colorVars)) {
    snap[k] = style.getPropertyValue(k).trim()
  }
  return snap
}

onMounted(load)
onUnmounted(() => {
  if (_previewOriginal) {
    _applyVars(_previewOriginal)
    _previewOriginal = null
  }
})
</script>

<style scoped>
.view-root { padding: 28px 32px; max-width: 1200px; }
.view-header { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 28px; }
.view-title { font-size: 22px; font-weight: 700; color: var(--text); margin-bottom: 4px; }
.view-sub { font-size: 13px; color: var(--text3); }

.loading-state { display: flex; align-items: center; gap: 12px; color: var(--text3); padding: 40px 0; }
.spinner { width: 20px; height: 20px; border: 2px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: spin 0.7s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.section-label { font-size: 11px; font-weight: 700; letter-spacing: 0.08em; color: var(--text3); text-transform: uppercase; margin-bottom: 16px; margin-top: 8px; }
.section-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; margin-top: 32px; }
.section-header .section-label { margin: 0; }

.themes-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 16px; margin-bottom: 8px; }

.theme-card { background: var(--bg2); border: 1px solid var(--border); border-radius: var(--radius); overflow: hidden; transition: border-color 0.2s, transform 0.15s; cursor: default; }
.theme-card:hover { border-color: var(--accent); transform: translateY(-2px); }
.theme-card.active { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent); }
.theme-card.previewing { border-color: var(--accent); }

.theme-preview { height: 110px; display: flex; padding: 10px; gap: 8px; transition: background 0.2s; }
.preview-sidebar { width: 32px; display: flex; flex-direction: column; gap: 4px; }
.preview-logo { height: 16px; border-radius: 4px; margin-bottom: 6px; }
.preview-nav-item { height: 7px; border-radius: 3px; background: rgba(255,255,255,0.08); }
.preview-content { flex: 1; display: flex; gap: 6px; }
.preview-card { flex: 1; border: 1px solid; border-radius: 6px; padding: 7px; display: flex; flex-direction: column; gap: 5px; }
.preview-card-title { height: 5px; border-radius: 3px; }
.preview-stat { height: 14px; border-radius: 4px; width: 60%; }

.theme-info { padding: 14px 16px; }
.theme-name-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px; }
.theme-name { font-size: 14px; font-weight: 600; color: var(--text); }
.badge-active { font-size: 10px; font-weight: 700; background: rgba(99,102,241,0.15); color: var(--accent); border: 1px solid rgba(99,102,241,0.3); border-radius: 10px; padding: 1px 8px; }
.theme-desc { font-size: 12px; color: var(--text3); margin-bottom: 12px; line-height: 1.4; }

.btn-activate { width: 100%; padding: 8px; background: var(--accent); color: #fff; border: none; border-radius: var(--radius-sm); font-size: 12px; font-weight: 600; cursor: pointer; transition: opacity 0.15s; }
.btn-activate:hover { opacity: 0.85; }
.btn-activate:disabled { opacity: 0.5; cursor: not-allowed; }
.active-indicator { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--accent); font-weight: 600; }
.active-indicator svg { width: 14px; height: 14px; fill: currentColor; }

.theme-actions { display: flex; align-items: center; gap: 8px; }
.theme-actions .btn-activate { flex: 1; }

.btn-icon { background: transparent; border: 1px solid var(--border); color: var(--text2); border-radius: var(--radius-sm); width: 30px; height: 30px; display: flex; align-items: center; justify-content: center; cursor: pointer; transition: all 0.15s; flex-shrink: 0; }
.btn-icon svg { width: 14px; height: 14px; fill: currentColor; }
.btn-icon:hover { border-color: var(--accent); color: var(--accent); }
.btn-icon.danger:hover { border-color: var(--danger); color: var(--danger); }
.btn-icon:disabled { opacity: 0.3; cursor: not-allowed; }

.btn-primary { background: var(--accent); color: #fff; border: none; padding: 9px 20px; border-radius: var(--radius-sm); font-size: 13px; font-weight: 600; cursor: pointer; transition: opacity 0.15s; display: flex; align-items: center; gap: 6px; }
.btn-primary:hover { opacity: 0.85; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-secondary { background: transparent; color: var(--text2); border: 1px solid var(--border); padding: 8px 16px; border-radius: var(--radius-sm); font-size: 13px; cursor: pointer; transition: all 0.15s; display: flex; align-items: center; gap: 6px; }
.btn-secondary svg { width: 16px; height: 16px; fill: currentColor; }
.btn-secondary:hover { border-color: var(--accent); color: var(--accent); }

.empty-state { text-align: center; padding: 40px; color: var(--text3); border: 1px dashed var(--border); border-radius: var(--radius); margin-bottom: 20px; }
.empty-state svg { width: 40px; height: 40px; fill: currentColor; margin-bottom: 12px; display: block; margin-inline: auto; }

/* Modal */
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.6); display: flex; align-items: center; justify-content: center; z-index: 200; padding: 20px; }
.modal-lg { background: var(--bg2); border: 1px solid var(--border); border-radius: var(--radius); width: 100%; max-width: 920px; max-height: 90vh; display: flex; flex-direction: column; }
.modal-header { display: flex; align-items: center; justify-content: space-between; padding: 18px 24px; border-bottom: 1px solid var(--border); }
.modal-header h2 { font-size: 16px; font-weight: 700; color: var(--text); }
.modal-footer { padding: 16px 24px; border-top: 1px solid var(--border); display: flex; justify-content: flex-end; gap: 10px; }

.builder-layout { display: grid; grid-template-columns: 320px 1fr; gap: 0; flex: 1; overflow: hidden; }
.builder-controls { padding: 20px 24px; overflow-y: auto; border-right: 1px solid var(--border); }
.builder-preview { padding: 20px 24px; overflow-y: auto; }

.form-group { margin-bottom: 14px; }
.form-group label { display: block; font-size: 11px; font-weight: 600; color: var(--text3); text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 6px; }
.form-input { width: 100%; background: var(--bg3); border: 1px solid var(--border); color: var(--text); border-radius: var(--radius-sm); padding: 8px 10px; font-size: 13px; outline: none; }
.form-input:focus { border-color: var(--accent); }

.color-grid { display: flex; flex-direction: column; gap: 8px; margin-top: 8px; }
.color-row { display: flex; align-items: center; justify-content: space-between; }
.color-label { font-size: 12px; color: var(--text2); flex: 1; }
.color-input-wrap { display: flex; align-items: center; gap: 6px; }
.color-swatch { width: 28px; height: 28px; border: 1px solid var(--border); border-radius: 4px; padding: 2px; background: var(--bg3); cursor: pointer; }
.color-hex { width: 88px; background: var(--bg3); border: 1px solid var(--border); color: var(--text); border-radius: var(--radius-sm); padding: 4px 8px; font-size: 11px; font-family: monospace; outline: none; }
.color-hex:focus { border-color: var(--accent); }

/* Live preview */
.preview-label { font-size: 11px; font-weight: 700; letter-spacing: 0.08em; color: var(--text3); text-transform: uppercase; margin-bottom: 12px; }
.live-preview { border-radius: 10px; overflow: hidden; border: 1px solid var(--border); display: flex; height: 340px; }
.lp-sidebar { width: 110px; padding: 12px 8px; display: flex; flex-direction: column; gap: 4px; border-right: 1px solid var(--lp-border); flex-shrink: 0; }
.lp-logo { font-size: 11px; font-weight: 800; color: #fff; padding: 4px 8px; border-radius: 6px; margin-bottom: 12px; text-align: center; }
.lp-nav { font-size: 11px; padding: 6px 8px; border-radius: 6px; cursor: default; }
.lp-content { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.lp-topbar { padding: 10px 14px; border-bottom: 1px solid; font-size: 12px; font-weight: 600; }
.lp-cards { display: flex; gap: 8px; padding: 12px 12px 8px; }
.lp-card { flex: 1; background: var(--lp-bg2); border: 1px solid var(--lp-border); border-radius: 8px; padding: 10px; }
.lp-card-val { font-size: 20px; font-weight: 800; }
.lp-card-label { font-size: 10px; margin-top: 2px; }
.lp-table { margin: 0 12px; border: 1px solid var(--lp-border); border-radius: 8px; overflow: hidden; font-size: 11px; }
.lp-row { display: grid; grid-template-columns: 1fr 1fr 1fr; padding: 7px 10px; border-bottom: 1px solid var(--lp-border); }
.lp-row:last-child { border-bottom: none; }
.lp-row.header { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; }
</style>
