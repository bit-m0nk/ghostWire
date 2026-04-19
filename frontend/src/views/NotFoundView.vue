<template>
  <div class="notfound">
    <div class="box">
      <div class="code">404</div>
      <h2>Page not found</h2>
      <p>The page you're looking for doesn't exist.</p>
      <router-link to="/" class="btn-primary">Go home</router-link>
    </div>
  </div>
</template>

<style scoped>
.notfound {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg);
}
.box {
  text-align: center;
  padding: 48px 32px;
}
.code {
  font-size: 72px;
  font-weight: 800;
  color: var(--border);
  line-height: 1;
  margin-bottom: 16px;
}
h2 {
  font-size: 20px;
  color: var(--text);
  margin-bottom: 8px;
}
p {
  color: var(--text2);
  margin-bottom: 24px;
}
.btn-primary {
  display: inline-block;
  background: var(--accent);
  color: #fff;
  padding: 10px 24px;
  border-radius: var(--radius-sm);
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
}
.btn-primary:hover {
  background: #6fa0ff;
  text-decoration: none;
}
</style>
