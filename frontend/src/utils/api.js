import axios from 'axios'
import router from '@/router'

const api = axios.create({
  baseURL: '/api',
  timeout: 15000,
})

// Attach JWT token to every request
api.interceptors.request.use(config => {
  const token = localStorage.getItem('ghostwire_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Handle 401 — clear session and navigate to login via Vue Router (no full reload)
api.interceptors.response.use(
  res => res,
  err => {
    if (err.response?.status === 401) {
      localStorage.removeItem('ghostwire_token')
      localStorage.removeItem('ghostwire_user')
      router.replace('/login').catch(() => {})
    }
    return Promise.reject(err)
  }
)

export default api
