<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import {
  AuthError,
  getCaptcha,
  refreshUserSetting,
  register,
  registrationIsEnabled
} from '../services/auth'

const router = useRouter()
const form = reactive({
  username: '',
  nickname: '',
  mobile: '',
  email: '',
  password: '',
  confirmPassword: '',
  captchaCode: ''
})
const captchaId = ref('')
const captchaImage = ref('')
const captchaLoading = ref(false)
const loading = ref(false)
const errorMessage = ref('')

async function refreshCaptcha() {
  captchaLoading.value = true
  form.captchaCode = ''
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

function validate(): string {
  const usernameLength = form.username.trim().length
  if (usernameLength < 3 || usernameLength > 60) return '用户名长度需为 3～60 位'
  if (form.password.length < 6 || form.password.length > 32) return '密码长度需为 6～32 位'
  if (form.password !== form.confirmPassword) return '两次输入的密码不一致'
  if (!captchaId.value || !form.captchaCode.trim()) return '请输入图形验证码'
  if (form.mobile.trim().length > 20) return '手机号最多 20 个字符'
  if (form.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) return '邮箱格式不正确'
  return ''
}

async function submit() {
  try {
    await refreshUserSetting()
  } catch {
    // The backend register endpoint also enforces the switch; use the last known value here.
  }
  if (!registrationIsEnabled()) {
    errorMessage.value = '当前系统暂未开放新用户注册'
    return
  }
  errorMessage.value = validate()
  if (errorMessage.value) return
  loading.value = true
  try {
    await register({
      username: form.username,
      password: form.password,
      captchaId: captchaId.value,
      captchaCode: form.captchaCode,
      nickname: form.nickname,
      mobile: form.mobile,
      email: form.email
    })
    await router.replace({
      path: '/login',
      query: { username: form.username.trim(), registration: 'success' }
    })
  } catch (error) {
    errorMessage.value = error instanceof AuthError ? error.message : '注册失败，请稍后重试'
    await refreshCaptcha()
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <section class="auth-view register-view">
    <div class="auth-intro">
      <span class="eyebrow">CREATE ACCOUNT</span>
      <h1>创建账号</h1>
      <p>填写基础信息完成注册，成功后会自动登录。</p>
    </div>
    <form class="auth-panel" @submit.prevent="submit">
      <h2>注册账号</h2>
      <p class="auth-panel-hint"><span class="required">*</span> 为必填项</p>
      <div v-if="errorMessage" class="auth-error" role="alert">{{ errorMessage }}</div>
      <div class="auth-field-grid">
        <label>
          <span>用户名 <b class="required">*</b></span>
          <input v-model="form.username" name="username" maxlength="60" autocomplete="username" placeholder="3～60 位" autofocus />
        </label>
        <label>
          <span>昵称</span>
          <input v-model="form.nickname" name="nickname" maxlength="60" autocomplete="nickname" placeholder="默认使用用户名" />
        </label>
        <label>
          <span>手机号</span>
          <input v-model="form.mobile" name="mobile" maxlength="20" autocomplete="tel" placeholder="选填" />
        </label>
        <label>
          <span>邮箱</span>
          <input v-model="form.email" name="email" type="email" maxlength="120" autocomplete="email" placeholder="选填" />
        </label>
        <label>
          <span>密码 <b class="required">*</b></span>
          <input v-model="form.password" name="password" type="password" maxlength="32" autocomplete="new-password" placeholder="6～32 位" />
        </label>
        <label>
          <span>确认密码 <b class="required">*</b></span>
          <input v-model="form.confirmPassword" name="confirmPassword" type="password" maxlength="32" autocomplete="new-password" placeholder="再次输入密码" />
        </label>
        <label class="captcha-label">
          <span>图形验证码 <b class="required">*</b></span>
          <span class="captcha-field">
            <input v-model="form.captchaCode" name="captchaCode" maxlength="6" autocomplete="off" placeholder="请输入验证码" />
            <button class="captcha-image-button" type="button" :disabled="captchaLoading" title="点击换一张" @click="refreshCaptcha">
              <span v-if="captchaLoading">加载中…</span>
              <img v-else-if="captchaImage" :src="captchaImage" alt="图形验证码" />
              <span v-else>重新加载</span>
            </button>
          </span>
        </label>
      </div>
      <button class="primary-button auth-submit" type="submit" :disabled="loading">
        <span v-if="loading" class="spinner" aria-hidden="true"></span>{{ loading ? '注册中…' : '注册' }}
      </button>
      <p class="auth-switch">已有账号？<RouterLink :to="{ path: '/login', query: { username: form.username } }">返回登录</RouterLink></p>
    </form>
  </section>
</template>
