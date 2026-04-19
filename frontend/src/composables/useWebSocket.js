/**
 * GhostWire — useWebSocket composable
 *
 * Provides a reactive WebSocket connection to /api/ws with:
 *  - JWT token injection (query param)
 *  - Automatic reconnect with exponential back-off (max 30 s)
 *  - Heartbeat: replies "pong" to server "ping" frames
 *  - Clean teardown on component unmount
 *
 * Usage:
 *   const { snapshot, lastEvent, connected } = useWebSocket()
 */
import { ref, onUnmounted } from 'vue'

const BASE_DELAY  = 1500   // ms — first reconnect delay
const MAX_DELAY   = 30000  // ms — cap for exponential back-off
const MAX_RETRIES = 20     // give up after this many consecutive failures

export function useWebSocket() {
  const snapshot  = ref(null)   // latest "snapshot" frame
  const lastEvent = ref(null)   // latest "event" frame
  const connected = ref(false)
  const error     = ref(null)

  let ws        = null
  let retries   = 0
  let delay     = BASE_DELAY
  let destroyed = false
  let reconnectTimer = null

  function _wsUrl() {
    const token = localStorage.getItem('ghostwire_token') || ''
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    return `${proto}://${location.host}/api/ws?token=${encodeURIComponent(token)}`
  }

  function connect() {
    if (destroyed) return
    if (!localStorage.getItem('ghostwire_token')) return   // not logged in

    try {
      ws = new WebSocket(_wsUrl())
    } catch (e) {
      scheduleReconnect()
      return
    }

    ws.onopen = () => {
      connected.value = true
      error.value     = null
      retries = 0
      delay   = BASE_DELAY
    }

    ws.onmessage = ({ data }) => {
      let msg
      try { msg = JSON.parse(data) } catch { return }

      switch (msg.type) {
        case 'snapshot':
          snapshot.value = msg
          break
        case 'event':
          lastEvent.value = msg
          break
        case 'ping':
          ws?.readyState === WebSocket.OPEN && ws.send('pong')
          break
        case 'error':
          error.value = msg.message || 'WebSocket error'
          // Server will close after an error frame — don't force reconnect on auth errors
          if (msg.message?.toLowerCase().includes('token') ||
              msg.message?.toLowerCase().includes('user')) {
            destroyed = true   // auth error — no point reconnecting
          }
          break
      }
    }

    ws.onerror = () => {
      // onclose will fire right after, handle retry there
    }

    ws.onclose = (evt) => {
      connected.value = false
      if (!destroyed) {
        scheduleReconnect()
      }
    }
  }

  function scheduleReconnect() {
    if (destroyed || retries >= MAX_RETRIES) return
    retries++
    reconnectTimer = setTimeout(() => {
      if (!destroyed) connect()
    }, delay)
    delay = Math.min(delay * 1.5, MAX_DELAY)
  }

  function disconnect() {
    destroyed = true
    clearTimeout(reconnectTimer)
    if (ws) {
      ws.onclose = null   // prevent reconnect loop
      ws.close()
      ws = null
    }
    connected.value = false
  }

  // Start immediately
  connect()

  // Clean up when the component using this composable is destroyed
  onUnmounted(disconnect)

  return { snapshot, lastEvent, connected, error, disconnect }
}
