<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'

import ErrorNotice from '../components/ErrorNotice.vue'
import FileDropzone from '../components/FileDropzone.vue'
import PageHeading from '../components/PageHeading.vue'
import ResultPlaceholder from '../components/ResultPlaceholder.vue'
import { uploadForCutout } from '../services/api'
import { triggerDownload, validateImageFile } from '../utils/files'
import { composeBackground } from '../utils/image'
import { createObjectUrlManager } from '../utils/objectUrl'

interface BackgroundOption {
  key: string
  label: string
  color: string
}

const backgrounds: BackgroundOption[] = [
  { key: 'transparent', label: '透明', color: '' },
  { key: 'white', label: '白色', color: '#FFFFFF' },
  { key: 'blue', label: '蓝色', color: '#438EDB' },
  { key: 'red', label: '红色', color: '#D93838' }
]

const file = ref<File | null>(null)
const inputPreviewUrl = ref('')
const resultPreviewUrl = ref('')
const transparentBlob = ref<Blob | null>(null)
const resultBlob = ref<Blob | null>(null)
const selectedBackground = ref('transparent')
const customColor = ref('#F5C6D6')
const loading = ref(false)
const composing = ref(false)
const error = ref<unknown>(null)
let compositionGeneration = 0

const inputManager = createObjectUrlManager()
const transparentManager = createObjectUrlManager()
const resultManager = createObjectUrlManager()

function resetResult(): void {
  compositionGeneration += 1
  transparentBlob.value = null
  resultBlob.value = null
  resultPreviewUrl.value = ''
  selectedBackground.value = 'transparent'
  transparentManager.clear()
  resultManager.clear()
}

function selectFile(nextFile: File): void {
  try {
    file.value = validateImageFile(nextFile)
    inputPreviewUrl.value = inputManager.set(nextFile)
    resetResult()
    error.value = null
  } catch (reason) {
    error.value = reason
  }
}

async function cutout(): Promise<void> {
  if (!file.value || loading.value) return
  loading.value = true
  error.value = null
  resetResult()
  try {
    const blob = await uploadForCutout(file.value)
    transparentBlob.value = blob
    transparentManager.set(blob)
    resultBlob.value = blob
    resultPreviewUrl.value = resultManager.set(blob)
  } catch (reason) {
    error.value = reason
  } finally {
    loading.value = false
  }
}

async function selectBackground(option: BackgroundOption): Promise<void> {
  if (!transparentBlob.value) return
  selectedBackground.value = option.key
  const generation = ++compositionGeneration
  composing.value = true
  error.value = null
  try {
    const blob =
      option.key === 'transparent'
        ? transparentBlob.value
        : await composeBackground(transparentManager.current, option.color)
    if (generation !== compositionGeneration) return
    resultBlob.value = blob
    resultPreviewUrl.value = resultManager.set(blob)
  } catch (reason) {
    if (generation === compositionGeneration) error.value = reason
  } finally {
    if (generation === compositionGeneration) composing.value = false
  }
}

function applyCustomColor(): void {
  void selectBackground({ key: 'custom', label: '自定义', color: customColor.value })
}

function downloadResult(): void {
  if (!resultBlob.value || composing.value) return
  triggerDownload(
    resultBlob.value,
    selectedBackground.value === 'transparent'
      ? 'transparent-cutout.png'
      : 'id-photo.png'
  )
}

onBeforeUnmount(() => {
  compositionGeneration += 1
  inputManager.clear()
  transparentManager.clear()
  resultManager.clear()
})
</script>

<template>
  <div class="tool-view">
    <PageHeading
      eyebrow="PORTRAIT"
      title="人像背景移除"
      description="上传一张人像照片，生成透明 PNG 或直接更换证件照背景。"
    />
    <ErrorNotice v-if="error" :error="error" @dismiss="error = null" />
    <div class="workspace-grid">
      <section class="panel input-panel">
        <FileDropzone
          accept="image/jpeg,image/png,image/webp"
          title="选择一张人像照片"
          hint="人物越清晰、与背景区分越明显，抠图效果越好"
          :file="file"
          :disabled="loading"
          camera
          @select="selectFile"
        />
        <img
          v-if="inputPreviewUrl"
          class="image-preview portrait-preview"
          :src="inputPreviewUrl"
          alt="待抠图人像预览"
        />
        <button
          class="primary-button full-button purple-button"
          type="button"
          :disabled="!file || loading"
          @click="cutout"
        >
          <span v-if="loading" class="spinner" />
          {{ loading ? '正在移除背景…' : '移除背景' }}
        </button>
      </section>

      <section class="panel result-panel cutout-result-panel">
        <div v-if="resultPreviewUrl" class="cutout-result">
          <div class="result-heading">
            <div>
              <span class="success-label purple-label">处理完成</span>
              <h2>选择背景</h2>
            </div>
            <span class="local-badge">仅本地换色</span>
          </div>
          <div class="background-options" aria-label="证件照背景颜色">
            <button
              v-for="option in backgrounds"
              :key="option.key"
              type="button"
              class="background-option"
              :class="{ selected: selectedBackground === option.key }"
              :aria-pressed="selectedBackground === option.key"
              @click="selectBackground(option)"
            >
              <span
                class="color-swatch"
                :class="{ checkerboard: option.key === 'transparent' }"
                :style="option.color ? { backgroundColor: option.color } : undefined"
              />
              {{ option.label }}
            </button>
          </div>
          <div class="custom-color-row">
            <label for="custom-color">自定义颜色</label>
            <input id="custom-color" v-model="customColor" type="color" />
            <code>{{ customColor.toUpperCase() }}</code>
            <button class="text-button" type="button" @click="applyCustomColor">应用</button>
          </div>
          <div
            class="result-stage"
            :class="{ checkerboard: selectedBackground === 'transparent' }"
          >
            <img :src="resultPreviewUrl" alt="人像抠图结果" />
            <div v-if="composing" class="processing-mask">
              <span class="spinner dark-spinner" />
              正在生成背景…
            </div>
          </div>
          <button
            class="primary-button full-button purple-button"
            type="button"
            :disabled="composing"
            @click="downloadResult"
          >
            {{ selectedBackground === 'transparent' ? '下载透明 PNG' : '下载证件照' }}
          </button>
        </div>
        <ResultPlaceholder
          v-else
          symbol="像"
          title="透明背景结果会显示在这里"
          description="抠图只需处理一次，切换背景色不会重新上传。"
        />
      </section>
    </div>
  </div>
</template>
