<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'

import ErrorNotice from '../components/ErrorNotice.vue'
import FileDropzone from '../components/FileDropzone.vue'
import PageHeading from '../components/PageHeading.vue'
import ResultPlaceholder from '../components/ResultPlaceholder.vue'
import {
  cancelVideoCompression,
  createVideoCompression,
  getVideoCompression,
  videoCompressionDownloadUrl
} from '../services/api'
import type { CompressionPreset, VideoCompressionJob } from '../types/api'
import { formatFileSize, validateVideoFile } from '../utils/files'

const file = ref<File | null>(null)
const preset = ref<CompressionPreset>('balanced')
const maxHeight = ref(1080)
const crf = ref(26)
const sizeMode = ref(false)
const targetSizeMb = ref<number | undefined>()
const uploadProgress = ref(0)
const job = ref<VideoCompressionJob | null>(null)
const loading = ref(false)
const error = ref<unknown>(null)
let pollTimer = 0
let disposed = false

function selectFile(nextFile: File): void {
  try {
    file.value = validateVideoFile(nextFile)
    job.value = null
    uploadProgress.value = 0
    error.value = null
  } catch (reason) {
    error.value = reason
  }
}

async function startCompression(): Promise<void> {
  if (!file.value || loading.value) return
  loading.value = true
  error.value = null
  try {
    job.value = await createVideoCompression(file.value, {
      preset: preset.value,
      maxHeight: preset.value === 'custom' ? maxHeight.value : undefined,
      crf: preset.value === 'custom' && !sizeMode.value ? crf.value : undefined,
      targetSizeMb: preset.value === 'custom' && sizeMode.value ? targetSizeMb.value : undefined
    }, progress => uploadProgress.value = progress)
    await pollJob()
  } catch (reason) {
    error.value = reason
    loading.value = false
  }
}

async function pollJob(): Promise<void> {
  if (!job.value || disposed) return
  try {
    const next = await getVideoCompression(job.value.jobId)
    job.value = next
    if (next.status === 'completed') {
      loading.value = false
      return
    }
    if (next.status === 'failed' || next.status === 'cancelled') {
      loading.value = false
      if (next.status === 'failed') error.value = new Error(next.errorMessage || '视频压缩失败')
      return
    }
    pollTimer = window.setTimeout(() => void pollJob(), 1000)
  } catch (reason) {
    loading.value = false
    error.value = reason
  }
}

async function cancel(): Promise<void> {
  if (!job.value) return
  window.clearTimeout(pollTimer)
  await cancelVideoCompression(job.value.jobId)
  job.value.status = 'cancelled'
  loading.value = false
}

onBeforeUnmount(() => {
  disposed = true
  window.clearTimeout(pollTimer)
  if (job.value && ['queued', 'processing'].includes(job.value.status)) {
    void cancelVideoCompression(job.value.jobId)
  }
})
</script>

<template>
  <div class="tool-view">
    <PageHeading eyebrow="VIDEO COMPRESS" title="视频压缩"
      description="本机使用 FFmpeg 压缩视频，统一生成兼容性更好的 MP4 文件。" />
    <ErrorNotice v-if="error" :error="error" @dismiss="error = null" />
    <div class="workspace-grid">
      <section class="panel input-panel">
        <FileDropzone accept="video/mp4,video/quicktime,video/x-matroska,video/webm"
          title="选择需要压缩的视频" hint="支持 MP4、MOV、MKV、WebM；在线版最大 500MB，本机版最大 2GB"
          :file="file" :disabled="loading" @select="selectFile" />
        <div v-if="file" class="file-summary"><span class="video-file-icon">MP4</span><div><strong>{{ file.name }}</strong><span>{{ formatFileSize(file.size) }}</span></div></div>
        <fieldset class="format-fieldset" :disabled="loading"><legend>压缩方式</legend>
          <div class="video-presets">
            <button v-for="item in ([['small','小体积','最高 720p'],['balanced','均衡','最高 1080p'],['high','高清','保持分辨率'],['custom','高级','自定义参数']] as const)"
              :key="item[0]" type="button" :class="{ selected: preset === item[0] }" @click="preset = item[0]">
              <strong>{{ item[1] }}</strong><small>{{ item[2] }}</small>
            </button>
          </div>
        </fieldset>
        <div v-if="preset === 'custom'" class="video-advanced">
          <label>最高分辨率 <select v-model.number="maxHeight"><option :value="480">480p</option><option :value="720">720p</option><option :value="1080">1080p</option><option :value="2160">2160p</option></select></label>
          <label class="mode-row"><input v-model="sizeMode" type="checkbox" /> 按目标大小估算</label>
          <label v-if="sizeMode">目标大小 <input v-model.number="targetSizeMb" type="number" min="1" placeholder="MB" /></label>
          <label v-else>质量 CRF <input v-model.number="crf" type="range" min="18" max="35" /> {{ crf }}</label>
        </div>
        <button class="primary-button full-button" type="button" :disabled="!file || loading" @click="startCompression">
          <span v-if="loading" class="spinner" />{{ loading ? '正在处理…' : '开始压缩' }}
        </button>
        <div v-if="loading" class="progress-panel"><div class="progress-track"><div class="progress-value" :style="{ width: `${job ? job.progress : uploadProgress}%` }" /></div>
          <div><span>{{ job ? (job.status === 'queued' ? '等待处理' : '正在压缩') : '正在上传' }}</span><strong>{{ job ? job.progress : uploadProgress }}%</strong></div>
          <button class="text-button" type="button" @click="cancel">取消任务</button></div>
      </section>
      <section class="panel result-panel">
        <div v-if="job?.status === 'completed' && job.token" class="video-result">
          <span class="success-mark">✓</span><span class="success-label">压缩完成</span><h2>{{ job.fileName }}</h2>
          <div class="video-sizes"><span>{{ formatFileSize(job.originalSize) }}</span><b>→</b><strong>{{ formatFileSize(job.outputSize || 0) }}</strong></div>
          <p>结果将在本机临时保留 15 分钟，请及时保存。</p>
          <a class="primary-button download-link" :href="videoCompressionDownloadUrl(job.token)" :download="job.fileName">下载 MP4</a>
        </div>
        <ResultPlaceholder v-else symbol="MP4" title="压缩结果会显示在这里" description="压缩耗时取决于视频时长、分辨率和电脑性能。" />
      </section>
    </div>
  </div>
</template>

<style scoped>
.video-file-icon{width:44px;height:44px;display:grid;place-items:center;border-radius:10px;color:#b33b35;background:#fde9e7;font-size:10px;font-weight:800}.video-presets{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.video-presets button{padding:12px;display:grid;gap:4px;border:1px solid var(--line);border-radius:12px;background:#fff;text-align:left;cursor:pointer}.video-presets button.selected{border-color:#d7463e;background:#fff3f2}.video-presets small{color:var(--muted);font-size:10px}.video-advanced{margin-top:12px;padding:14px;display:grid;gap:12px;border:1px solid var(--line);border-radius:13px;background:#fafbfc}.video-advanced label{display:flex;align-items:center;gap:9px;color:var(--muted);font-size:11px}.video-advanced select,.video-advanced input[type=number]{padding:8px;border:1px solid #d9deea;border-radius:8px;background:#fff}.video-advanced input[type=range]{flex:1}.progress-panel .text-button{display:block;margin:5px auto 0}.video-result{min-height:450px;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center}.video-result h2{max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.video-sizes{margin:16px 0;display:flex;align-items:center;gap:14px}.video-result p{color:var(--muted);font-size:11px}.download-link{min-height:48px;padding:0 28px;display:inline-flex;align-items:center;justify-content:center}@media(max-width:640px){.video-result{min-height:330px}}
</style>
