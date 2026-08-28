<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import {
  authState,
  hasFeaturePermission,
  logout,
  refreshFeaturePermissions
} from '../services/auth'
import {
  getWindowsBuildArtifactUrl,
  getWindowsBuildStatus,
  startWindowsBuild
} from '../services/api'
import type { WindowsBuildArtifact } from '../types/api'

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

const DEFAULT_DIST_PATH = 'C:\\lihuize\\wechatMini\\dist'
const DEFAULT_DESKTOP_PATH = 'C:\\Users\\localadmin\\Desktop'

const displayName = computed(() =>
  authState.session?.user.nickname || authState.session?.user.username || ''
)
const canBuildWindows = computed(() => hasFeaturePermission('windows-build'))

const buildDialogOpen = ref(false)
const buildStarting = ref(false)
const buildStatus = ref<'idle' | 'running' | 'restarting' | 'completed' | 'failed'>('idle')
const buildError = ref('')
const targetDirectory = ref(DEFAULT_DIST_PATH)
const outputDirectory = ref(DEFAULT_DIST_PATH)
const logPath = ref('')
const artifacts = ref<WindowsBuildArtifact[]>([])
const pollTimer = ref<number | null>(null)
const consecutiveErrors = ref(0)

function loadPermissions() {
  if (!authState.session) return
  refreshFeaturePermissions().catch(() => undefined)
}

onMounted(loadPermissions)
watch(() => authState.session?.token, loadPermissions)

function openBuildDialog() {
  buildError.value = ''
  buildStarting.value = false
  buildStatus.value = 'idle'
  targetDirectory.value = DEFAULT_DIST_PATH
  buildDialogOpen.value = true
}

function closeBuildDialog() {
  stopPolling()
  buildDialogOpen.value = false
}

function setQuickPath(path: string) {
  targetDirectory.value = path
}

function stopPolling() {
  if (pollTimer.value !== null) {
    clearInterval(pollTimer.value)
    pollTimer.value = null
  }
}

async function checkStatus() {
  try {
    const res = await getWindowsBuildStatus()
    consecutiveErrors.value = 0
    if (res.status === 'running') {
      buildStatus.value = 'running'
    } else if (res.status === 'completed') {
      stopPolling()
      buildStatus.value = 'completed'
      outputDirectory.value = res.outputDirectory || targetDirectory.value
      artifacts.value = res.artifacts || []
      logPath.value = res.logPath || ''
    } else if (res.status === 'failed') {
      stopPolling()
      buildStatus.value = 'failed'
      buildError.value = 'Windows 打包构建失败，请查看日志'
      logPath.value = res.logPath || ''
    }
  } catch {
    // During service restart, connection might drop momentarily.
    consecutiveErrors.value += 1
    if (buildStatus.value === 'running') {
      buildStatus.value = 'restarting'
    }
    if (consecutiveErrors.value > 30) {
      stopPolling()
      buildStatus.value = 'failed'
      buildError.value = '连接服务超时，请检查 Windows 服务状态'
    }
  }
}

function startPolling() {
  stopPolling()
  consecutiveErrors.value = 0
  pollTimer.value = window.setInterval(checkStatus, 2500)
}

async function handleWindowsBuild() {
  const token = authState.session?.token
  if (!token || buildStarting.value) return
  buildStarting.value = true
  buildError.value = ''
  try {
    const result = await startWindowsBuild(token, targetDirectory.value)
    buildStatus.value = 'running'
    outputDirectory.value = result.outputDirectory || targetDirectory.value
    logPath.value = result.logPath || ''
    startPolling()
  } catch (error) {
    buildError.value = error instanceof Error ? error.message : '启动 Windows 打包失败'
  } finally {
    buildStarting.value = false
  }
}

onUnmounted(() => {
  stopPolling()
})

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
        <button
          v-if="authState.session && canBuildWindows"
          class="account-register build-nav-button"
          type="button"
          @click="openBuildDialog"
        >
          打包
        </button>
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
    <div v-if="buildDialogOpen" class="modal-backdrop" role="presentation" @click.self="closeBuildDialog">
      <section class="access-modal build-modal" role="dialog" aria-modal="true" aria-labelledby="build-modal-title">
        <span
          class="access-modal-icon build-modal-icon"
          :class="{
            'is-success': buildStatus === 'completed',
            'is-failed': buildStatus === 'failed'
          }"
          aria-hidden="true"
        >
          {{ buildStatus === 'completed' ? '✓' : buildStatus === 'failed' ? '!' : 'W' }}
        </span>
        <h2 id="build-modal-title">
          {{ buildStatus === 'completed' ? '打包与重启完成' : buildStatus === 'failed' ? '打包未完成' : 'Windows 本机打包' }}
        </h2>

        <!-- Completed View -->
        <template v-if="buildStatus === 'completed'">
          <p>Windows 安装包与便携版已重新生成完毕，Windows 服务已自动重启并生效。</p>
          <div class="build-path-group">
            <span class="build-path-label">产物输出路径</span>
            <div class="build-output-path">{{ outputDirectory }}</div>
          </div>
          <div v-if="artifacts.length > 0" class="build-artifacts-list">
            <div v-for="item in artifacts" :key="item.name" class="build-artifact-card">
              <div class="build-artifact-meta">
                <span class="build-artifact-name">{{ item.name }}</span>
                <span class="build-artifact-size">{{ item.sizeMb }} MB</span>
              </div>
              <a
                class="build-download-button"
                :href="getWindowsBuildArtifactUrl(item.name)"
                :download="item.name"
              >
                下载文件
              </a>
            </div>
          </div>
          <div class="build-hint-box">
            提示：最新代码及前端静态页面已在后台服务（端口 9902）更新运行。
          </div>
          <div class="access-modal-actions">
            <button class="primary-button" type="button" @click="closeBuildDialog">完成</button>
          </div>
        </template>

        <!-- Running or Restarting View -->
        <template v-else-if="buildStatus === 'running' || buildStatus === 'restarting'">
          <p>打包任务正在执行中，请耐心等待（通常耗时约 30~60 秒）…</p>
          <div class="build-progress-section">
            <div class="build-steps">
              <div class="build-step-item is-done">
                <span class="build-step-icon">✓</span>
                <span>权限校验通过</span>
              </div>
              <div class="build-step-item" :class="buildStatus === 'running' ? 'is-active' : 'is-done'">
                <span class="build-step-icon">{{ buildStatus === 'running' ? '●' : '✓' }}</span>
                <span>构建 Web 前端、执行测试并打包 EXE/ZIP</span>
              </div>
              <div class="build-step-item" :class="buildStatus === 'restarting' ? 'is-active' : ''">
                <span class="build-step-icon">{{ buildStatus === 'restarting' ? '●' : '○' }}</span>
                <span>自动重启 Windows 服务 (DandanTools)</span>
              </div>
            </div>
            <div class="build-path-group">
              <span class="build-path-label">保存电脑路径</span>
              <div class="build-output-path">{{ targetDirectory }}</div>
            </div>
          </div>
        </template>

        <!-- Failed View -->
        <template v-else-if="buildStatus === 'failed'">
          <p v-if="buildError" class="build-error">{{ buildError }}</p>
          <div v-if="logPath" class="build-path-group">
            <span class="build-path-label">日志文件</span>
            <div class="build-output-path">{{ logPath }}</div>
          </div>
          <div class="access-modal-actions">
            <button class="secondary-button" type="button" @click="closeBuildDialog">关闭</button>
            <button class="primary-button" type="button" @click="handleWindowsBuild">重新打包</button>
          </div>
        </template>

        <!-- Idle / Initial View -->
        <template v-else>
          <p>将重新编译 Web 前端、执行自动化测试并生成 Windows 安装包与便携包，完成后自动重启本机 Windows 服务。</p>
          <div class="build-path-group">
            <label class="build-path-label" for="target-dir-input">选择保存电脑路径</label>
            <div class="build-path-input-row">
              <input
                id="target-dir-input"
                v-model="targetDirectory"
                class="build-path-input"
                type="text"
                placeholder="例如 C:\lihuize\wechatMini\dist"
              />
            </div>
            <div class="build-quick-buttons">
              <button
                class="build-quick-btn"
                :class="{ 'is-active': targetDirectory === DEFAULT_DIST_PATH }"
                type="button"
                @click="setQuickPath(DEFAULT_DIST_PATH)"
              >
                默认目录 (dist)
              </button>
              <button
                class="build-quick-btn"
                :class="{ 'is-active': targetDirectory === DEFAULT_DESKTOP_PATH }"
                type="button"
                @click="setQuickPath(DEFAULT_DESKTOP_PATH)"
              >
                桌面目录
              </button>
            </div>
          </div>
          <p v-if="buildError" class="build-error">{{ buildError }}</p>
          <div class="access-modal-actions">
            <button class="secondary-button" type="button" :disabled="buildStarting" @click="closeBuildDialog">取消</button>
            <button class="primary-button" type="button" :disabled="buildStarting" @click="handleWindowsBuild">
              <span v-if="buildStarting" class="spinner" aria-hidden="true"></span>
              {{ buildStarting ? '正在启动…' : '确认打包' }}
            </button>
          </div>
        </template>
      </section>
    </div>
  </header>
</template>
