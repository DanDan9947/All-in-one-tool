<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AppHeader from './components/AppHeader.vue'
import GlobalContentRails from './components/GlobalContentRails.vue'
import {
  accessPromptState,
  closeLoginRequiredPrompt,
  showLoginRequiredPrompt
} from './services/accessControl'
import { authState, ensureUserSetting, loginIsRequired, refreshUserSetting } from './services/auth'

const router = useRouter()
const route = useRoute()

async function refreshAccessPolicy() {
  try {
    await refreshUserSetting()
  } catch {
    return
  }
  if ((route.meta.requiresAuth || (route.meta.tool && loginIsRequired())) && !authState.session) {
    const targetPath = route.fullPath
    await router.replace('/')
    showLoginRequiredPrompt(targetPath)
  }
}

onMounted(() => {
  ensureUserSetting().catch(() => undefined)
  window.addEventListener('focus', refreshAccessPolicy)
})

onUnmounted(() => window.removeEventListener('focus', refreshAccessPolicy))

async function goToLogin() {
  const redirect = accessPromptState.targetPath
  closeLoginRequiredPrompt()
  await router.push({ path: '/login', query: { redirect } })
}
</script>

<template>
  <div class="app-shell">
    <AppHeader />
    <div class="global-rails-wrap">
      <GlobalContentRails />
    </div>
    <main class="main-content">
      <RouterView />
    </main>
    <footer class="site-footer">
      <span>文件仅用于本次处理，不保存历史记录</span>
      <span class="footer-dot">·</span>
      <span>文件大小上限以各工具页面说明为准</span>
    </footer>
    <div v-if="accessPromptState.visible" class="modal-backdrop" role="presentation" @click.self="closeLoginRequiredPrompt">
      <section class="access-modal" role="dialog" aria-modal="true" aria-labelledby="access-modal-title">
        <span class="access-modal-icon" aria-hidden="true">!</span>
        <h2 id="access-modal-title">需要登录后使用</h2>
        <p>当前系统已开启登录访问，请先登录账号，再继续使用此功能。</p>
        <div class="access-modal-actions">
          <button class="secondary-button" type="button" @click="closeLoginRequiredPrompt">暂不登录</button>
          <button class="primary-button" type="button" @click="goToLogin">前往登录</button>
        </div>
        <RouterLink v-if="authState.setting.registerEnabled" class="access-register-link" to="/register" @click="closeLoginRequiredPrompt">
          没有账号？立即注册
        </RouterLink>
      </section>
    </div>
  </div>
</template>
