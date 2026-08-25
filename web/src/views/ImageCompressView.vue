<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'

import ErrorNotice from '../components/ErrorNotice.vue'
import FileDropzone from '../components/FileDropzone.vue'
import PageHeading from '../components/PageHeading.vue'
import ResultPlaceholder from '../components/ResultPlaceholder.vue'
import { compressImage } from '../services/api'
import type {
  CompressionPreset,
  ImageCompressionResult,
  ImageOutputFormat
} from '../types/api'
import {
  formatFileSize,
  triggerDownload,
  validateCompressionImageFile
} from '../utils/files'
import { createObjectUrlManager } from '../utils/objectUrl'

const presets: Array<{ value: CompressionPreset; label: string; hint: string }> = [
  { value: 'small', label: '小体积', hint: '最长边 1600px · 质量 60' },
  { value: 'balanced', label: '均衡', hint: '最长边 2560px · 质量 75' },
  { value: 'high', label: '高清', hint: '保持尺寸 · 质量 88' },
  { value: 'custom', label: '高级', hint: '自定义尺寸、质量和目标大小' }
]
const targetSizeOptions = [200, 500, 1024]

const file = ref<File | null>(null)
const inputUrl = ref('')
const resultUrl = ref('')
const result = ref<ImageCompressionResult | null>(null)
const preset = ref<CompressionPreset>('balanced')
const maxDimension = ref(1920)
const quality = ref(75)
const targetSizeKb = ref<number | undefined>()
const outputFormat = ref<ImageOutputFormat>('auto')
const loading = ref(false)
const error = ref<unknown>(null)
const inputManager = createObjectUrlManager()
const resultManager = createObjectUrlManager()
const saved = computed(() => result.value ? result.value.originalSize - result.value.outputSize : 0)

function selectFile(nextFile: File): void {
  try {
    file.value = validateCompressionImageFile(nextFile)
    inputUrl.value = inputManager.set(nextFile)
    resultManager.clear()
    resultUrl.value = ''
    result.value = null
    error.value = null
  } catch (reason) {
    error.value = reason
  }
}

function selectTargetSize(sizeKb: number): void {
  preset.value = 'custom'
  targetSizeKb.value = sizeKb
  resultManager.clear()
  resultUrl.value = ''
  result.value = null
}

async function runCompression(): Promise<void> {
  if (!file.value || loading.value) return
  loading.value = true
  error.value = null
  try {
    const compressed = await compressImage(file.value, {
      preset: preset.value,
      outputFormat: outputFormat.value,
      maxDimension: preset.value === 'custom' ? maxDimension.value : undefined,
      quality: preset.value === 'custom' ? quality.value : undefined,
      targetSizeKb: preset.value === 'custom' ? targetSizeKb.value : undefined
    })
    result.value = compressed
    resultUrl.value = resultManager.set(compressed.blob)
  } catch (reason) {
    error.value = reason
  } finally {
    loading.value = false
  }
}

function downloadResult(): void {
  if (result.value) triggerDownload(result.value.blob, result.value.fileName)
}

onBeforeUnmount(() => {
  inputManager.clear()
  resultManager.clear()
})
</script>

<template>
  <div class="tool-view">
    <PageHeading eyebrow="IMAGE COMPRESS" title="图片压缩"
      description="智能选择更小的图片格式，也可以指定尺寸、质量或目标文件大小。" />
    <ErrorNotice v-if="error" :error="error" @dismiss="error = null" />
    <div class="workspace-grid">
      <section class="panel input-panel">
        <FileDropzone accept="image/jpeg,image/png,image/webp" title="选择需要压缩的图片"
          hint="支持 JPG、PNG、WebP，单张不超过 50MB" :file="file" :disabled="loading"
          camera @select="selectFile" />
        <img v-if="inputUrl" class="image-preview" :src="inputUrl" alt="待压缩图片预览" />
        <fieldset class="format-fieldset" :disabled="loading">
          <legend>压缩方式</legend>
          <div class="compression-presets">
            <button v-for="item in presets" :key="item.value" type="button"
              class="compression-preset" :class="{ selected: preset === item.value }"
              @click="preset = item.value">
              <strong>{{ item.label }}</strong><small>{{ item.hint }}</small>
            </button>
          </div>
        </fieldset>
        <div class="quick-target-panel">
          <div><strong>常用目标大小</strong><span>适合报名、证件和办公系统上传</span></div>
          <div class="quick-target-options">
            <button v-for="size in targetSizeOptions" :key="size" type="button"
              :class="{ selected: preset === 'custom' && targetSizeKb === size }"
              :disabled="loading" @click="selectTargetSize(size)">
              {{ size === 1024 ? '1MB' : `${size}KB` }}
            </button>
          </div>
        </div>
        <div v-if="preset === 'custom'" class="advanced-options">
          <label>最长边 <input v-model.number="maxDimension" type="number" min="320" max="16000" /> px</label>
          <label>质量 <input v-model.number="quality" type="range" min="35" max="95" /> {{ quality }}</label>
          <label>目标大小 <input v-model.number="targetSizeKb" type="number" min="16" placeholder="可不填" /> KB</label>
          <label>输出格式
            <select v-model="outputFormat">
              <option value="auto">智能选择</option><option value="jpeg">JPEG</option>
              <option value="webp">WebP</option><option value="png">PNG</option>
            </select>
          </label>
        </div>
        <button class="primary-button full-button" type="button" :disabled="!file || loading" @click="runCompression">
          <span v-if="loading" class="spinner" />{{ loading ? '正在压缩…' : '开始压缩' }}
        </button>
      </section>
      <section class="panel result-panel">
        <div v-if="result" class="compression-result">
          <div class="result-heading"><div><span class="success-label">压缩完成</span><h2>{{ result.fileName }}</h2></div>
            <span class="value-badge">{{ result.format.toUpperCase() }}</span></div>
          <img class="compression-preview" :src="resultUrl" alt="图片压缩结果" />
          <div class="size-comparison">
            <div><small>压缩前</small><strong>{{ formatFileSize(result.originalSize) }}</strong></div>
            <span>→</span>
            <div><small>压缩后</small><strong>{{ formatFileSize(result.outputSize) }}</strong></div>
          </div>
          <p v-if="result.skipped">原图已经接近最优，已保留原文件。</p>
          <p v-else-if="!result.targetReached">未能达到目标大小，已生成当前可用的最小结果。</p>
          <p v-else>减少 {{ formatFileSize(Math.max(0, saved)) }}，压缩率 {{ result.ratio }}% · {{ result.width }} × {{ result.height }}</p>
          <button class="primary-button full-button" type="button" @click="downloadResult">下载压缩图片</button>
        </div>
        <ResultPlaceholder v-else symbol="IMG" title="压缩结果会显示在这里"
          description="默认使用均衡模式；透明图片会保留透明通道。" />
      </section>
    </div>
  </div>
</template>

<style scoped>
.compression-presets{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.compression-preset{padding:12px;display:grid;gap:4px;border:1px solid var(--line);border-radius:12px;background:#fff;text-align:left;cursor:pointer}.compression-preset.selected{border-color:var(--blue);background:var(--blue-soft)}.compression-preset small{color:var(--muted);font-size:10px}.quick-target-panel{margin-top:12px;padding:12px 14px;display:flex;align-items:center;justify-content:space-between;gap:12px;border:1px solid #d9e4fa;border-radius:13px;background:#f6f9ff}.quick-target-panel>div:first-child{display:grid;gap:3px}.quick-target-panel strong{font-size:12px}.quick-target-panel span{color:var(--muted);font-size:10px}.quick-target-options{display:flex;gap:7px}.quick-target-options button{padding:7px 10px;border:1px solid #cddaf3;border-radius:999px;color:#2b67d1;background:#fff;font-size:11px;font-weight:700;cursor:pointer}.quick-target-options button.selected{border-color:var(--blue);color:#fff;background:var(--blue)}.advanced-options{margin-top:12px;padding:14px;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;border:1px solid var(--line);border-radius:13px;background:#fafbfc}.advanced-options label{display:grid;gap:6px;color:var(--muted);font-size:11px}.advanced-options input,.advanced-options select{min-width:0;padding:8px;border:1px solid #d9deea;border-radius:8px;background:#fff}.compression-result{width:100%}.compression-preview{width:100%;height:280px;object-fit:contain;border:1px solid var(--line);border-radius:14px;background:#f5f6f8}.size-comparison{margin-top:16px;display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:12px}.size-comparison div{padding:12px;display:grid;gap:3px;border-radius:11px;background:#f7f9fc}.size-comparison small,.compression-result p{color:var(--muted);font-size:11px}.compression-result p{text-align:center}@media(max-width:640px){.quick-target-panel{align-items:flex-start;flex-direction:column}.advanced-options{grid-template-columns:1fr}.compression-preview{height:230px}}
</style>
