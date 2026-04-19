<template>
  <div id="app-root">
    <template v-if="auth.isLoggedIn">
      <AppSidebar v-if="auth.isAdmin" />
      <main :class="auth.isAdmin ? 'main-with-sidebar' : 'main-full'">
        <router-view />
      </main>
    </template>
    <template v-else>
      <router-view />
    </template>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import AppSidebar from '@/components/shared/AppSidebar.vue'
const auth = useAuthStore()

// Bootstrap the active theme from the server (no auth required)
onMounted(async () => {
  try {
    const resp = await fetch('/api/themes/active')
    if (!resp.ok) return
    const data = await resp.json()
    if (data?.variables) {
      const root = document.documentElement
      for (const [k, v] of Object.entries(data.variables)) {
        root.style.setProperty(k, v)
      }
    }
  } catch {
    // Theme load failure is non-fatal — fallback CSS vars remain active
  }
})
</script>

<style scoped>
#app-root { display: flex; min-height: 100vh; }
.main-with-sidebar { flex: 1; margin-left: 220px; padding: 24px; min-height: 100vh; overflow-x: hidden; }
.main-full { flex: 1; }
</style>
