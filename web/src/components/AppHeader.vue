<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { authState, logout } from '../services/auth'

const route = useRoute()
const router = useRouter()

const navigation = [
  { to: '/screen-record', label: '电脑录屏' },
  { to: '/image-compress', label: '图片压缩' },
  { to: '/video-compress', label: '视频压缩' },
  { to: '/ocr', label: '文字识别' },
  { to: '/pdf-convert', label: 'PDF 转换' },
  { to: '/excel-headers', label: 'Excel 标题' },
  { to: '/cutout', label: '人像抠图' },
  { to: '/ink-cutout', label: '印章抠图' }
]

const displayName = computed(() =>
  authState.session?.user.nickname || authState.session?.user.username || ''
)

async function handleLogout() {
  logout()
  if (route.meta.tool || route.meta.requiresAuth) await router.replace('/')
}
</script>

<template>
  <header class="site-header">
    <div class="header-inner">
      <RouterLink class="brand" to="/" aria-label="返回蛋蛋小工具首页">
        <img class="brand-mark" src="/dandan-logo.png" alt="" />
        <span>
          <strong>蛋蛋小工具</strong>
          <small>本机处理 · 不上传文件</small>
        </span>
      </RouterLink>
      <nav class="top-navigation" aria-label="工具导航">
        <RouterLink v-for="item in navigation" :key="item.to" :to="item.to">
          {{ item.label }}
        </RouterLink>
      </nav>
      <div class="account-navigation">
        <RouterLink class="account-link suggestion-nav-link" to="/suggestions">
          <span class="suggestion-label-full">功能建议</span>
          <span class="suggestion-label-short">建议</span>
        </RouterLink>
        <template v-if="authState.session">
          <span class="account-name" :title="authState.session.user.username">{{ displayName }}</span>
          <button class="account-link account-logout" type="button" @click="handleLogout">退出</button>
        </template>
        <template v-else>
          <RouterLink class="account-link" to="/login">登录</RouterLink>
          <RouterLink v-if="authState.setting.registerEnabled" class="account-register" to="/register">注册</RouterLink>
        </template>
      </div>
    </div>
  </header>
</template>
