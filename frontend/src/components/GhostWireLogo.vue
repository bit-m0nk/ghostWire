<template>
  <div class="gw-logo" :class="size">
    <svg :width="dims.w" :height="dims.h" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
      <!-- Ghost body -->
      <path d="M24 4C15.163 4 8 11.163 8 20V38L13 34L18 38L24 34L30 38L35 34L40 38V20C40 11.163 32.837 4 24 4Z"
            fill="url(#ghostBody)" opacity="0.18"/>
      <path d="M24 4C15.163 4 8 11.163 8 20V38L13 34L18 38L24 34L30 38L35 34L40 38V20C40 11.163 32.837 4 24 4Z"
            stroke="url(#ghostStroke)" stroke-width="1.5" stroke-linejoin="round" fill="none"/>
      <!-- Eyes -->
      <circle cx="19" cy="20" r="2.5" fill="url(#eyeGrad)"/>
      <circle cx="29" cy="20" r="2.5" fill="url(#eyeGrad)"/>
      <!-- Network lines (wire motif) -->
      <line x1="14" y1="28" x2="22" y2="32" stroke="url(#wireGrad)" stroke-width="1" opacity="0.6"/>
      <line x1="34" y1="28" x2="26" y2="32" stroke="url(#wireGrad)" stroke-width="1" opacity="0.6"/>
      <circle cx="14" cy="28" r="1.5" fill="url(#nodeDot)" opacity="0.8"/>
      <circle cx="34" cy="28" r="1.5" fill="url(#nodeDot)" opacity="0.8"/>
      <circle cx="24" cy="32" r="1.5" fill="url(#nodeDot)"/>
      <defs>
        <linearGradient id="ghostBody" x1="8" y1="4" x2="40" y2="44" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stop-color="#6366f1"/>
          <stop offset="100%" stop-color="#8b5cf6"/>
        </linearGradient>
        <linearGradient id="ghostStroke" x1="8" y1="4" x2="40" y2="44" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stop-color="#818cf8"/>
          <stop offset="100%" stop-color="#a78bfa"/>
        </linearGradient>
        <linearGradient id="eyeGrad" x1="0" y1="0" x2="48" y2="48" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stop-color="#c7d2fe"/>
          <stop offset="100%" stop-color="#ddd6fe"/>
        </linearGradient>
        <linearGradient id="wireGrad" x1="8" y1="28" x2="40" y2="32" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stop-color="#6366f1"/>
          <stop offset="100%" stop-color="#8b5cf6"/>
        </linearGradient>
        <linearGradient id="nodeDot" x1="0" y1="0" x2="48" y2="48" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stop-color="#818cf8"/>
          <stop offset="100%" stop-color="#a78bfa"/>
        </linearGradient>
      </defs>
    </svg>
    <div class="logo-text" v-if="showText">
      <span class="logo-ghost">Ghost</span><span class="logo-wire">Wire</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({
  size:     { type: String, default: 'md' },   // sm | md | lg
  showText: { type: Boolean, default: true },
})
const dims = computed(() => ({
  sm: { w: 28, h: 28 },
  md: { w: 36, h: 36 },
  lg: { w: 56, h: 56 },
}[props.size] || { w: 36, h: 36 }))
</script>

<style scoped>
.gw-logo {
  display: flex;
  align-items: center;
  gap: 8px;
  user-select: none;
}
.logo-text {
  font-weight: 800;
  letter-spacing: -0.5px;
  line-height: 1;
}
.logo-ghost { color: #c7d2fe; }
.logo-wire  { color: #a78bfa; }
.gw-logo.sm .logo-text { font-size: 15px; }
.gw-logo.md .logo-text { font-size: 18px; }
.gw-logo.lg .logo-text { font-size: 26px; }
</style>
