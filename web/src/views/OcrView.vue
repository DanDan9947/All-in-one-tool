<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'

import ErrorNotice from '../components/ErrorNotice.vue'
import FileDropzone from '../components/FileDropzone.vue'
import PageHeading from '../components/PageHeading.vue'
import ResultPlaceholder from '../components/ResultPlaceholder.vue'
import { uploadForOcr } from '../services/api'
import { validateImageFile } from '../utils/files'
import { createObjectUrlManager } from '../utils/objectUrl'

const file = ref<File | null>(null)
const previewUrl = ref('')
const resultText = ref('')
const loading = ref(false)
const error = ref<unknown>(null)
const copied = ref(false)
const previewManager = createObjectUrlManager()

function selectFile(nextFile: File): void {
  try {
    file.value = validateImageFile(nextFile)
    previewUrl.value = previewManager.set(nextFile)
    resultText.value = ''
    error.value = null
    copied.value = false
  } catch (reason) {
    error.value = reason
  }
}

async function recognize(): Promise<void> {
  if (!file.value || loading.value) return
  loading.value = true
  error.value = null
  try {
    const result = await uploadForOcr(file.value)
    resultText.value = result.text
  } catch (reason) {
    error.value = reason
  } finally {
    loading.value = false
  }
}

async function copyResult(): Promise<void> {
  if (!resultText.value) return
  try {
    await navigator.clipboard.writeText(resultText.value)
  } catch {
    const textarea = document.createElement('textarea')
    textarea.value = resultText.value
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    textarea.remove()
  }
  copied.value = true
  window.setTimeout(() => (copied.value = false), 1600)
}

onBeforeUnmount(() => previewManager.clear())
</script>

<template>
  <div class="tool-view">
    <PageHeading
      eyebrow="OCR"
      title="提取图片文字"
      description="上传包含文字的图片，识别结果可以直接选择或复制。"
    />
    <ErrorNotice v-if="error" :error="error" @dismiss="error = null" />
    <div class="workspace-grid">
      <section class="panel input-panel">
        <FileDropzone
          accept="image/jpeg,image/png,image/webp"
          title="选择含有文字的图片"
          hint="支持 JPG、PNG、WebP，单张不超过 10MB"
          :file="file"
          :disabled="loading"
          camera
          @select="selectFile"
        />
        <img v-if="previewUrl" class="image-preview" :src="previewUrl" alt="待识别图片预览" />
        <button
          class="primary-button full-button"
          type="button"
          :disabled="!file || loading"
          @click="recognize"
        >
          <span v-if="loading" class="spinner" />
          {{ loading ? '正在识别…' : '开始识别' }}
        </button>
      </section>

      <section class="panel result-panel">
        <div v-if="resultText" class="text-result">
          <div class="result-heading">
            <div>
              <span class="success-label">识别完成</span>
              <h2>识别结果</h2>
            </div>
            <button class="secondary-button compact-button" type="button" @click="copyResult">
              {{ copied ? '已复制' : '复制全部' }}
            </button>
          </div>
          <pre>{{ resultText }}</pre>
        </div>
        <ResultPlaceholder
          v-else
          symbol="文"
          title="识别结果会显示在这里"
          description="文字越清晰、图片越端正，识别效果越好。"
        />
      </section>
    </div>
  </div>
</template>
