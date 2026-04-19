<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-brand">
        <div class="brand-glow"></div>
        <GhostWireLogo size="lg" :showText="true" />
        <p>Self-hosted VPN Management</p>
      </div>

      <!-- Step 1: Username + password -->
      <form v-if="!needs2fa" @submit.prevent="submit">
        <div class="form-group">
          <label>Username</label>
          <input v-model="username" type="text" placeholder="admin" autocomplete="username" required />
        </div>
        <div class="form-group">
          <label>Password</label>
          <input v-model="password" type="password" placeholder="••••••••" autocomplete="current-password" required />
        </div>
        <div v-if="error" class="alert alert-danger">{{ error }}</div>
        <button type="submit" class="btn-primary w-full" :disabled="loading">
          <span v-if="loading">Signing in…</span>
          <span v-else>Sign in</span>
        </button>
      </form>

      <!-- Step 2: 2FA code -->
      <form v-else @submit.prevent="submit2fa">
        <div class="twofa-header">
          <div class="twofa-icon">🔐</div>
          <h3>Two-factor verification</h3>
          <p class="text-muted text-sm">
            {{ twoFaMethod === 'totp'
              ? 'Enter the 6-digit code from your authenticator app'
              : 'Enter the code sent to your email' }}
          </p>
        </div>
        <div class="form-group">
          <label>Verification code</label>
          <input
            v-model="twoFaCode"
            type="text"
            inputmode="numeric"
            pattern="[0-9]*"
            placeholder="000000"
            maxlength="6"
            autocomplete="one-time-code"
            class="code-input"
            ref="codeInput"
            required
          />
        </div>
        <div v-if="error" class="alert alert-danger">{{ error }}</div>
        <button type="submit" class="btn-primary w-full" :disabled="loading || twoFaCode.length < 6">
          <span v-if="loading">Verifying…</span>
          <span v-else>Verify</span>
        </button>
        <button type="button" class="btn-ghost w-full mt-2" @click="resetLogin">
          ← Back to login
        </button>
      </form>

      <div class="login-footer">
        <span class="dot" :class="serverOk ? 'dot-green' : 'dot-red'"></span>
        {{ serverOk ? 'Server online' : 'Checking server…' }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import api from '@/utils/api'
import GhostWireLogo from '@/components/GhostWireLogo.vue'

const auth     = useAuthStore()
const router   = useRouter()
const username = ref('')
const password = ref('')
const serverOk = ref(false)
const loading  = ref(false)
const error    = ref('')

// 2FA state
const needs2fa        = ref(false)
const twoFaMethod     = ref('totp')
const twoFaChallenge  = ref('')
const twoFaCode       = ref('')
const codeInput       = ref(null)

onMounted(async () => {
  if (auth.isLoggedIn) {
    router.replace(auth.isAdmin ? '/' : '/portal')
    return
  }
  try {
    const { data } = await api.get('/vpn/ping')
    serverOk.value = data.status === 'ok'
  } catch { serverOk.value = false }
})

async function submit() {
  loading.value = true
  error.value   = ''
  try {
    const form = new FormData()
    form.append('username', username.value)
    form.append('password', password.value)
    const { data } = await api.post('/auth/token', form)

    if (data.needs_2fa) {
      // Server wants 2FA
      needs2fa.value       = true
      twoFaMethod.value    = data.method
      twoFaChallenge.value = data.challenge_token
      await nextTick()
      codeInput.value?.focus()
    } else {
      // Logged in directly
      auth.token = data.access_token
      auth.user  = { username: data.username, full_name: data.full_name, is_admin: data.is_admin }
      localStorage.setItem('ghostwire_token', auth.token)
      localStorage.setItem('ghostwire_user', JSON.stringify(auth.user))
      router.replace(auth.isAdmin ? '/' : '/portal')
    }
  } catch (e) {
    error.value = e.response?.data?.detail || 'Login failed'
  } finally {
    loading.value = false
  }
}

async function submit2fa() {
  loading.value = true
  error.value   = ''
  try {
    const { data } = await api.post('/auth/verify-2fa', {
      challenge_token: twoFaChallenge.value,
      code:            twoFaCode.value.trim(),
    })
    auth.token = data.access_token
    auth.user  = { username: data.username, full_name: data.full_name, is_admin: data.is_admin }
    localStorage.setItem('ghostwire_token', auth.token)
    localStorage.setItem('ghostwire_user', JSON.stringify(auth.user))
    router.replace(auth.isAdmin ? '/' : '/portal')
  } catch (e) {
    error.value = e.response?.data?.detail || 'Invalid code'
    twoFaCode.value = ''
  } finally {
    loading.value = false
  }
}

function resetLogin() {
  needs2fa.value    = false
  twoFaCode.value   = ''
  twoFaChallenge.value = ''
  error.value       = ''
  password.value    = ''
}
</script>

<style scoped>
.login-page { min-height: 100vh; display: flex; align-items: center; justify-content: center; background: var(--bg); padding: 20px; }
.login-card { width: 100%; max-width: 380px; background: var(--bg2); border: 1px solid var(--border); border-radius: 16px; padding: 36px; }
.login-brand { text-align: center; margin-bottom: 28px; position: relative; }
.brand-glow { width: 60px; height: 60px; border-radius: 50%; background: radial-gradient(circle, rgba(99,102,241,0.3) 0%, transparent 70%); margin: 0 auto 12px; }
.login-brand p { font-size: 13px; color: var(--text3); }
.login-footer { margin-top: 20px; display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--text3); justify-content: center; }
button[type=submit] { padding: 10px; font-size: 14px; font-weight: 600; margin-top: 4px; }

/* 2FA step */
.twofa-header { text-align: center; margin-bottom: 20px; }
.twofa-icon { font-size: 32px; margin-bottom: 8px; }
.twofa-header h3 { font-size: 16px; font-weight: 700; color: var(--text); margin-bottom: 6px; }
.code-input {
  text-align: center;
  font-size: 28px;
  font-weight: 700;
  letter-spacing: 10px;
  font-family: monospace;
  color: var(--accent);
}
.mt-2 { margin-top: 8px; }
</style>
