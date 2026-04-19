<template>
  <aside class="sidebar">
    <div class="sidebar-brand">
      <GhostWireLogo size="md" :showText="true" />
    </div>

    <nav class="sidebar-nav">
      <router-link to="/"         class="nav-item" active-class="active" exact>
        <svg viewBox="0 0 24 24"><path d="M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z"/></svg>
        Dashboard
      </router-link>
      <router-link to="/users"    class="nav-item" active-class="active">
        <svg viewBox="0 0 24 24"><path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z"/></svg>
        Users
      </router-link>
      <router-link to="/custom-fields" class="nav-item" active-class="active">
        <svg viewBox="0 0 24 24"><path d="M14 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V8l-6-6zm-1 7V3.5L18.5 9H13zm-2 9H7v-2h4v2zm4-4H7v-2h8v2z"/></svg>
        Custom Fields
      </router-link>
      <router-link to="/dns-blocking" class="nav-item" active-class="active">
        <svg viewBox="0 0 24 24"><path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm-1 14H9V9h2v6zm0-8H9V5h2v2zm4 8h-2V9h2v6zm0-8h-2V5h2v2z"/></svg>
        DNS Blocking
      </router-link>
      <router-link to="/analytics" class="nav-item" active-class="active">
        <svg viewBox="0 0 24 24"><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5 11h-2V8h2v6zm-4 4H8V8h2v10zm8-8h-2v4h2v-4z"/></svg>
        Analytics
      </router-link>
      <router-link to="/nodes" class="nav-item" active-class="active">
        <svg viewBox="0 0 24 24"><path d="M20 3H4v10c0 2.21 1.79 4 4 4h6c2.21 0 4-1.79 4-4v-3h2c1.11 0 2-.89 2-2V5c0-1.11-.89-2-2-2zm0 5h-2V5h2v3zM4 19h16v2H4z"/></svg>
        Server Nodes
      </router-link>
      <router-link to="/bots" class="nav-item" active-class="active">
        <svg viewBox="0 0 24 24"><path d="M20 9V7c0-1.1-.9-2-2-2h-3c0-1.66-1.34-3-3-3S9 3.34 9 5H6c-1.1 0-2 .9-2 2v2c-1.66 0-3 1.34-3 3s1.34 3 3 3v4c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2v-4c1.66 0 3-1.34 3-3s-1.34-3-3-3zM7 8h10v9H7V8zm5 8c.55 0 1-.45 1-1s-.45-1-1-1-1 .45-1 1 .45 1 1 1zm-2-4h4v-2H10v2z"/></svg>
        Bot Integrations
      </router-link>
      <router-link to="/plugins" class="nav-item" active-class="active">
        <svg viewBox="0 0 24 24"><path d="M20.5 11H19V7c0-1.1-.9-2-2-2h-4V3.5A2.5 2.5 0 0010 1 2.5 2.5 0 007.5 3.5V5H3.5A1.5 1.5 0 002 6.5v3.8h1.5c1.56 0 2.82 1.26 2.82 2.82a2.82 2.82 0 01-2.82 2.82H2v3.58A1.5 1.5 0 003.5 21h4v-1.5a2.5 2.5 0 012.5-2.5 2.5 2.5 0 012.5 2.5V21h4c.83 0 1.5-.67 1.5-1.5v-4h1.5a2.5 2.5 0 002.5-2.5 2.5 2.5 0 00-2.5-2.5z"/></svg>
        Plugins
      </router-link>
      <router-link to="/themes" class="nav-item" active-class="active">
        <svg viewBox="0 0 24 24"><path d="M12 3c-4.97 0-9 4.03-9 9s4.03 9 9 9c.83 0 1.5-.67 1.5-1.5 0-.39-.15-.74-.39-1.01-.23-.26-.38-.61-.38-.99 0-.83.67-1.5 1.5-1.5H16c2.76 0 5-2.24 5-5 0-4.42-4.03-8-9-8zm-5.5 9c-.83 0-1.5-.67-1.5-1.5S5.67 9 6.5 9 8 9.67 8 10.5 7.33 12 6.5 12zm3-4C8.67 8 8 7.33 8 6.5S8.67 5 9.5 5s1.5.67 1.5 1.5S10.33 8 9.5 8zm5 0c-.83 0-1.5-.67-1.5-1.5S13.67 5 14.5 5s1.5.67 1.5 1.5S15.33 8 14.5 8zm3 4c-.83 0-1.5-.67-1.5-1.5S16.67 9 17.5 9s1.5.67 1.5 1.5-.67 1.5-1.5 1.5z"/></svg>
        Themes
      </router-link>
      <router-link to="/backup" class="nav-item" active-class="active">
        <svg viewBox="0 0 24 24"><path d="M19 12v7H5v-7H3v7c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2v-7h-2zm-6 .67l2.59-2.58L17 11.5l-5 5-5-5 1.41-1.41L11 12.67V3h2z"/></svg>
        Backup &amp; Restore
      </router-link>

      <div class="nav-divider"></div>
      <router-link to="/sessions" class="nav-item" active-class="active">
        <svg viewBox="0 0 24 24"><path d="M1 9l2 2c4.97-4.97 13.03-4.97 18 0l2-2C16.93 2.93 7.08 2.93 1 9zm8 8l3 3 3-3c-1.65-1.66-4.34-1.66-6 0zm-4-4l2 2c2.76-2.76 7.24-2.76 10 0l2-2C15.14 9.14 8.87 9.14 5 13z"/></svg>
        Active Sessions
      </router-link>
      <router-link to="/logs"     class="nav-item" active-class="active">
        <svg viewBox="0 0 24 24"><path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z"/></svg>
        Audit Logs
      </router-link>

      <div class="nav-divider"></div>

      <router-link to="/config"   class="nav-item" active-class="active">
        <svg viewBox="0 0 24 24"><path d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.09.63-.09.94s.02.64.07.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z"/></svg>
        Configuration
        <span v-if="!smtpConfigured" class="nav-badge-warn" title="SMTP not configured">!</span>
      </router-link>
      <router-link to="/system"   class="nav-item" active-class="active">
        <svg viewBox="0 0 24 24"><path d="M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm-5 11H4v-2h11v2zm3-4H4V9h14v2z"/></svg>
        System
      </router-link>
    </nav>

    <div class="sidebar-footer">
      <div class="user-info">
        <div class="user-avatar">{{ auth.user?.username?.[0]?.toUpperCase() }}</div>
        <div>
          <div class="user-name">{{ auth.user?.username }}</div>
          <div class="user-role">Administrator</div>
        </div>
      </div>
      <button class="logout-btn" @click="logout">Sign out</button>
    </div>
  </aside>
</template>

<script setup>
import GhostWireLogo from '@/components/GhostWireLogo.vue'
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import api from '@/utils/api'

const auth           = useAuthStore()
const router         = useRouter()
const smtpConfigured = ref(true)

onMounted(async () => {
  try {
    const { data } = await api.get('/config/status')
    smtpConfigured.value = data.smtp?.configured === true
  } catch {}
})

function logout() {
  auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.sidebar {
  position: fixed; left: 0; top: 0; bottom: 0; width: 220px;
  background: var(--bg2); border-right: 1px solid var(--border);
  display: flex; flex-direction: column; z-index: 100;
}
.sidebar-brand {
  display: flex; align-items: center; gap: 10px;
  padding: 20px 20px 16px; font-size: 16px; font-weight: 700; color: var(--text);
  border-bottom: 1px solid var(--border);
}
.sidebar-nav { flex: 1; padding: 12px 10px; display: flex; flex-direction: column; gap: 2px; overflow-y: auto; }
.nav-item {
  display: flex; align-items: center; gap: 10px; padding: 9px 12px;
  border-radius: var(--radius-sm); color: var(--text2); font-size: 13px;
  transition: all 0.15s; text-decoration: none;
}
.nav-item svg { width: 16px; height: 16px; fill: currentColor; flex-shrink: 0; }
.nav-item:hover { background: var(--bg3); color: var(--text); }
.nav-item.active { background: rgba(99,102,241,0.15); color: var(--accent); }

.nav-divider { height: 1px; background: var(--border); margin: 6px 4px; }

.nav-badge-warn {
  margin-left: auto; font-size: 10px; font-weight: 800;
  background: rgba(251,191,36,0.2); color: var(--warning);
  border: 1px solid rgba(251,191,36,0.3); border-radius: 10px;
  padding: 0 5px; line-height: 16px;
}

.sidebar-footer { padding: 14px; border-top: 1px solid var(--border); }
.user-info { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.user-avatar { width: 32px; height: 32px; border-radius: 50%; background: var(--accent2); display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 13px; color: #fff; flex-shrink: 0; }
.user-name { font-size: 13px; font-weight: 600; color: var(--text); }
.user-role { font-size: 11px; color: var(--text3); }
.logout-btn { width: 100%; background: transparent; color: var(--text3); border: 1px solid var(--border); padding: 7px; border-radius: var(--radius-sm); font-size: 12px; transition: all 0.15s; cursor: pointer; }
.logout-btn:hover { background: var(--danger); color: #fff; border-color: var(--danger); }
</style>
