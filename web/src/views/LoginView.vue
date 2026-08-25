<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { AuthError, authState, getCaptcha, login, saveSession } from '../services/auth'

const route = useRoute()
const router = useRouter()
const username = ref(typeof route.query.username === 'string' ? route.query.username : '')
const password = ref('')
const captchaId = ref('')
const captchaCode = ref('')
const captchaImage = ref('')
const captchaLoading = ref(false)
const loading = ref(false)
const errorMessage = ref('')

if (route.query.registration === 'disabled') {
  errorMessage.value = '当前系统暂未开放新用户注册'
} else if (route.query.registration === 'success') {
  errorMessage.value = '注册成功，请输入验证码登录'
}

async function refreshCaptcha() {
  captchaLoading.value = true
  captchaCode.value = ''
  try {
    const challenge = await getCaptcha()
    captchaId.value = challenge.captchaId
    captchaImage.value = challenge.imageBase64
  } catch (error) {
    captchaId.value = ''
    captchaImage.value = ''
    errorMessage.value = error instanceof AuthError ? error.message : '验证码加载失败，请稍后重试'
  } finally {
    captchaLoading.value = false
  }
}

onMounted(refreshCaptcha)

function redirectAfterLogin(): string {
  const redirect = route.query.redirect
  return typeof redirect === 'string' && redirect.startsWith('/') && !redirect.startsWith('//')
    ? redirect
    : '/'
}

async function submit() {
  errorMessage.value = ''
  if (!username.value.trim() || !password.value || !captchaId.value || !captchaCode.value.trim()) {
    errorMessage.value = '请输入用户名、密码和图形验证码'
    return
  }
  loading.value = true
  try {
    const session = await login(username.value, password.value, captchaId.value, captchaCode.value)
    saveSession(session)
    await router.replace(redirectAfterLogin())
  } catch (error) {
    errorMessage.value = error instanceof AuthError ? error.message : '登录失败，请稍后重试'
    await refreshCaptcha()
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <section class="auth-view">
    <div class="auth-intro">
      <span class="eyebrow">ACCOUNT</span>
      <h1>欢迎回来</h1>
      <p>登录蛋蛋小工具账号，继续使用你的工具服务。</p>
    </div>
    <form class="auth-panel" @submit.prevent="submit">
      <h2>账号登录</h2>
      <p class="auth-panel-hint">使用用户名和密码登录</p>
      <div v-if="errorMessage" class="auth-error" role="alert">{{ errorMessage }}</div>
      <label>
        <span>用户名</span>
        <input v-model="username" name="username" maxlength="60" autocomplete="username" placeholder="请输入用户名" autofocus />
      </label>
      <label>
        <span>密码</span>
        <input v-model="password" name="password" type="password" maxlength="32" autocomplete="current-password" placeholder="请输入密码" />
      </label>
      <label>
        <span>图形验证码</span>
        <span class="captcha-field">
          <input v-model="captchaCode" name="captchaCode" maxlength="6" autocomplete="off" placeholder="请输入验证码" />
          <button class="captcha-image-button" type="button" :disabled="captchaLoading" title="点击换一张" @click="refreshCaptcha">
            <span v-if="captchaLoading">加载中…</span>
            <img v-else-if="captchaImage" :src="captchaImage" alt="图形验证码" />
            <span v-else>重新加载</span>
          </button>
        </span>
      </label>
      <button class="primary-button auth-submit" type="submit" :disabled="loading">
        <span v-if="loading" class="spinner" aria-hidden="true"></span>{{ loading ? '登录中…' : '登录' }}
      </button>
      <p v-if="authState.setting.registerEnabled" class="auth-switch">还没有账号？<RouterLink to="/register">立即注册</RouterLink></p>
      <p v-else class="auth-switch">当前系统暂未开放新用户注册</p>
    </form>
  </section>
</template>
