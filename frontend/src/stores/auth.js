import { defineStore } from 'pinia'
import api from '@/utils/api'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token:   localStorage.getItem('ghostwire_token') || null,
    user:    JSON.parse(localStorage.getItem('ghostwire_user') || 'null'),
    loading: false,
    error:   null,
  }),

  getters: {
    isLoggedIn: s => !!s.token,
    isAdmin:    s => s.user?.is_admin === true,
  },

  actions: {
    async login(username, password) {
      this.loading = true
      this.error   = null
      try {
        const form = new FormData()
        form.append('username', username)
        form.append('password', password)
        const { data } = await api.post('/auth/token', form)
        this.token = data.access_token
        this.user  = {
          username:  data.username,
          full_name: data.full_name,
          is_admin:  data.is_admin,
        }
        localStorage.setItem('ghostwire_token', this.token)
        localStorage.setItem('ghostwire_user', JSON.stringify(this.user))
        return true
      } catch (e) {
        this.error = e.response?.data?.detail || 'Login failed'
        return false
      } finally {
        this.loading = false
      }
    },

    logout() {
      this.token = null
      this.user  = null
      localStorage.removeItem('ghostwire_token')
      localStorage.removeItem('ghostwire_user')
    },
  }
})
