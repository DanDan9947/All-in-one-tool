<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import {
  listMySuggestions,
  submitSuggestion,
  SuggestionError,
  type FeatureSuggestion
} from '../services/suggestions'

const form = reactive({ title: '', content: '', contact: '' })
const suggestions = ref<FeatureSuggestion[]>([])
const loading = ref(false)
const listLoading = ref(true)
const errorMessage = ref('')
const successMessage = ref('')

const statusLabels: Record<number, string> = {
  0: '待处理',
  1: '已采纳',
  2: '暂未采纳',
  3: '已完成'
}

function formatTime(value?: string): string {
  if (!value) return ''
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { hour12: false })
}

async function loadSuggestions() {
  listLoading.value = true
  try {
    const page = await listMySuggestions()
    suggestions.value = page.items
  } catch (error) {
    errorMessage.value = error instanceof SuggestionError ? error.message : '建议列表加载失败'
  } finally {
    listLoading.value = false
  }
}

async function submit() {
  errorMessage.value = ''
  successMessage.value = ''
  if (!form.title.trim()) {
    errorMessage.value = '请输入建议标题'
    return
  }
  if (!form.content.trim()) {
    errorMessage.value = '请描述你希望增加或改进的功能'
    return
  }
  loading.value = true
  try {
    await submitSuggestion(form)
    form.title = ''
    form.content = ''
    form.contact = ''
    successMessage.value = '建议提交成功，管理员回复后会显示在下方'
    await loadSuggestions()
  } catch (error) {
    errorMessage.value = error instanceof SuggestionError ? error.message : '建议提交失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

onMounted(loadSuggestions)
</script>

<template>
  <div class="suggestions-view">
    <section class="suggestions-heading">
      <span class="eyebrow">FEEDBACK</span>
      <h1>功能建议</h1>
      <p>告诉我们你希望增加的功能或需要改进的地方，处理进度和管理员回复会展示在这里。</p>
    </section>

    <div class="suggestions-layout">
      <form class="panel suggestion-form" @submit.prevent="submit">
        <div class="suggestion-panel-title">
          <div>
            <h2>提交新建议</h2>
            <p>请尽量描述使用场景和期望结果</p>
          </div>
          <span class="suggestion-icon" aria-hidden="true">+</span>
        </div>
        <div v-if="errorMessage" class="auth-error" role="alert">{{ errorMessage }}</div>
        <div v-if="successMessage" class="suggestion-success" role="status">{{ successMessage }}</div>
        <label>
          <span>建议标题 <b class="required">*</b></span>
          <input v-model="form.title" maxlength="120" placeholder="例如：增加图片格式批量转换" />
        </label>
        <label>
          <span>详细说明 <b class="required">*</b></span>
          <textarea v-model="form.content" maxlength="5000" rows="8" placeholder="请描述遇到的问题、使用场景和期望效果"></textarea>
          <small>{{ form.content.length }}/5000</small>
        </label>
        <label>
          <span>联系方式</span>
          <input v-model="form.contact" maxlength="120" placeholder="选填，手机号、邮箱或其他联系方式" />
        </label>
        <button class="primary-button suggestion-submit" type="submit" :disabled="loading">
          <span v-if="loading" class="spinner" aria-hidden="true"></span>{{ loading ? '提交中…' : '提交建议' }}
        </button>
      </form>

      <section class="panel suggestion-history" aria-labelledby="suggestion-history-title">
        <div class="suggestion-panel-title">
          <div>
            <h2 id="suggestion-history-title">我的建议</h2>
            <p>管理员回复后会在对应建议下方显示</p>
          </div>
          <button class="text-button" type="button" :disabled="listLoading" @click="loadSuggestions">刷新</button>
        </div>
        <div v-if="listLoading" class="suggestion-empty">正在加载…</div>
        <div v-else-if="!suggestions.length" class="suggestion-empty">
          <strong>还没有提交过建议</strong>
          <span>你的第一条建议会显示在这里</span>
        </div>
        <div v-else class="suggestion-list">
          <article v-for="item in suggestions" :key="item.id" class="suggestion-card">
            <div class="suggestion-card-head">
              <h3>{{ item.title }}</h3>
              <span class="suggestion-status" :class="`status-${item.status}`">
                {{ statusLabels[item.status] || '处理中' }}
              </span>
            </div>
            <p class="suggestion-content">{{ item.content }}</p>
            <time>{{ formatTime(item.createTime) }}</time>
            <div v-if="item.reply" class="suggestion-reply">
              <strong>管理员回复</strong>
              <p>{{ item.reply }}</p>
              <time v-if="item.updateTime">{{ formatTime(item.updateTime) }}</time>
            </div>
            <div v-else class="suggestion-waiting">暂未回复，我们会尽快查看</div>
          </article>
        </div>
      </section>
    </div>
  </div>
</template>
