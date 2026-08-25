<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'

import ErrorNotice from '../components/ErrorNotice.vue'
import FileDropzone from '../components/FileDropzone.vue'
import PageHeading from '../components/PageHeading.vue'
import ResultPlaceholder from '../components/ResultPlaceholder.vue'
import { uploadForInkCutout } from '../services/api'
import { triggerDownload, validateImageFile } from '../utils/files'
import { createObjectUrlManager } from '../utils/objectUrl'

const file = ref<File | null>(null)
const inputPreviewUrl = ref('')
const resultPreviewUrl = ref('')
const resultBlob = ref<Blob | null>(null)
const threshold = ref(18)
const loading = ref(false)
const error = ref<unknown>(null)
const inputManager = createObjectUrlManager()
const resultManager = createObjectUrlManager()

function selectFile(nextFile: File): void {
  try {
    file.value = validateImageFile(nextFile)
    inputPreviewUrl.value = inputManager.set(nextFile)
    resultManager.clear()
    resultPreviewUrl.value = ''
    resultBlob.value = null
    error.value = null
  } catch (reason) {
    error.value = reason
  }
}

async function processImage(): Promise<void> {
  if (!file.value || loading.value) return
  loading.value = true
  error.value = null
  try {
    const blob = await uploadForInkCutout(file.value, threshold.value)
    resultBlob.value = blob
    resultPreviewUrl.value = resultManager.set(blob)
  } catch (reason) {
    error.value = reason
  } finally {
    loading.value = false
  }
}

function downloadResult(): void {
  if (resultBlob.value) triggerDownload(resultBlob.value, 'ink-cutout.png')
}

onBeforeUnmount(() => {
  inputManager.clear()
  resultManager.clear()
})
</script>

<template>
  <div class="tool-view">
    <PageHeading
      eyebrow="INK CUTOUT"
      title="文字 / 印章抠图"
      description="保留彩色印章、文字和手写内容，去除白色或近白色背景。"
    />
    <ErrorNotice v-if="error" :error="error" @dismiss="error = null" />
    <div class="workspace-grid">
      <section class="panel input-panel">
        <FileDropzone
          accept="image/jpeg,image/png,image/webp"
          title="选择文字或印章图片"
          hint="背景有灰影时调高强度；浅色文字丢失时调低"
          :file="file"
          :disabled="loading"
          camera
          @select="selectFile"
        />
        <img v-if="inputPreviewUrl" class="image-preview" :src="inputPreviewUrl" alt="待处理图片" />
        <div v-if="file" class="range-panel">
          <div class="range-heading">
            <label for="threshold">去白强度</label>
            <output for="threshold">{{ threshold }}</output>
          </div>
          <input
            id="threshold"
            v-model.number="threshold"
            type="range"
            min="0"
            max="80"
            step="1"
            :disabled="loading"
          />
          <div class="range-labels"><span>保留浅色</span><span>去除灰影</span></div>
        </div>
        <button
          class="primary-button full-button teal-button"
          type="button"
          :disabled="!file || loading"
          @click="processImage"
        >
          <span v-if="loading" class="spinner" />
          {{ loading ? '正在处理…' : resultBlob ? '按当前强度重新处理' : '开始文字抠图' }}
        </button>
      </section>

      <section class="panel result-panel">
        <div v-if="resultPreviewUrl" class="cutout-result">
          <div class="result-heading">
            <div>
              <span class="success-label teal-label">处理完成</span>
              <h2>透明背景结果</h2>
            </div>
            <span class="value-badge">强度 {{ threshold }}</span>
          </div>
          <div class="result-stage checkerboard">
            <img :src="resultPreviewUrl" alt="文字印章透明背景结果" />
          </div>
          <button
            class="primary-button full-button teal-button"
            type="button"
            @click="downloadResult"
          >
            下载透明 PNG
          </button>
        </div>
        <ResultPlaceholder
          v-else
          symbol="章"
          title="透明背景结果会显示在这里"
          description="蓝色印章、彩色文字和黑色手写内容都会保留。"
        />
      </section>
    </div>
  </div>
</template>
