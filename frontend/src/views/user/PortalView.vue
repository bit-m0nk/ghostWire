<template>
  <div class="gw-portal">

    <!-- ── Sidebar ───────────────────────────────────────────────── -->
    <aside class="gw-sidebar" :class="{ collapsed: sidebarCollapsed }">
      <div class="sidebar-top">
        <div class="sidebar-brand">
          <span class="brand-pulse"></span>
          <span class="brand-name" v-show="!sidebarCollapsed">{{ brand }}</span>
        </div>
        <button class="collapse-btn" @click="sidebarCollapsed = !sidebarCollapsed">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path v-if="!sidebarCollapsed" d="M11 19l-7-7 7-7M18 19l-7-7 7-7"/>
            <path v-else d="M13 5l7 7-7 7M6 5l7 7-7 7"/>
          </svg>
        </button>
      </div>

      <nav class="sidebar-nav">
        <button v-for="item in navItems" :key="item.id"
          class="nav-item" :class="{ active: activeSection === item.id }"
          @click="activeSection = item.id"
          :title="sidebarCollapsed ? item.label : ''">
          <span class="nav-icon" v-html="item.icon"></span>
          <span class="nav-label" v-show="!sidebarCollapsed">{{ item.label }}</span>
          <span v-if="item.badge && !sidebarCollapsed" class="nav-badge">{{ item.badge }}</span>
        </button>
      </nav>

      <div class="sidebar-footer" v-show="!sidebarCollapsed">
        <div class="user-chip">
          <div class="user-avatar">{{ userInitial }}</div>
          <div class="user-meta">
            <div class="user-name">{{ auth.user?.username }}</div>
            <div class="user-role">VPN User</div>
          </div>
          <button class="signout-btn" @click="logout" title="Sign out">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="15" height="15">
              <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9"/>
            </svg>
          </button>
        </div>
      </div>
    </aside>

    <!-- ── Main ──────────────────────────────────────────────────── -->
    <main class="gw-main">

      <div class="topbar">
        <div class="topbar-left">
          <div class="page-title">{{ currentNav?.label }}</div>
          <div class="page-sub">{{ currentNav?.sub }}</div>
        </div>
        <div class="topbar-right">
          <div class="server-pill" v-if="serverInfo">
            <span class="spill-dot dot-green"></span>
            <code>{{ serverInfo.server }}</code>
          </div>
          <button class="mobile-menu-btn" @click="sidebarCollapsed = !sidebarCollapsed">☰</button>
        </div>
      </div>

      <!-- OVERVIEW ─────────────────────────────────────────────── -->
      <section v-show="activeSection === 'overview'" class="section-body">

        <div v-if="profileUpdateRequired" class="update-banner">
          <span class="ub-icon">⚠</span>
          <div class="ub-body">
            <strong>Re-download your VPN profile</strong>
            <p>Your server IP changed — existing profiles will fail to connect.</p>
          </div>
          <button class="ub-dismiss" @click="dismissProfileUpdateBanner">✕</button>
        </div>

        <div class="stats-row">
          <div class="stat-tile">
            <div class="st-icon st-blue"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15.3 15.3 0 010 20"/></svg></div>
            <div class="st-data"><div class="st-val">{{ mySessions.length }}</div><div class="st-lbl">Active Sessions</div></div>
          </div>
          <div class="stat-tile">
            <div class="st-icon st-green"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg></div>
            <div class="st-data"><div class="st-val">{{ fmtBytes(totalBytesIn) }}</div><div class="st-lbl">Data In</div></div>
          </div>
          <div class="stat-tile">
            <div class="st-icon st-purple"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 18 13.5 8.5 8.5 13.5 1 6"/><polyline points="17 18 23 18 23 12"/></svg></div>
            <div class="st-data"><div class="st-val">{{ fmtBytes(totalBytesOut) }}</div><div class="st-lbl">Data Out</div></div>
          </div>
          <div class="stat-tile">
            <div class="st-icon" :class="twoFAEnabled ? 'st-green' : 'st-warn'"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0110 0v4"/></svg></div>
            <div class="st-data">
              <div class="st-val" :style="{color: twoFAEnabled ? 'var(--success)' : 'var(--warning)'}">{{ twoFAEnabled ? 'On' : 'Off' }}</div>
              <div class="st-lbl">2FA</div>
            </div>
          </div>
        </div>

        <div class="quick-actions">
          <div class="qa-title">Quick Actions</div>
          <div class="qa-grid">
            <button class="qa-card" @click="activeSection='connect'"><span class="qa-icon">⬇</span><span class="qa-lbl">Download Config</span></button>
            <button class="qa-card" @click="activeSection='security'"><span class="qa-icon">🔐</span><span class="qa-lbl">Setup 2FA</span></button>
            <button class="qa-card" @click="activeSection='sessions'"><span class="qa-icon">📡</span><span class="qa-lbl">My Sessions</span></button>
            <button class="qa-card" @click="activeSection='dns'"><span class="qa-icon">🛡</span><span class="qa-lbl">DNS Blocking</span></button>
          </div>
        </div>

        <div class="card mt-4" v-if="serverInfo">
          <div class="card-title">Server Details</div>
          <div class="server-info-grid">
            <div class="si-row"><span class="si-key">Hostname</span><code class="si-val">{{ serverInfo.server }}</code></div>
            <div class="si-row"><span class="si-key">Protocol</span><code class="si-val">IKEv2 / IPSec</code></div>
            <div class="si-row"><span class="si-key">DNS</span><code class="si-val">1.1.1.1, 8.8.8.8</code></div>
            <div class="si-row"><span class="si-key">Public IP</span><code class="si-val">{{ serverInfo.current_ip }}</code></div>
            <div class="si-row"><span class="si-key">Brand</span><code class="si-val">{{ serverInfo.brand }}</code></div>
          </div>
        </div>

        <div class="card mt-3" v-if="fleetNodes.length > 1">
          <div class="card-title">Available Servers</div>
          <div class="fleet-list">
            <div v-for="node in fleetNodes" :key="node.id" class="fleet-row">
              <span class="fleet-flag">{{ node.flag }}</span>
              <div class="fleet-info"><div class="fleet-name">{{ node.name }}</div><div class="fleet-loc">{{ node.location }}</div></div>
              <div class="fleet-right">
                <span v-if="node.latency_ms" class="fleet-ping">{{ node.latency_ms }}ms</span>
                <span class="fleet-badge online">Online</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- CONNECT ──────────────────────────────────────────────── -->
      <section v-show="activeSection === 'connect'" class="section-body">

        <div class="card" v-if="!configsLoaded">
          <div class="card-title">🔑 Unlock VPN Configs</div>
          <p class="hint-text mb-3">Enter your <strong>VPN password</strong> (different from panel login) to reveal connection profiles.</p>
          <div class="unlock-row">
            <div class="form-group" style="flex:1;margin:0">
              <label>VPN Username</label>
              <div class="static-val">{{ vpnUsername || '(contact admin)' }}</div>
            </div>
            <div class="form-group" style="flex:2;margin:0">
              <label>VPN Password</label>
              <div class="pw-wrap">
                <input v-model="vpnPassword" :type="showPw?'text':'password'" placeholder="Enter VPN password" @keyup.enter="loadConfigs"/>
                <button class="pw-eye" @click="showPw=!showPw">{{ showPw?'🙈':'👁' }}</button>
              </div>
            </div>
            <button class="btn-primary" style="align-self:flex-end;white-space:nowrap" @click="loadConfigs" :disabled="!vpnPassword||loadingConfigs">
              {{ loadingConfigs ? 'Loading…' : 'Load Configs' }}
            </button>
          </div>
          <div v-if="credError" class="alert alert-danger mt-3">{{ credError }}</div>
        </div>

        <div v-if="configsLoaded">
          <div class="os-tabs">
            <button v-for="os in osList" :key="os.key" class="os-tab" :class="{active:activeOs===os.key}" @click="activeOs=os.key">
              <span v-html="os.icon" class="ostab-icon"></span>{{ os.label }}
            </button>
          </div>

          <!-- iOS -->
          <div v-if="activeOs==='ios'" class="method-grid">
            <div class="method-card recommended">
              <div class="method-badge">Easiest</div>
              <div class="method-header"><div class="micon" style="background:linear-gradient(135deg,#007AFF,#5856D6)"><svg viewBox="0 0 24 24" fill="white"><path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.8-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M13 3.5c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11z"/></svg></div><div><div class="mt">.mobileconfig Profile</div><div class="ms">IKEv2 + IPSec fallback, CA bundled</div></div></div>
              <div class="steps"><p>1. Download on iPhone via <b>Safari</b></p><p>2. Settings → General → VPN &amp; Device Management → Install</p><p>3. Settings → VPN → try <b>"{{ brand }} IKEv2"</b> first, then IPSec</p></div>
              <button class="btn-primary w-full mt-2" @click="dl('mobileconfig')" :disabled="dlBusy==='mobileconfig'">⬇ {{ dlBusy==='mobileconfig'?'Downloading…':'Download .mobileconfig' }}</button>
              <div class="alert alert-warning text-sm mt-2">⚠ Must use <b>Safari</b> on iPhone — other browsers won't trigger the installer.</div>
            </div>
            <div class="method-card">
              <div class="method-header"><div class="micon" style="background:linear-gradient(135deg,#FF9500,#FF6B00)"><svg viewBox="0 0 24 24" fill="white"><path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4z"/></svg></div><div><div class="mt">IPSec XAuth — No cert</div><div class="ms">Settings → VPN → Type: IPSec</div></div></div>
              <div class="alert alert-success text-sm mt-2 mb-2">✓ No certificate needed</div>
              <div class="ftable" v-if="manual?.ios_ipsec"><div class="fr" v-for="(v,k) in manual.ios_ipsec.fields" :key="k"><span>{{k}}</span><code>{{v}}</code></div></div>
              <div class="alert alert-info text-sm mt-2">Settings → General → VPN → Add VPN → <b>Type: IPSec</b><br>⚠ Leave <b>Group Name blank</b></div>
            </div>
            <div class="method-card">
              <div class="method-header"><div class="micon" style="background:linear-gradient(135deg,#34C759,#248A3D)"><svg viewBox="0 0 24 24" fill="white"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg></div><div><div class="mt">IKEv2 — Manual with CA cert</div><div class="ms">Most secure</div></div></div>
              <div class="alert alert-warning text-sm mt-2 mb-2">① Download CA cert → tap on iPhone → Settings → Install → Trust</div>
              <div class="flex gap-1 flex-wrap mb-2"><a href="/api/profiles/ca.der" class="btn-ghost btn-sm" download>⬇ .der</a><a href="/api/profiles/ca.crt" class="btn-ghost btn-sm" download>⬇ .crt</a><a href="/api/profiles/ca.pem" class="btn-ghost btn-sm" download>⬇ .pem</a></div>
              <div class="ftable" v-if="manual?.ios_ikev2"><div class="fr" v-for="(v,k) in manual.ios_ikev2.fields" :key="k"><span>{{k}}</span><code>{{v}}</code></div></div>
            </div>
          </div>

          <!-- Android -->
          <div v-if="activeOs==='android'" class="method-grid">
            <div class="method-card recommended">
              <div class="method-badge">Easiest</div>
              <div class="method-header"><div class="micon" style="background:linear-gradient(135deg,#3DDC84,#1A7A3C)"><svg viewBox="0 0 24 24" fill="white"><path d="M17.523 15.341a5.023 5.023 0 01-4.996 4.65 5.023 5.023 0 01-4.997-4.65H2.5l1.518-8.5h15.964l1.518 8.5h-4.977zM8.5 3L6 6h12l-2.5-3h-7zm7.5 8a1 1 0 100-2 1 1 0 000 2zm-8 0a1 1 0 100-2 1 1 0 000 2z"/></svg></div><div><div class="mt">strongSwan App (.sswan)</div><div class="ms">Play Store — one-tap import</div></div></div>
              <div class="steps"><p>1. Install <b>strongSwan VPN Client</b> from Play Store</p><p>2. Download .sswan → tap → Open with strongSwan</p><p>3. Tap connection → enter VPN password</p></div>
              <div class="flex gap-2 flex-wrap mt-2">
                <button class="btn-primary flex-1" @click="dl('sswan')" :disabled="dlBusy==='sswan'">⬇ {{ dlBusy==='sswan'?'Downloading…':'.sswan (cert)' }}</button>
                <button class="btn-ghost flex-1" @click="dl('sswan-xauth')" :disabled="dlBusy==='sswan-xauth'">⬇ {{ dlBusy==='sswan-xauth'?'Downloading…':'.sswan (XAuth)' }}</button>
              </div>
            </div>
            <div class="method-card">
              <div class="method-header"><div class="micon" style="background:linear-gradient(135deg,#FF5722,#E64A19)"><svg viewBox="0 0 24 24" fill="white"><path d="M12.65 10C11.83 7.67 9.61 6 7 6c-3.31 0-6 2.69-6 6s2.69 6 6 6c2.61 0 4.83-1.67 5.65-4H17v4h4v-4h2v-4H12.65zM7 14c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2z"/></svg></div><div><div class="mt">Built-in IKEv2/IPSec PSK</div><div class="ms">No cert needed</div></div></div>
              <div class="alert alert-success text-sm mt-2 mb-2">✓ No certificate needed</div>
              <div class="ftable" v-if="manual?.android_psk"><div class="fr" v-for="(v,k) in manual.android_psk.fields" :key="k"><span>{{k}}</span><code>{{v}}</code></div></div>
            </div>
            <div class="method-card">
              <div class="method-header"><div class="micon" style="background:linear-gradient(135deg,#607D8B,#37474F)"><svg viewBox="0 0 24 24" fill="white"><path d="M1 9l2 2c4.97-4.97 13.03-4.97 18 0l2-2C16.93 2.93 7.08 2.93 1 9zm8 8l3 3 3-3c-1.65-1.66-4.34-1.66-6 0zm-4-4l2 2c2.76-2.76 7.24-2.76 10 0l2-2C15.14 9.14 8.87 9.14 5 13z"/></svg></div><div><div class="mt">Built-in L2TP/IPSec PSK</div><div class="ms">Classic · all Android</div></div></div>
              <div class="ftable" v-if="manual?.android_l2tp_psk"><div class="fr" v-for="(v,k) in manual.android_l2tp_psk.fields" :key="k"><span>{{k}}</span><code>{{v}}</code></div></div>
            </div>
          </div>

          <!-- Windows -->
          <div v-if="activeOs==='windows'" class="method-grid">
            <div class="method-card recommended">
              <div class="method-badge">Recommended</div>
              <div class="method-header"><div class="micon" style="background:linear-gradient(135deg,#0078D4,#00BCF2)"><svg viewBox="0 0 24 24" fill="white"><path d="M3 12V6.75l6-1.32v6.57H3zm17 0V5.25L11 3.5V12h9zm-9 .75H3v5.93l6 1.07v-7zm9 0h-8V20.5l8-1.43V12.75z"/></svg></div><div><div class="mt">PowerShell auto-install</div><div class="ms">Installs CA cert + VPN in one step</div></div></div>
              <div class="steps"><p>1. Download script below</p><p>2. Right-click → <b>Run with PowerShell</b> (as Administrator)</p><p>3. If prompted "cannot be loaded" — open PowerShell as Admin and run: <code class="ic">Set-ExecutionPolicy RemoteSigned</code></p><p>4. Settings → Network → VPN → connect</p></div>
              <button class="btn-primary w-full mt-2" @click="dl('ps1')" :disabled="dlBusy==='ps1'">⬇ {{ dlBusy==='ps1'?'Downloading…':'PowerShell script (.ps1)' }}</button>
            </div>
            <div class="method-card">
              <div class="method-header"><div class="micon" style="background:linear-gradient(135deg,#5C2D91,#7B2FBE)"><svg viewBox="0 0 24 24" fill="white"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 3c1.66 0 3 1.34 3 3s-1.34 3-3 3-3-1.34-3-3 1.34-3 3-3zm0 14.2c-2.5 0-4.71-1.28-6-3.22.03-1.99 4-3.08 6-3.08 1.99 0 5.97 1.09 6 3.08-1.29 1.94-3.5 3.22-6 3.22z"/></svg></div><div><div class="mt">Manual IKEv2</div><div class="ms">Settings → Network &amp; Internet → VPN</div></div></div>
              <div class="flex gap-1 flex-wrap mb-2 mt-2"><a href="/api/profiles/ca.der" class="btn-ghost btn-sm" download>⬇ .der</a><a href="/api/profiles/ca.crt" class="btn-ghost btn-sm" download>⬇ .crt</a></div>
              <div class="ftable" v-if="manual?.windows"><div class="fr" v-for="(v,k) in manual.windows.fields" :key="k"><span>{{k}}</span><code>{{v}}</code></div></div>
              <button class="btn-ghost btn-sm w-full mt-2" @click="dl('pbk')" :disabled="dlBusy==='pbk'">⬇ .pbk phonebook</button>
            </div>
          </div>

          <!-- macOS -->
          <div v-if="activeOs==='macos'" class="method-grid">
            <div class="method-card recommended">
              <div class="method-badge">Recommended</div>
              <div class="method-header"><div class="micon" style="background:linear-gradient(135deg,#555,#222)"><svg viewBox="0 0 24 24" fill="white"><path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.8-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M13 3.5c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11z"/></svg></div><div><div class="mt">.mobileconfig Profile</div><div class="ms">macOS 10.11+</div></div></div>
              <div class="steps"><p>1. Download → double-click</p><p>2. System Preferences → Profiles → Install</p><p>3. System Preferences → Network → connect VPN</p></div>
              <button class="btn-primary w-full mt-2" @click="dl('mobileconfig')" :disabled="dlBusy==='mobileconfig'">⬇ {{ dlBusy==='mobileconfig'?'Downloading…':'.mobileconfig' }}</button>
            </div>
            <div class="method-card">
              <div class="method-header"><div class="micon" style="background:linear-gradient(135deg,#6e6e73,#3a3a3c)"><svg viewBox="0 0 24 24" fill="white"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 3c1.66 0 3 1.34 3 3s-1.34 3-3 3-3-1.34-3-3 1.34-3 3-3zm0 14.2c-2.5 0-4.71-1.28-6-3.22.03-1.99 4-3.08 6-3.08 1.99 0 5.97 1.09 6 3.08-1.29 1.94-3.5 3.22-6 3.22z"/></svg></div><div><div class="mt">Manual IKEv2</div><div class="ms">Keychain → import CA → trust → add VPN</div></div></div>
              <a href="/api/profiles/ca.crt" class="btn-ghost btn-sm w-full mb-2 mt-2" download>⬇ CA cert (.crt)</a>
              <div class="ftable" v-if="manual?.ios_ikev2"><div class="fr" v-for="(v,k) in manual.ios_ikev2.fields" :key="k"><span>{{k}}</span><code>{{v}}</code></div></div>
            </div>
          </div>

          <!-- Linux -->
          <div v-if="activeOs==='linux'" class="method-grid">
            <div class="method-card recommended">
              <div class="method-badge">Recommended</div>
              <div class="method-header"><div class="micon" style="background:linear-gradient(135deg,#E95420,#C34113)"><svg viewBox="0 0 24 24" fill="white"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/></svg></div><div><div class="mt">NetworkManager (.nmconnection)</div><div class="ms">Ubuntu, Fedora, Debian, etc.</div></div></div>
              <div class="steps"><p>1. Download profile below</p><p>2. <code class="ic">sudo nmcli connection import type vpn file {{ brand }}_VPN.nmconnection</code></p><p>3. <code class="ic">sudo nmcli connection up '{{ brand }} VPN'</code></p></div>
              <button class="btn-primary w-full mt-2" @click="dl('nmconnection')" :disabled="dlBusy==='nmconnection'">⬇ {{ dlBusy==='nmconnection'?'Downloading…':'.nmconnection' }}</button>
            </div>
            <div class="method-card" v-if="manual?.linux">
              <div class="method-header"><div class="micon" style="background:linear-gradient(135deg,#2196F3,#0D47A1)"><svg viewBox="0 0 24 24" fill="white"><path d="M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm-8 9L4 8h16l-8 5z"/></svg></div><div><div class="mt">Terminal commands</div><div class="ms">Any Linux distro</div></div></div>
              <div class="code-block mt-2"><div v-for="cmd in manual.linux.commands" :key="cmd" class="code-line">{{ cmd }}</div></div>
            </div>
          </div>

          <div v-if="dlError" class="alert alert-danger mt-3">{{ dlError }}</div>
        </div>
      </section>

      <!-- SESSIONS ─────────────────────────────────────────────── -->
      <section v-show="activeSection === 'sessions'" class="section-body">
        <div class="card">
          <div class="card-title" style="justify-content:space-between">
            <span>Active Sessions</span>
            <button class="btn-ghost btn-sm" @click="refreshSessions">↻ Refresh</button>
          </div>
          <div v-if="mySessions.length === 0" class="empty-state">
            <div class="es-icon">📡</div>
            <div class="es-text">No active sessions</div>
            <div class="es-sub">Connect your device to see sessions here</div>
          </div>
          <div v-else class="sessions-list">
            <div v-for="sess in mySessions" :key="sess.id" class="session-card">
              <div class="sess-dot"></div>
              <div class="sess-main">
                <div class="sess-ip">{{ sess.client_ip }}</div>
                <div class="sess-meta">
                  <span>{{ sess.country_name || sess.country || 'Unknown' }}</span>
                  <span class="sep">·</span>
                  <span>VIP: <code>{{ sess.virtual_ip }}</code></span>
                  <span class="sep">·</span>
                  <span>{{ fmtAgo(sess.connected_at) }}</span>
                </div>
              </div>
              <div class="sess-bytes">
                <div class="sb-row"><span class="sb-in">↓</span><span>{{ fmtBytes(parseInt(sess.bytes_in, 10) || 0) }}</span></div>
                <div class="sb-row"><span class="sb-out">↑</span><span>{{ fmtBytes(parseInt(sess.bytes_out, 10) || 0) }}</span></div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- SECURITY ─────────────────────────────────────────────── -->
      <section v-show="activeSection === 'security'" class="section-body">
        <div class="security-grid">

          <div class="card">
            <div class="card-title">Two-Factor Authentication</div>
            <div class="twofa-bar" :class="twoFAStatus.totp_enabled ? 'tfa-on' : 'tfa-off'">
              <span class="tfa-dot"></span>
              2FA is <strong>&nbsp;{{ twoFAStatus.totp_enabled ? 'enabled' : 'disabled' }}</strong>
            </div>

            <div v-if="twoFAStatus.totp_enabled" class="mt-3">
              <p class="hint-text mb-3">Enter your authenticator code + panel password to disable 2FA.</p>
              <div class="form-group"><label>Current panel password</label><input v-model="disable.password" type="password"/></div>
              <div class="form-group"><label>Authenticator code</label><input v-model="disable.code" type="text" inputmode="numeric" maxlength="6" placeholder="000000" class="code-input"/></div>
              <div v-if="disableError" class="alert alert-danger">{{ disableError }}</div>
              <div v-if="disableOk" class="alert alert-success">{{ disableOk }}</div>
              <button class="btn-danger" @click="doDisable" :disabled="disabling">{{ disabling ? 'Disabling…' : 'Disable 2FA' }}</button>
            </div>

            <div v-else-if="!qrVisible" class="mt-3">
              <p class="hint-text mb-3">Protect your account with Google Authenticator, Authy, 1Password, or Bitwarden.</p>
              <button class="btn-primary" @click="startSetup" :disabled="setupLoading">{{ setupLoading ? 'Loading…' : 'Set up 2FA' }}</button>
              <div v-if="setupError" class="alert alert-danger mt-2">{{ setupError }}</div>
            </div>

            <div v-else class="mt-3">
              <p class="hint-text mb-3">Scan QR code with your authenticator app, then enter the 6-digit code to activate.</p>
              <div class="qr-wrap" v-if="qrSvg"><div class="qr-inner" v-html="qrSvg"></div></div>
              <div v-else-if="setupLoading" class="qr-placeholder"><div class="qr-spinner"></div><span class="hint-text">Loading…</span></div>
              <div v-else class="qr-placeholder"><span class="hint-text">⚠ QR failed — use manual key below</span></div>

              <details class="manual-secret mt-2">
                <summary class="hint-text" style="cursor:pointer;user-select:none">Can't scan? Enter key manually</summary>
                <div class="secret-box mt-2">
                  <code class="grouped-secret">{{ groupedSecret }}</code>
                  <button class="btn-ghost btn-sm" @click="copySecret">📋</button>
                </div>
                <div class="hint-text mt-1">Type: Time-based (TOTP) · Period: 30s · Digits: 6</div>
              </details>

              <div class="form-group mt-3"><label>Panel password (re-confirm)</label><input v-model="confirm.password" type="password"/></div>
              <div class="form-group"><label>6-digit code from app</label><input v-model="confirm.code" type="text" inputmode="numeric" maxlength="6" placeholder="000000" class="code-input"/></div>
              <div v-if="confirmError" class="alert alert-danger">{{ confirmError }}</div>
              <div v-if="confirmOk" class="alert alert-success">{{ confirmOk }}</div>
              <div class="flex gap-2">
                <button class="btn-primary" @click="doConfirm" :disabled="confirming||confirm.code.length<6">{{ confirming?'Activating…':'Activate 2FA' }}</button>
                <button class="btn-ghost" @click="qrVisible=false">Cancel</button>
              </div>
            </div>
          </div>

          <div class="card">
            <div class="card-title">Change Panel Password</div>
            <p class="hint-text mb-3">This changes your GhostWire panel login password only.</p>
            <div class="form-group"><label>Current password</label><input v-model="pass.current" type="password" autocomplete="current-password"/></div>
            <div class="form-group"><label>New password (min 8 chars)</label><input v-model="pass.new_" type="password" autocomplete="new-password"/></div>
            <div v-if="passMsg" class="alert" :class="`alert-${passMsgType}`">{{ passMsg }}</div>
            <button class="btn-primary" @click="changePass">Update Password</button>
          </div>

          <div class="card" style="grid-column:1/-1">
            <div class="card-title">API Keys</div>
            <ApiKeysView />
          </div>
        </div>
      </section>

      <!-- DNS ──────────────────────────────────────────────────── -->
      <section v-show="activeSection === 'dns'" class="section-body">
        <div class="card">
          <div class="card-title">DNS Ad Blocking</div>
          <p class="hint-text mb-4">Block ads and trackers at the DNS level for all your VPN traffic.</p>
          <div v-if="dnsSettings" class="dns-toggle-row">
            <div>
              <div class="dns-label">Block ads &amp; trackers</div>
              <div class="dns-sub">{{ dnsSettings.blocking_enabled ? '🟢 Active — ads are being blocked' : '⚫ Disabled — all DNS queries pass through' }}</div>
            </div>
            <label class="toggle-switch">
              <input type="checkbox" :checked="dnsSettings.blocking_enabled" @change="toggleDnsBlocking"/>
              <span class="toggle-slider"></span>
            </label>
          </div>
          <div v-if="dnsSettings && (dnsSettings.custom_whitelist?.length || dnsSettings.custom_blacklist?.length)" class="dns-chips mt-3">
            <span v-if="dnsSettings.custom_whitelist?.length" class="chip-green">✓ {{ dnsSettings.custom_whitelist.length }} whitelisted</span>
            <span v-if="dnsSettings.custom_blacklist?.length" class="chip-red">✗ {{ dnsSettings.custom_blacklist.length }} blacklisted</span>
          </div>
          <div v-if="!dnsSettings" class="empty-state mt-3">
            <div class="es-icon">🛡</div>
            <div class="es-text">DNS settings unavailable</div>
          </div>
        </div>
      </section>

    </main>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import api from '@/utils/api'
import { useWebSocket } from '@/composables/useWebSocket'
import ApiKeysView from '@/components/twofa/ApiKeysView.vue'

const auth   = useAuthStore()
const router = useRouter()

const brand            = ref('GhostWire')
const serverInfo       = ref(null)
const activeSection    = ref('overview')
const sidebarCollapsed = ref(false)

const manual         = ref(null)
const vpnPassword    = ref('')
const vpnUsername    = ref('')
const showPw         = ref(false)
const credError      = ref('')
const loadingConfigs = ref(false)
const configsLoaded  = ref(false)
const activeOs       = ref('ios')
const dlBusy         = ref('')
const dlError        = ref('')

const mySessions = ref([])
const fleetNodes = ref([])

// ── WebSocket live session updates ────────────────────────────────────────────
const { snapshot: _wsSnap } = useWebSocket()
watch(_wsSnap, (snap) => {
  if (snap?.active_sessions) {
    // The WS snapshot provides both `bytes_in` (formatted string e.g. "1.2 MB")
    // and `bytes_in_raw` (raw integer bytes). Normalize sessions so fmtBytes()
    // always receives a plain number, regardless of which path populated the list.
    mySessions.value = snap.active_sessions.map(s => ({
      ...s,
      bytes_in:  typeof s.bytes_in  === 'number' ? s.bytes_in  : (s.bytes_in_raw  ?? 0),
      bytes_out: typeof s.bytes_out === 'number' ? s.bytes_out : (s.bytes_out_raw ?? 0),
    }))
  }
})

const pass        = ref({ current: '', new_: '' })
const passMsg     = ref('')
const passMsgType = ref('info')

const twoFAStatus  = ref({ totp_enabled: false, has_secret: false })
const qrVisible    = ref(false)
const qrSvg        = ref('')
const setupSecret  = ref('')
const setupLoading = ref(false)
const setupError   = ref('')
const confirm      = ref({ password: '', code: '' })
const confirming   = ref(false)
const confirmError = ref('')
const confirmOk    = ref('')
const disable      = ref({ password: '', code: '' })
const disabling    = ref(false)
const disableError = ref('')
const disableOk    = ref('')

const dnsSettings           = ref(null)
const profileUpdateRequired = ref(false)
let _pollTimer = null

const twoFAEnabled  = computed(() => twoFAStatus.value.totp_enabled)
const userInitial   = computed(() => (auth.user?.username || '?')[0].toUpperCase())
const totalBytesIn  = computed(() => mySessions.value.reduce((a, s) => a + (parseInt(s.bytes_in,  10) || 0), 0))
const totalBytesOut = computed(() => mySessions.value.reduce((a, s) => a + (parseInt(s.bytes_out, 10) || 0), 0))
const groupedSecret = computed(() => setupSecret.value.match(/.{1,4}/g)?.join(' ') || '')

const navItems = computed(() => [
  { id: 'overview', label: 'Overview',    sub: 'Your VPN at a glance',        icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>' },
  { id: 'connect',  label: 'Connect',     sub: 'Download profiles & configs', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>' },
  { id: 'sessions', label: 'Sessions',    sub: 'Active VPN connections',      icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M2 12h20"/><path d="M12 2a15.3 15.3 0 010 20"/></svg>', badge: mySessions.value.length || null },
  { id: 'security', label: 'Security',    sub: 'Password, 2FA & API keys',    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>' },
  { id: 'dns',      label: 'DNS Blocking',sub: 'Ad & tracker blocking',       icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/></svg>' },
])
const currentNav = computed(() => navItems.value.find(n => n.id === activeSection.value))

const osList = [
  { key:'ios',     label:'iOS',     icon:'<svg viewBox="0 0 24 24" width="13" height="13" fill="currentColor"><path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.8-.91.65.03 2.47.26 3.64 1.98c-2.17 1.28-2.15 3.81 2.68 4.04-.42 1.44-1.38 2.83zm-5.71-14c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11z"/></svg>' },
  { key:'android', label:'Android', icon:'<svg viewBox="0 0 24 24" width="13" height="13" fill="currentColor"><path d="M17.523 15.341a5.023 5.023 0 01-4.996 4.65 5.023 5.023 0 01-4.997-4.65H2.5l1.518-8.5h15.964l1.518 8.5h-4.977zM8.5 3L6 6h12l-2.5-3h-7zm7.5 8a1 1 0 100-2 1 1 0 000 2zm-8 0a1 1 0 100-2 1 1 0 000 2z"/></svg>' },
  { key:'windows', label:'Windows', icon:'<svg viewBox="0 0 24 24" width="13" height="13" fill="currentColor"><path d="M3 12V6.75l6-1.32v6.57H3zm17 0V5.25L11 3.5V12h9zm-9 .75H3v5.93l6 1.07v-7zm9 0h-8V20.5l8-1.43V12.75z"/></svg>' },
  { key:'macos',   label:'macOS',   icon:'<svg viewBox="0 0 24 24" width="13" height="13" fill="currentColor"><path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.8-.91.65.03 2.47.26 3.64 1.98c-2.17 1.28-2.15 3.81 2.68 4.04-.42 1.44-1.38 2.83zM13 3.5c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11z"/></svg>' },
  { key:'linux',   label:'Linux',   icon:'<svg viewBox="0 0 24 24" width="13" height="13" fill="currentColor"><path d="M12 2a10 10 0 100 20A10 10 0 0012 2z"/></svg>' },
]

onMounted(async () => {
  await Promise.allSettled([
    api.get('/vpn/server-info').then(r => { serverInfo.value = r.data; brand.value = r.data.brand || 'GhostWire' }),
    api.get('/auth/me').then(r => { vpnUsername.value = r.data.vpn_username || '' }),
    api.get('/dns/settings/me').then(r => { dnsSettings.value = r.data }),
    api.get('/vpn/sessions/my').then(r => { mySessions.value = r.data }),
    api.get('/nodes/').then(r => { fleetNodes.value = r.data.filter(n => n.is_enabled && n.status === 'online') }),
    api.get('/2fa/status').then(r => { twoFAStatus.value = r.data }),
  ])
  _checkProfileUpdateStatus()
  _pollTimer = setInterval(_checkProfileUpdateStatus, 60_000)
})

async function _checkProfileUpdateStatus() {
  try { const { data } = await api.get('/profiles/update-status'); profileUpdateRequired.value = !!data.update_required } catch {}
}
async function dismissProfileUpdateBanner() {
  try { await api.post('/profiles/update-acknowledged') } catch {}
  profileUpdateRequired.value = false
  if (_pollTimer) { clearInterval(_pollTimer); _pollTimer = null }
}
async function refreshSessions() {
  try { const { data } = await api.get('/vpn/sessions/my'); mySessions.value = data } catch {}
}
async function loadConfigs() {
  if (!vpnPassword.value) return
  credError.value = ''; loadingConfigs.value = true
  try {
    const { data } = await api.get(`/profiles/manual?vpn_password=${encodeURIComponent(vpnPassword.value)}`)
    manual.value = data; configsLoaded.value = true
  } catch (e) {
    credError.value = e.response?.data?.detail || 'Wrong VPN password'
  } finally { loadingConfigs.value = false }
}
async function dl(type) {
  if (!vpnPassword.value) return
  dlError.value = ''; dlBusy.value = type
  const names = { mobileconfig:`${brand.value}_VPN.mobileconfig`, sswan:`${brand.value}_VPN.sswan`, 'sswan-xauth':`${brand.value}_VPN_XauthPSK.sswan`, ps1:`Install_${brand.value}_VPN.ps1`, pbk:`${brand.value}_VPN.pbk`, nmconnection:`${brand.value}_VPN.nmconnection` }
  try {
    const token = localStorage.getItem('ghostwire_token')
    const res = await fetch(`/api/profiles/download/${type}?vpn_password=${encodeURIComponent(vpnPassword.value)}`, { headers: { Authorization: `Bearer ${token}` } })
    if (!res.ok) { const e = await res.json().catch(()=>({detail:`HTTP ${res.status}`})); throw new Error(e.detail) }
    const blob = await res.blob()
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = names[type] || `${brand.value}_VPN.${type}`; document.body.appendChild(a); a.click(); document.body.removeChild(a)
  } catch (e) { dlError.value = `Download failed: ${e.message}` }
  finally { dlBusy.value = '' }
}
async function changePass() {
  passMsg.value = ''
  if (!pass.value.current || !pass.value.new_) { passMsg.value = 'Both fields required'; passMsgType.value = 'danger'; return }
  try {
    await api.post('/auth/change-password', { current_password: pass.value.current, new_password: pass.value.new_ })
    passMsg.value = '✓ Password changed'; passMsgType.value = 'success'; pass.value = { current:'', new_:'' }
  } catch (e) { passMsg.value = e.response?.data?.detail || 'Failed'; passMsgType.value = 'danger' }
  setTimeout(() => passMsg.value = '', 6000)
}
async function fetch2FAStatus() {
  try { const { data } = await api.get('/2fa/status'); twoFAStatus.value = data } catch {}
}
async function startSetup() {
  setupLoading.value = true; setupError.value = ''
  try {
    const { data } = await api.get('/2fa/setup')
    setupSecret.value = data.secret
    qrSvg.value = ''
    // Use raw fetch so we get SVG text, not JSON-parsed garbage
    const token = localStorage.getItem('ghostwire_token')
    const res = await fetch('/api/2fa/setup/qr', {
      headers: { Authorization: `Bearer ${token}`, Accept: 'image/svg+xml, text/plain, */*' }
    })
    if (!res.ok) throw new Error(`QR fetch failed: ${res.status}`)
    const svg = await res.text()
    if (!svg || !svg.includes('<svg')) throw new Error('Invalid QR response')
    qrSvg.value = svg
    qrVisible.value = true
  } catch (e) {
    qrVisible.value = false
    setupError.value = e.response?.data?.detail || e.message || 'Setup failed — try again'
  } finally { setupLoading.value = false }
}
async function doConfirm() {
  confirming.value = true; confirmError.value = ''; confirmOk.value = ''
  try {
    await api.post('/2fa/setup/confirm', { password: confirm.value.password, code: confirm.value.code.trim() })
    confirmOk.value = '✓ 2FA enabled! Your account is now protected.'
    await fetch2FAStatus(); qrVisible.value = false
  } catch (e) { confirmError.value = e.response?.data?.detail || 'Confirmation failed' }
  finally { confirming.value = false }
}
async function doDisable() {
  disabling.value = true; disableError.value = ''; disableOk.value = ''
  try {
    await api.post('/2fa/disable', { password: disable.value.password, code: disable.value.code.trim() })
    disableOk.value = '2FA has been disabled.'
    disable.value = { password: '', code: '' }
    await fetch2FAStatus()
  } catch (e) { disableError.value = e.response?.data?.detail || 'Failed' }
  finally { disabling.value = false }
}
function copySecret() { navigator.clipboard?.writeText(setupSecret.value).catch(() => {}) }
async function toggleDnsBlocking() {
  if (!dnsSettings.value) return
  try { const resp = await api.put('/dns/settings/me', { blocking_enabled: !dnsSettings.value.blocking_enabled }); dnsSettings.value = resp.data } catch {}
}
function logout() { auth.logout(); router.replace('/login') }
function fmtAgo(iso) {
  if (!iso) return ''
  const s = Math.floor((Date.now() - new Date(iso)) / 1000)
  if (s < 60) return `${s}s ago`
  if (s < 3600) return `${Math.floor(s/60)}m ago`
  return `${Math.floor(s/3600)}h ago`
}
function fmtBytes(n) {
  if (!n) return '0 B'
  if (n < 1024) return n + ' B'
  if (n < 1048576) return (n/1024).toFixed(1) + ' KB'
  if (n < 1073741824) return (n/1048576).toFixed(1) + ' MB'
  return (n/1073741824).toFixed(2) + ' GB'
}
</script>

<style scoped>
.gw-portal { display:flex; min-height:100vh; background:var(--bg); }

/* Sidebar */
.gw-sidebar { width:220px; min-height:100vh; background:var(--bg2); border-right:1px solid var(--border); display:flex; flex-direction:column; transition:width .2s ease; position:sticky; top:0; height:100vh; flex-shrink:0; overflow:hidden; }
.gw-sidebar.collapsed { width:58px; }
.sidebar-top { display:flex; align-items:center; justify-content:space-between; padding:16px 12px; border-bottom:1px solid var(--border); gap:6px; }
.sidebar-brand { display:flex; align-items:center; gap:9px; overflow:hidden; }
.brand-pulse { width:9px; height:9px; border-radius:50%; background:var(--accent); box-shadow:0 0 7px var(--accent); flex-shrink:0; animation:gpulse 2s ease-in-out infinite; }
@keyframes gpulse { 0%,100%{box-shadow:0 0 5px var(--accent)} 50%{box-shadow:0 0 14px var(--accent),0 0 22px rgba(99,102,241,.35)} }
.brand-name { font-size:14px; font-weight:700; color:var(--text); white-space:nowrap; letter-spacing:.04em; }
.collapse-btn { background:none; border:none; padding:3px; color:var(--text3); cursor:pointer; border-radius:4px; display:flex; flex-shrink:0; }
.collapse-btn:hover { color:var(--text); background:var(--bg3); }
.collapse-btn svg { width:13px; height:13px; }
.sidebar-nav { flex:1; padding:10px 7px; display:flex; flex-direction:column; gap:2px; }
.nav-item { display:flex; align-items:center; gap:9px; padding:8px 9px; border-radius:7px; border:none; background:transparent; color:var(--text3); font-size:12px; font-weight:500; cursor:pointer; transition:all .12s; white-space:nowrap; font-family:inherit; width:100%; }
.nav-item:hover { background:var(--bg3); color:var(--text); }
.nav-item.active { background:rgba(99,102,241,.14); color:var(--accent); border:1px solid rgba(99,102,241,.22); }
.nav-icon { flex-shrink:0; width:15px; height:15px; display:flex; align-items:center; }
.nav-icon :deep(svg) { width:15px; height:15px; }
.nav-label { flex:1; }
.nav-badge { background:var(--accent); color:#fff; font-size:10px; font-weight:700; padding:1px 6px; border-radius:10px; }
.sidebar-footer { padding:10px 8px; border-top:1px solid var(--border); }
.user-chip { display:flex; align-items:center; gap:7px; padding:8px 6px; border-radius:7px; background:var(--bg3); border:1px solid var(--border); }
.user-avatar { width:26px; height:26px; border-radius:6px; background:linear-gradient(135deg,var(--accent),var(--accent2)); display:flex; align-items:center; justify-content:center; font-size:11px; font-weight:700; color:#fff; flex-shrink:0; }
.user-meta { flex:1; min-width:0; }
.user-name { font-size:11px; color:var(--text); font-weight:600; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.user-role { font-size:10px; color:var(--text3); }
.signout-btn { background:none; border:none; color:var(--text3); cursor:pointer; padding:3px; border-radius:4px; display:flex; }
.signout-btn:hover { color:var(--danger); }

/* Main */
.gw-main { flex:1; display:flex; flex-direction:column; min-width:0; }
.topbar { display:flex; align-items:center; justify-content:space-between; padding:14px 24px; background:var(--bg2); border-bottom:1px solid var(--border); position:sticky; top:0; z-index:5; gap:10px; }
.page-title { font-size:15px; font-weight:700; color:var(--text); }
.page-sub { font-size:11px; color:var(--text3); margin-top:1px; }
.topbar-right { display:flex; align-items:center; gap:8px; flex-shrink:0; }
.server-pill { display:flex; align-items:center; gap:6px; padding:4px 11px; border-radius:20px; background:var(--bg3); border:1px solid var(--border); font-size:11px; }
.server-pill code { color:var(--text2); font-family:monospace; }
.spill-dot { width:6px; height:6px; border-radius:50%; flex-shrink:0; }
.dot-green { background:var(--success); box-shadow:0 0 5px var(--success); }
.mobile-menu-btn { display:none; background:none; border:1px solid var(--border); color:var(--text2); padding:5px 9px; border-radius:5px; }
.section-body { padding:24px; overflow-y:auto; }

/* Overview */
.update-banner { display:flex; align-items:flex-start; gap:10px; padding:12px 14px; background:rgba(251,191,36,.08); border:1px solid rgba(251,191,36,.28); border-radius:var(--radius); margin-bottom:18px; }
.ub-icon { font-size:16px; flex-shrink:0; }
.ub-body { flex:1; }
.ub-body strong { display:block; color:var(--text); font-size:13px; margin-bottom:2px; }
.ub-body p { margin:0; font-size:12px; color:var(--text2); }
.ub-dismiss { background:none; border:none; color:var(--text3); cursor:pointer; font-size:14px; padding:0 4px; }
.stats-row { display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:12px; margin-bottom:18px; }
.stat-tile { display:flex; align-items:center; gap:12px; padding:14px 16px; background:var(--bg2); border:1px solid var(--border); border-radius:var(--radius); }
.st-icon { width:38px; height:38px; border-radius:9px; display:flex; align-items:center; justify-content:center; flex-shrink:0; }
.st-icon svg { width:17px; height:17px; }
.st-blue   { background:rgba(99,102,241,.14); color:var(--accent); }
.st-green  { background:rgba(52,211,153,.14); color:var(--success); }
.st-purple { background:rgba(139,92,246,.14); color:var(--accent2); }
.st-warn   { background:rgba(251,191,36,.14); color:var(--warning); }
.st-val { font-size:18px; font-weight:700; color:var(--text); line-height:1.2; }
.st-lbl { font-size:11px; color:var(--text3); margin-top:2px; }
.quick-actions { margin-bottom:4px; }
.qa-title { font-size:10px; color:var(--text3); text-transform:uppercase; letter-spacing:.08em; margin-bottom:8px; }
.qa-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:8px; }
.qa-card { display:flex; flex-direction:column; align-items:center; gap:7px; padding:14px 8px; background:var(--bg2); border:1px solid var(--border); border-radius:var(--radius); cursor:pointer; transition:all .14s; font-family:inherit; color:var(--text2); }
.qa-card:hover { border-color:var(--accent); background:rgba(99,102,241,.06); color:var(--text); transform:translateY(-1px); }
.qa-icon { font-size:18px; }
.qa-lbl { font-size:11px; font-weight:500; }
.server-info-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(180px,1fr)); gap:0; }
.si-row { display:flex; flex-direction:column; gap:3px; padding:9px 0; border-bottom:1px solid rgba(30,42,58,.5); }
.si-row:last-child { border-bottom:none; }
.si-key { font-size:10px; color:var(--text3); text-transform:uppercase; letter-spacing:.06em; }
.si-val { font-size:12px; color:var(--accent); background:rgba(99,102,241,.1); padding:2px 6px; border-radius:4px; display:inline-block; width:fit-content; font-family:monospace; }
.fleet-list { display:flex; flex-direction:column; gap:7px; }
.fleet-row { display:flex; align-items:center; gap:10px; padding:9px; background:var(--bg3); border-radius:7px; border:1px solid var(--border); }
.fleet-flag { font-size:18px; }
.fleet-info { flex:1; }
.fleet-name { font-size:13px; font-weight:600; color:var(--text); }
.fleet-loc  { font-size:11px; color:var(--text3); }
.fleet-right { display:flex; align-items:center; gap:6px; }
.fleet-ping  { font-size:11px; color:var(--text3); font-family:monospace; }
.fleet-badge { border-radius:10px; padding:2px 7px; font-size:10px; font-weight:600; }
.fleet-badge.online { background:rgba(52,211,153,.12); color:var(--success); border:1px solid rgba(52,211,153,.24); }

/* Sessions */
.empty-state { display:flex; flex-direction:column; align-items:center; justify-content:center; padding:40px 20px; gap:7px; }
.es-icon { font-size:28px; }
.es-text { font-size:13px; color:var(--text2); font-weight:600; }
.es-sub  { font-size:11px; color:var(--text3); }
.sessions-list { display:flex; flex-direction:column; gap:7px; }
.session-card { display:flex; align-items:center; gap:12px; padding:12px 14px; background:var(--bg3); border:1px solid var(--border); border-radius:var(--radius); }
.sess-dot { width:7px; height:7px; border-radius:50%; background:var(--success); box-shadow:0 0 5px var(--success); flex-shrink:0; }
.sess-main { flex:1; min-width:0; }
.sess-ip { font-size:13px; font-weight:600; color:var(--text); }
.sess-meta { font-size:11px; color:var(--text3); margin-top:2px; display:flex; gap:4px; flex-wrap:wrap; align-items:center; }
.sess-meta code { color:var(--accent2); background:rgba(139,92,246,.1); padding:1px 4px; border-radius:3px; font-family:monospace; font-size:10px; }
.sep { color:var(--border); }
.sess-bytes { display:flex; flex-direction:column; gap:3px; text-align:right; flex-shrink:0; }
.sb-row { display:flex; align-items:center; gap:4px; font-size:11px; color:var(--text2); justify-content:flex-end; }
.sb-in  { color:var(--success); font-weight:700; }
.sb-out { color:var(--accent);  font-weight:700; }

/* Connect */
.unlock-row { display:flex; gap:10px; align-items:flex-end; flex-wrap:wrap; }
.static-val { background:var(--bg3); border:1px solid var(--border); padding:7px 10px; border-radius:var(--radius-sm); font-size:13px; color:var(--text); font-family:monospace; }
.pw-wrap { position:relative; }
.pw-wrap input { padding-right:34px; }
.pw-eye { position:absolute; right:8px; top:50%; transform:translateY(-50%); background:none; border:none; cursor:pointer; font-size:13px; color:var(--text2); padding:2px; }
.os-tabs { display:flex; gap:3px; flex-wrap:wrap; background:var(--bg2); border:1px solid var(--border); border-radius:var(--radius); padding:4px; margin-bottom:16px; }
.os-tab { display:flex; align-items:center; gap:5px; padding:6px 12px; border-radius:6px; border:none; background:transparent; color:var(--text2); font-size:12px; font-weight:500; cursor:pointer; transition:all .12s; flex:1; justify-content:center; font-family:inherit; }
.os-tab:hover:not(.active) { background:var(--bg3); color:var(--text); }
.os-tab.active { background:var(--accent); color:#fff; }
.ostab-icon { display:inline-flex; align-items:center; }
.method-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(360px,1fr)); gap:16px; }
.method-card { background:var(--bg2); border:1px solid var(--border); border-radius:var(--radius); padding:20px; position:relative; }
.method-card.recommended { border-color:rgba(99,102,241,.45); }
.method-badge { position:absolute; top:-1px; right:12px; background:var(--accent); color:#fff; font-size:9px; font-weight:700; padding:2px 7px; border-radius:0 0 5px 5px; text-transform:uppercase; letter-spacing:.08em; }
.method-header { display:flex; align-items:center; gap:10px; margin-bottom:10px; }
.micon { width:36px; height:36px; border-radius:8px; display:flex; align-items:center; justify-content:center; flex-shrink:0; }
.micon svg { width:18px; height:18px; }
.mt { font-size:13px; font-weight:600; color:var(--text); }
.ms { font-size:11px; color:var(--text3); margin-top:1px; }
.steps p { font-size:12px; color:var(--text2); margin-bottom:3px; line-height:1.5; }
.steps p b { color:var(--text); }
.ftable { display:flex; flex-direction:column; border:1px solid var(--border); border-radius:5px; overflow:hidden; }
.fr { display:flex; justify-content:space-between; align-items:center; padding:5px 9px; border-bottom:1px solid rgba(30,42,58,.5); font-size:11px; background:var(--bg3); }
.fr:last-child { border-bottom:none; }
.fr>span { color:var(--text2); flex-shrink:0; margin-right:8px; min-width:90px; }
.fr code { word-break:break-all; color:var(--accent); font-family:monospace; }
.code-block { background:var(--bg3); border:1px solid var(--border); border-radius:5px; padding:10px; }
.code-line { font-size:11px; color:var(--accent); line-height:2; white-space:pre-wrap; font-family:monospace; }
.ic { background:var(--bg3); color:var(--accent); padding:1px 4px; border-radius:3px; font-size:10px; word-break:break-all; font-family:monospace; }

/* Security */
.security-grid { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
.twofa-bar { display:flex; align-items:center; gap:9px; padding:9px 12px; border-radius:7px; font-size:12px; border:1px solid; }
.tfa-on  { background:rgba(52,211,153,.07); border-color:rgba(52,211,153,.22); color:var(--success); }
.tfa-off { background:rgba(148,163,184,.05); border-color:var(--border); color:var(--text2); }
.tfa-dot { width:7px; height:7px; border-radius:50%; flex-shrink:0; background:currentColor; box-shadow:0 0 5px currentColor; }
.qr-wrap { display:flex; justify-content:center; padding:10px; background:#fff; border-radius:9px; border:2px solid rgba(99,102,241,.18); }
.qr-inner { display:flex; align-items:center; justify-content:center; }
.qr-inner :deep(svg) { width:190px!important; height:190px!important; display:block; }
.qr-placeholder { display:flex; flex-direction:column; align-items:center; justify-content:center; height:110px; background:var(--bg3); border-radius:7px; border:1px dashed var(--border); gap:7px; }
.qr-spinner { width:22px; height:22px; border:3px solid var(--border); border-top-color:var(--accent); border-radius:50%; animation:gwspin .7s linear infinite; }
@keyframes gwspin { to{transform:rotate(360deg)} }
.manual-secret { margin-top:7px; }
.secret-box { display:flex; align-items:center; gap:7px; background:var(--bg3); padding:8px 10px; border-radius:5px; border:1px solid var(--border); }
.grouped-secret { font-size:12px; font-weight:600; color:var(--accent2); letter-spacing:2px; flex:1; word-break:break-all; font-family:monospace; }
.code-input { text-align:center; font-size:20px; font-weight:700; letter-spacing:8px; color:var(--accent); font-family:monospace; }

/* DNS */
.dns-toggle-row { display:flex; align-items:center; justify-content:space-between; gap:16px; padding:14px; background:var(--bg3); border-radius:8px; border:1px solid var(--border); }
.dns-label { font-size:13px; font-weight:600; color:var(--text); margin-bottom:2px; }
.dns-sub { font-size:12px; color:var(--text2); }
.toggle-switch { position:relative; display:inline-block; width:40px; height:22px; flex-shrink:0; }
.toggle-switch input { opacity:0; width:0; height:0; }
.toggle-slider { position:absolute; inset:0; background:var(--bg3); border:1px solid var(--border); border-radius:22px; cursor:pointer; transition:.2s; }
.toggle-slider::before { content:''; position:absolute; width:16px; height:16px; left:2px; bottom:2px; background:var(--text3); border-radius:50%; transition:.2s; }
.toggle-switch input:checked+.toggle-slider { background:rgba(99,102,241,.18); border-color:var(--accent); }
.toggle-switch input:checked+.toggle-slider::before { transform:translateX(18px); background:var(--accent); }
.dns-chips { display:flex; gap:6px; flex-wrap:wrap; }
.chip-green { padding:3px 10px; border-radius:20px; font-size:11px; font-weight:600; background:rgba(52,211,153,.1); color:var(--success); border:1px solid rgba(52,211,153,.22); }
.chip-red   { padding:3px 10px; border-radius:20px; font-size:11px; font-weight:600; background:rgba(248,113,113,.1); color:var(--danger); border:1px solid rgba(248,113,113,.22); }

/* Shared */
.hint-text { font-size:12px; color:var(--text2); line-height:1.6; }
.flex { display:flex; }
.flex-wrap { flex-wrap:wrap; }
.gap-1 { gap:4px; }
.gap-2 { gap:8px; }
.mt-2 { margin-top:8px; }
.mt-3 { margin-top:14px; }
.mt-4 { margin-top:20px; }
.mb-2 { margin-bottom:8px; }
.mb-3 { margin-bottom:14px; }
.mb-4 { margin-bottom:20px; }
.w-full { width:100%; }
.text-sm { font-size:11px; }

@media(max-width:640px) {
  .gw-sidebar { position:fixed; z-index:50; height:100vh; }
  .gw-sidebar.collapsed { width:0; overflow:hidden; }
  .section-body { padding:14px; }
  .mobile-menu-btn { display:block; }
  .qa-grid { grid-template-columns:repeat(2,1fr); }
  .stats-row { grid-template-columns:1fr 1fr; }
  .security-grid { grid-template-columns:1fr; }
  .topbar { padding:10px 14px; }
  .method-grid { grid-template-columns:1fr; }
}
</style>
