import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/LoginView.vue'),
    meta: { public: true }
  },
  {
    path: '/',
    name: 'Dashboard',
    component: () => import('@/views/admin/DashboardView.vue'),
    meta: { admin: true }
  },
  {
    path: '/users',
    name: 'Users',
    component: () => import('@/views/admin/UsersView.vue'),
    meta: { admin: true }
  },
  {
    path: '/sessions',
    name: 'Sessions',
    component: () => import('@/views/admin/SessionsView.vue'),
    meta: { admin: true }
  },
  {
    path: '/logs',
    name: 'Logs',
    component: () => import('@/views/admin/LogsView.vue'),
    meta: { admin: true }
  },
  {
    path: '/system',
    name: 'System',
    component: () => import('@/views/admin/SystemView.vue'),
    meta: { admin: true }
  },
  {
    path: '/config',
    name: 'Config',
    component: () => import('@/views/admin/ConfigView.vue'),
    meta: { admin: true }
  },
  {
    path: '/custom-fields',
    name: 'CustomFields',
    component: () => import('@/views/admin/CustomFieldsView.vue'),
    meta: { admin: true }
  },
  // Phase 3
  {
    path: '/dns-blocking',
    name: 'DnsBlocking',
    component: () => import('@/views/admin/DnsBlockingView.vue'),
    meta: { admin: true }
  },
  {
    path: '/analytics',
    name: 'Analytics',
    component: () => import('@/views/admin/AnalyticsView.vue'),
    meta: { admin: true }
  },
  // Phase 4
  {
    path: '/nodes',
    name: 'Nodes',
    component: () => import('@/views/admin/NodesView.vue'),
    meta: { admin: true }
  },
  {
    path: '/bots',
    name: 'Bots',
    component: () => import('@/views/admin/BotsView.vue'),
    meta: { admin: true }
  },
  // Phase 5
  {
    path: '/plugins',
    name: 'Plugins',
    component: () => import('@/views/admin/PluginsView.vue'),
    meta: { admin: true }
  },
  {
    path: '/themes',
    name: 'Themes',
    component: () => import('@/views/admin/ThemesView.vue'),
    meta: { admin: true }
  },
  {
    path: '/backup',
    name: 'Backup',
    component: () => import('@/views/admin/BackupView.vue'),
    meta: { admin: true }
  },
  {
    path: '/portal',
    name: 'Portal',
    component: () => import('@/views/user/PortalView.vue'),
    meta: { auth: true }
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/NotFoundView.vue'),
    meta: { public: true }
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  const auth = useAuthStore()
  if (to.meta.public) return next()
  if (!auth.isLoggedIn) return next({ name: 'Login', replace: true })
  if (to.meta.admin && !auth.isAdmin) return next({ name: 'Portal', replace: true })
  next()
})

export default router
