<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, shallowRef } from 'vue'

import ErrorNotice from '../components/ErrorNotice.vue'
import PageHeading from '../components/PageHeading.vue'
import {
  cancelScreenRecording,
  completeScreenRecording,
  createScreenRecording,
  deleteScreenRecordingResult,
  screenRecordingDownloadUrl,
  uploadScreenRecordingChunk
} from '../services/api'
import { ApiError, type ScreenRecordingResult } from '../types/api'
import {
  FULL_SELECTION,
  isFullSelection,
  numberedFileName,
  preferredWebmMimeType,
  screenRecordingFileName,
  sourceRectangle,
  transformSelection,
  type NormalizedRect,
  type SelectionHandle
} from '../utils/screenRecording'

type RecordingStatus = 'idle' | 'ready' | 'recording' | 'paused' | 'finalizing' | 'done' | 'error'
type PermissionStateValue = 'granted' | 'denied' | 'prompt'

interface DirectoryFileHandle {
  name: string
  createWritable(): Promise<WritableStream<Uint8Array>>
}

interface DirectoryHandle {
  name: string
  getFileHandle(name: string, options?: { create?: boolean }): Promise<DirectoryFileHandle>
  removeEntry(name: string): Promise<void>
  queryPermission?(options: { mode: 'readwrite' }): Promise<PermissionStateValue>
  requestPermission?(options: { mode: 'readwrite' }): Promise<PermissionStateValue>
}

type DirectoryPickerWindow = Window & {
  showDirectoryPicker?: (options: {
    id: string
    mode: 'readwrite'
    startIn: 'videos'
  }) => Promise<DirectoryHandle>
}

const preview = ref<HTMLVideoElement | null>(null)
const cropCanvas = ref<HTMLCanvasElement | null>(null)
const selectionStage = ref<HTMLElement | null>(null)
const status = ref<RecordingStatus>('idle')
const selection = ref<NormalizedRect>({ ...FULL_SELECTION })
const videoWidth = ref(0)
const videoHeight = ref(0)
const sizeBytes = ref(0)
const elapsedSeconds = ref(0)
const error = ref<ApiError | null>(null)
const successMessage = ref('')
const saveDirectoryName = ref('')
const pendingResult = ref<ScreenRecordingResult | null>(null)
const displaySurface = ref('')

const displayStream = shallowRef<MediaStream | null>(null)
let outputStream: MediaStream | null = null
let mediaRecorder: MediaRecorder | null = null
let activeRecordingId: string | null = null
let saveDirectoryHandle: DirectoryHandle | null = null
let uploadChain: Promise<void> = Promise.resolve()
let uploadFailure: unknown = null
let nextSequence = 0
let animationFrame = 0
let videoFrameCallback = 0
let timerId = 0
let recordingStartedAt = 0
let pauseStartedAt = 0
let pausedDuration = 0
let currentFileName = ''
let dragging: { handle: SelectionHandle; startX: number; startY: number; initial: NormalizedRect } | undefined

const isCapturing = computed(() => ['recording', 'paused', 'finalizing'].includes(status.value))
const canStart = computed(() => status.value === 'ready' && videoWidth.value > 0 && videoHeight.value > 0 && !!saveDirectoryHandle)
const sourcePixels = computed(() => sourceRectangle(selection.value, videoWidth.value || 1, videoHeight.value || 1))
const recordsFullSource = computed(() => isFullSelection(selection.value))
const selectionStyle = computed(() => ({
  left: `${selection.value.x * 100}%`, top: `${selection.value.y * 100}%`,
  width: `${selection.value.width * 100}%`, height: `${selection.value.height * 100}%`
}))
const formattedDuration = computed(() => {
  const hours = Math.floor(elapsedSeconds.value / 3600)
  const minutes = Math.floor((elapsedSeconds.value % 3600) / 60)
  const seconds = elapsedSeconds.value % 60
  return [hours, minutes, seconds].map(value => String(value).padStart(2, '0')).join(':')
})
const formattedSize = computed(() => formatBytes(sizeBytes.value))
const sourceLabel = computed(() => {
  if (displaySurface.value === 'monitor') return '整个屏幕'
  if (displaySurface.value === 'window') return '所选窗口'
  if (displaySurface.value === 'browser') return '浏览器标签页'
  return '录制来源'
})
const supportsDirectoryPicker = typeof (window as DirectoryPickerWindow).showDirectoryPicker === 'function'

function setError(value: unknown, fallback: string): void {
  error.value = value instanceof ApiError
    ? value
    : new ApiError(value instanceof Error ? value.message : fallback)
  status.value = 'error'
}

async function chooseSaveDirectory(): Promise<boolean> {
  const picker = (window as DirectoryPickerWindow).showDirectoryPicker
  if (!picker) {
    setError(null, '当前浏览器不能选择保存文件夹，请使用最新版 Chrome 或 Microsoft Edge。')
    return false
  }
  try {
    const handle = await picker.call(window, {
      id: 'screen-recordings', mode: 'readwrite', startIn: 'videos'
    })
    saveDirectoryHandle = handle
    saveDirectoryName.value = handle.name
    error.value = null
    if (status.value === 'error' && !displayStream.value) status.value = 'idle'
    return true
  } catch (value) {
    if (value instanceof DOMException && value.name === 'AbortError') return false
    setError(value, '无法取得文件夹写入权限，请重新选择保存文件夹。')
    return false
  }
}

async function ensureDirectoryPermission(): Promise<boolean> {
  if (!saveDirectoryHandle) return false
  if (!saveDirectoryHandle.queryPermission) return true
  let permission = await saveDirectoryHandle.queryPermission({ mode: 'readwrite' })
  if (permission !== 'granted' && saveDirectoryHandle.requestPermission) {
    permission = await saveDirectoryHandle.requestPermission({ mode: 'readwrite' })
  }
  return permission === 'granted'
}

async function chooseSource(): Promise<void> {
  error.value = null
  successMessage.value = ''
  if (!saveDirectoryHandle) {
    error.value = new ApiError('请先选择录屏文件要保存的文件夹。', 'SAVE_DIRECTORY_REQUIRED')
    return
  }
  if (!navigator.mediaDevices?.getDisplayMedia || typeof MediaRecorder === 'undefined') {
    setError(null, '当前浏览器不支持电脑录屏，请使用最新版 Microsoft Edge 或 Google Chrome。')
    return
  }
  cleanupSource()
  try {
    const options = {
      video: { frameRate: { ideal: 30, max: 30 } }, audio: true,
      systemAudio: 'include', surfaceSwitching: 'include'
    } as DisplayMediaStreamOptions
    const stream = await navigator.mediaDevices.getDisplayMedia(options)
    if (stream.getAudioTracks().length === 0) {
      stream.getTracks().forEach(track => track.stop())
      throw new ApiError('没有获取到系统声音。请重新选择屏幕，并勾选“同时共享系统音频”。', 'SYSTEM_AUDIO_REQUIRED')
    }
    displayStream.value = stream
    displaySurface.value = stream.getVideoTracks()[0]?.getSettings().displaySurface || ''
    selection.value = { ...FULL_SELECTION }
    status.value = 'ready'
    await nextTick()
    if (preview.value) {
      preview.value.srcObject = stream
      await preview.value.play()
    }
    stream.getVideoTracks()[0]?.addEventListener('ended', sourceEnded, { once: true })
  } catch (value) {
    if (value instanceof DOMException && (value.name === 'NotAllowedError' || value.name === 'AbortError')) {
      status.value = 'idle'
      return
    }
    setError(value, '无法打开屏幕共享。')
  }
}

function sourceMetadataReady(): void {
  if (!preview.value) return
  videoWidth.value = preview.value.videoWidth
  videoHeight.value = preview.value.videoHeight
}

function sourceEnded(): void {
  if (status.value === 'recording' || status.value === 'paused') {
    stopRecorder()
    return
  }
  cleanupSource()
  if (status.value !== 'done') {
    status.value = 'idle'
    error.value = new ApiError('屏幕共享已结束。尚未点击“开始录制”，所以没有生成文件，请重新选择录制来源。', 'CAPTURE_ENDED')
  }
}

function beginSelectionDrag(event: PointerEvent, handle: SelectionHandle): void {
  if (isCapturing.value || !selectionStage.value) return
  event.preventDefault()
  dragging = { handle, startX: event.clientX, startY: event.clientY, initial: { ...selection.value } }
  window.addEventListener('pointermove', moveSelection)
  window.addEventListener('pointerup', endSelectionDrag, { once: true })
}

function moveSelection(event: PointerEvent): void {
  if (!dragging || !selectionStage.value) return
  const bounds = selectionStage.value.getBoundingClientRect()
  selection.value = transformSelection(
    dragging.initial, dragging.handle,
    (event.clientX - dragging.startX) / bounds.width,
    (event.clientY - dragging.startY) / bounds.height,
    Math.min(1, 64 / Math.max(64, videoWidth.value)),
    Math.min(1, 64 / Math.max(64, videoHeight.value))
  )
}

function endSelectionDrag(): void {
  dragging = undefined
  window.removeEventListener('pointermove', moveSelection)
}

function resetSelection(): void {
  if (!isCapturing.value) selection.value = { ...FULL_SELECTION }
}

async function startRecording(): Promise<void> {
  if (!preview.value || !cropCanvas.value || !displayStream.value || !canStart.value) return
  error.value = null
  successMessage.value = ''
  pendingResult.value = null
  if (!await ensureDirectoryPermission()) {
    error.value = new ApiError('保存文件夹没有写入权限，请重新选择文件夹。', 'SAVE_PERMISSION_REQUIRED')
    return
  }
  if (displayStream.value.getAudioTracks().length === 0) {
    error.value = new ApiError('系统音轨已经失效，请重新选择录制来源。', 'SYSTEM_AUDIO_REQUIRED')
    return
  }
  const mimeType = preferredWebmMimeType()
  if (!mimeType) {
    setError(null, '当前浏览器无法录制视频，请使用最新版 Microsoft Edge 或 Google Chrome。')
    return
  }
  try {
    const session = await createScreenRecording(mimeType)
    activeRecordingId = session.recordingId
    currentFileName = screenRecordingFileName()
    const source = sourcePixels.value
    if (recordsFullSource.value) {
      const sourceVideoTrack = displayStream.value.getVideoTracks()[0]
      if (!sourceVideoTrack) throw new Error('屏幕视频轨道已经失效')
      outputStream = new MediaStream([sourceVideoTrack.clone()])
    } else {
      cropCanvas.value.width = source.width
      cropCanvas.value.height = source.height
      drawCropFrame()
      outputStream = cropCanvas.value.captureStream(30)
    }
    for (const audioTrack of displayStream.value.getAudioTracks()) outputStream.addTrack(audioTrack.clone())
    mediaRecorder = new MediaRecorder(outputStream, {
      mimeType, videoBitsPerSecond: 6_000_000, audioBitsPerSecond: 128_000
    })
    nextSequence = 0
    sizeBytes.value = 0
    uploadFailure = null
    uploadChain = Promise.resolve()
    mediaRecorder.ondataavailable = queueChunk
    mediaRecorder.onstop = () => void finalizeRecording()
    mediaRecorder.onerror = event => {
      uploadFailure = event
      if (mediaRecorder?.state !== 'inactive') mediaRecorder?.stop()
    }
    mediaRecorder.start(session.chunkIntervalMs)
    status.value = 'recording'
    recordingStartedAt = Date.now()
    pausedDuration = 0
    elapsedSeconds.value = 0
    timerId = window.setInterval(updateTimer, 1000)
  } catch (value) {
    if (activeRecordingId) void cancelScreenRecording(activeRecordingId)
    activeRecordingId = null
    stopOutputStream()
    setError(value, '无法开始录屏。')
  }
}

function drawCropFrame(): void {
  if (!preview.value || !cropCanvas.value || !displayStream.value) return
  const context = cropCanvas.value.getContext('2d', { alpha: false })
  if (!context) return
  const source = sourcePixels.value
  context.drawImage(preview.value, source.x, source.y, source.width, source.height,
    0, 0, cropCanvas.value.width, cropCanvas.value.height)
  if (typeof preview.value.requestVideoFrameCallback === 'function') {
    videoFrameCallback = preview.value.requestVideoFrameCallback(() => drawCropFrame())
  } else {
    animationFrame = requestAnimationFrame(drawCropFrame)
  }
}

function cancelCropDrawing(): void {
  cancelAnimationFrame(animationFrame)
  animationFrame = 0
  if (preview.value && videoFrameCallback) {
    preview.value.cancelVideoFrameCallback(videoFrameCallback)
    videoFrameCallback = 0
  }
}

function queueChunk(event: BlobEvent): void {
  if (!activeRecordingId || event.data.size === 0 || uploadFailure) return
  const recordingId = activeRecordingId
  const sequence = nextSequence++
  uploadChain = uploadChain.then(async () => {
    const result = await uploadScreenRecordingChunk(recordingId, sequence, event.data)
    sizeBytes.value = result.sizeBytes
  }).catch(value => {
    uploadFailure = value
    if (mediaRecorder && mediaRecorder.state !== 'inactive') mediaRecorder.stop()
  })
}

function pauseRecording(): void {
  if (!mediaRecorder || mediaRecorder.state !== 'recording') return
  mediaRecorder.pause()
  pauseStartedAt = Date.now()
  status.value = 'paused'
}

function resumeRecording(): void {
  if (!mediaRecorder || mediaRecorder.state !== 'paused') return
  mediaRecorder.resume()
  pausedDuration += Date.now() - pauseStartedAt
  status.value = 'recording'
}

function stopRecording(): void {
  stopRecorder()
}

function stopRecorder(): void {
  if (!mediaRecorder || mediaRecorder.state === 'inactive') return
  if (mediaRecorder.state === 'paused') {
    pausedDuration += Date.now() - pauseStartedAt
    mediaRecorder.resume()
  }
  updateTimer()
  status.value = 'finalizing'
  mediaRecorder.stop()
  window.clearInterval(timerId)
}

async function findAvailableFileName(preferredName: string): Promise<string> {
  if (!saveDirectoryHandle) throw new Error('保存文件夹已失效')
  for (let index = 0; index < 10_000; index += 1) {
    const candidate = numberedFileName(preferredName, index)
    try {
      await saveDirectoryHandle.getFileHandle(candidate)
    } catch (value) {
      if (value instanceof DOMException && value.name === 'NotFoundError') return candidate
      throw value
    }
  }
  throw new Error('保存文件夹内同名文件过多')
}

async function saveResult(result: ScreenRecordingResult): Promise<void> {
  if (!saveDirectoryHandle) throw new Error('保存文件夹已失效，请重新选择')
  if (!await ensureDirectoryPermission()) throw new Error('保存文件夹没有写入权限')
  const targetName = await findAvailableFileName(result.fileName)
  let created = false
  try {
    const fileHandle = await saveDirectoryHandle.getFileHandle(targetName, { create: true })
    created = true
    const response = await fetch(screenRecordingDownloadUrl(result.token))
    if (!response.ok || !response.body) throw new Error('读取 MP4 文件失败')
    const writable = await fileHandle.createWritable()
    await response.body.pipeTo(writable)
    if (result.sizeBytes <= 0) throw new Error('生成的 MP4 文件为空')
  } catch (value) {
    if (created) {
      try { await saveDirectoryHandle.removeEntry(targetName) } catch { /* best effort */ }
    }
    throw value
  }
  try { await deleteScreenRecordingResult(result.token) } catch { /* expires automatically */ }
  pendingResult.value = null
  successMessage.value = `录屏已保存：${targetName}（${formatBytes(result.sizeBytes)}）`
  status.value = 'done'
}

async function retrySave(): Promise<void> {
  if (!pendingResult.value) return
  error.value = null
  status.value = 'finalizing'
  try {
    await saveResult(pendingResult.value)
  } catch (value) {
    setError(value, 'MP4 保存失败，请检查文件夹权限和磁盘空间后重试。')
  }
}

async function finalizeRecording(): Promise<void> {
  cancelCropDrawing()
  window.clearInterval(timerId)
  const recordingId = activeRecordingId
  try {
    await uploadChain
    if (uploadFailure) throw uploadFailure
    if (!recordingId) throw new Error('录屏任务已经失效')
    const result = await completeScreenRecording(recordingId, currentFileName, elapsedSeconds.value)
    activeRecordingId = null
    pendingResult.value = result
    await saveResult(result)
  } catch (value) {
    if (recordingId && activeRecordingId) await cancelScreenRecording(recordingId)
    activeRecordingId = null
    setError(value, pendingResult.value
      ? 'MP4 已生成，但写入文件夹失败。请检查权限或空间后重试保存。'
      : '录屏转码失败，请检查本机磁盘空间后重试。')
  } finally {
    stopOutputStream()
    cleanupSource()
  }
}

function updateTimer(): void {
  if (!recordingStartedAt) return
  const currentPause = status.value === 'paused' ? Date.now() - pauseStartedAt : 0
  elapsedSeconds.value = Math.max(0,
    Math.floor((Date.now() - recordingStartedAt - pausedDuration - currentPause) / 1000))
}

function formatBytes(value: number): string {
  if (!value) return '0 KB'
  return value < 1024 * 1024 ? `${(value / 1024).toFixed(1)} KB` : `${(value / (1024 * 1024)).toFixed(1)} MB`
}

function stopOutputStream(): void {
  cancelCropDrawing()
  outputStream?.getTracks().forEach(track => track.stop())
  outputStream = null
  mediaRecorder = null
}

function cleanupSource(): void {
  displayStream.value?.getTracks().forEach(track => track.stop())
  displayStream.value = null
  if (preview.value) preview.value.srcObject = null
  videoWidth.value = 0
  videoHeight.value = 0
  displaySurface.value = ''
}

onBeforeUnmount(() => {
  window.clearInterval(timerId)
  window.removeEventListener('pointermove', moveSelection)
  if (mediaRecorder) {
    mediaRecorder.ondataavailable = null
    mediaRecorder.onstop = null
    mediaRecorder.onerror = null
    if (mediaRecorder.state !== 'inactive') mediaRecorder.stop()
  }
  if (activeRecordingId) void cancelScreenRecording(activeRecordingId)
  stopOutputStream()
  cleanupSource()
})
</script>

<template>
  <div class="tool-view screen-record-view">
    <PageHeading eyebrow="SCREEN RECORD" title="电脑录屏"
      description="先选择保存文件夹，再选择屏幕或窗口并框选录制范围。完成后自动生成 MP4，视频只在本机处理。" />
    <ErrorNotice v-if="error" :error="error" @dismiss="error = null" />
    <div v-if="successMessage" class="recording-success">{{ successMessage }}</div>
    <section class="recording-panel panel">
      <div v-if="!displayStream" class="recording-empty">
        <span class="recording-icon">REC</span>
        <h2>选择保存文件夹并设置录制来源</h2>
        <p>选择文件夹时不会创建文件；录制成功并生成 MP4 后才会写入。</p>
        <div v-if="!supportsDirectoryPicker" class="browser-warning">
          当前浏览器不支持文件夹保存，请使用最新版 Chrome 或 Microsoft Edge。
        </div>
        <div class="recording-setup-actions">
          <button class="secondary-button" type="button" :disabled="!supportsDirectoryPicker" @click="chooseSaveDirectory">
            1. 选择保存文件夹
          </button>
          <span v-if="saveDirectoryName" class="save-file-name">已选择：{{ saveDirectoryName }}</span>
          <button class="primary-button" type="button"
            :disabled="!saveDirectoryName || !supportsDirectoryPicker" @click="chooseSource">
            2. 选择录制来源
          </button>
          <button v-if="pendingResult" class="primary-button" type="button" @click="retrySave">
            重试保存 MP4
          </button>
        </div>
      </div>
      <template v-else>
        <div class="recording-status-strip" :class="{ paused: status === 'paused', active: status === 'recording' }">
          <span class="status-dot" />
          <strong>{{ status === 'recording' ? '正在录制' : status === 'paused' ? '已暂停' : status === 'finalizing' ? '正在生成 MP4' : '尚未开始录制' }}</strong>
          <time>{{ formattedDuration }}</time>
          <span>{{ formattedSize }}</span>
          <span>{{ sourcePixels.width }} × {{ sourcePixels.height }}</span>
        </div>
        <div class="recording-toolbar">
          <div>
            <strong>{{ isCapturing ? '录制区域已锁定' : '拖动边框调整录制范围' }}</strong>
            <span>{{ sourcePixels.width }} × {{ sourcePixels.height }} 像素 · 保存到 {{ saveDirectoryName }}</span>
          </div>
          <button class="secondary-button compact-button" type="button" :disabled="isCapturing" @click="resetSelection">重置为全部画面</button>
          <button class="secondary-button compact-button" type="button" :disabled="isCapturing" @click="chooseSaveDirectory">更改保存文件夹</button>
        </div>
        <div ref="selectionStage" class="recording-stage">
          <video ref="preview" muted playsinline @loadedmetadata="sourceMetadataReady" />
          <div v-if="isCapturing" class="recording-preview-cover">
            <span class="recording-live-dot" />
            <strong>正在录制{{ sourceLabel }}</strong>
            <p v-if="displaySurface === 'monitor'">现在可以切换到其他浏览器或程序，整个桌面的变化都会录入。</p>
            <p v-else>当前只会录制{{ sourceLabel }}；如需跨程序录制，请重新选择“整个屏幕”。</p>
            <time>{{ formattedDuration }}</time>
          </div>
          <div class="selection-mask" :class="{ locked: isCapturing }" :style="selectionStyle"
            @pointerdown="beginSelectionDrag($event, 'move')">
            <span class="selection-size">{{ sourcePixels.width }} × {{ sourcePixels.height }}</span>
            <button v-for="handle in (['n', 'ne', 'e', 'se', 's', 'sw', 'w', 'nw'] as SelectionHandle[])"
              :key="handle" type="button" class="selection-handle" :class="`handle-${handle}`"
              :aria-label="`调整 ${handle} 边界`" @pointerdown.stop="beginSelectionDrag($event, handle)" />
          </div>
        </div>
        <div v-if="status === 'recording' || status === 'paused' || status === 'finalizing'"
          class="recording-bottom-timer" :class="{ paused: status === 'paused' }" aria-live="polite">
          <span>{{ status === 'finalizing' ? '录制完成' : status === 'paused' ? '已暂停' : '已录制' }}</span>
          <strong>{{ elapsedSeconds }}</strong>
          <span>秒</span>
          <time :datetime="`PT${elapsedSeconds}S`">{{ formattedDuration }}</time>
        </div>
        <div class="recording-actions">
          <button v-if="status === 'ready'" class="primary-button record-button" type="button" :disabled="!canStart" @click="startRecording">3. 开始录制（点击后开始计时）</button>
          <button v-if="status === 'recording'" class="secondary-button" type="button" @click="pauseRecording">暂停</button>
          <button v-if="status === 'paused'" class="secondary-button" type="button" @click="resumeRecording">继续</button>
          <button v-if="status === 'recording' || status === 'paused'" class="primary-button stop-button" type="button" @click="stopRecording">停止并保存</button>
          <button v-if="status === 'finalizing'" class="primary-button" type="button" disabled><span class="spinner" />正在生成并保存 MP4…</button>
          <button v-if="!isCapturing" class="text-button" type="button" @click="chooseSource">重新选择来源</button>
        </div>
      </template>
    </section>
    <canvas ref="cropCanvas" class="recording-canvas" aria-hidden="true" />
  </div>
</template>

<style scoped>
.recording-panel{padding:24px}.recording-empty{min-height:420px;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center}.recording-icon{width:76px;height:76px;display:grid;place-items:center;border-radius:24px;color:#fff;background:#d7463e;box-shadow:0 16px 32px rgba(215,70,62,.2);font-size:15px;font-weight:800}.recording-empty h2{margin:22px 0 8px}.recording-empty p{margin:0 0 18px;color:var(--muted);font-size:13px}.browser-warning{margin-bottom:16px;padding:10px 14px;border-radius:10px;color:#a63630;background:#fff0ee;font-size:12px}.recording-setup-actions{display:flex;align-items:center;justify-content:center;flex-wrap:wrap;gap:10px}.save-file-name{width:100%;color:var(--teal);font-size:12px;font-weight:600}.recording-status-strip{margin-bottom:14px;padding:12px 16px;display:flex;align-items:center;gap:12px;border:1px solid #d9e0eb;border-radius:14px;color:#4e5d75;background:#f7f9fc}.recording-status-strip.active{color:#a92f29;border-color:#f0b5b1;background:#fff3f2}.recording-status-strip.paused{color:#845b13;border-color:#ead39f;background:#fff9e9}.status-dot{width:11px;height:11px;border-radius:50%;background:#94a0b3;box-shadow:0 0 0 5px rgba(148,160,179,.12)}.active .status-dot{background:#dc3f37;box-shadow:0 0 0 5px rgba(220,63,55,.12);animation:pulse 1.3s infinite}.paused .status-dot{background:#d49a25;animation:none}.recording-status-strip time{font-size:28px;font-weight:800;font-variant-numeric:tabular-nums;letter-spacing:1px}.recording-status-strip>span:not(.status-dot){color:var(--muted);font-size:11px}.recording-toolbar{margin-bottom:14px;display:flex;align-items:center;justify-content:space-between;gap:10px}.recording-toolbar>div{display:grid;gap:4px;margin-right:auto}.recording-toolbar span{color:var(--muted);font-size:11px}.recording-stage{position:relative;width:100%;overflow:hidden;border-radius:16px;background:#111827;user-select:none;touch-action:none}.recording-stage video{width:100%;max-height:68vh;display:block;object-fit:contain}.recording-preview-cover{position:absolute;inset:0;z-index:4;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:24px;text-align:center;color:#fff;background:linear-gradient(145deg,#111827,#1d2940)}.recording-preview-cover strong{margin-top:18px;font-size:24px}.recording-preview-cover p{max-width:520px;margin:10px 0;color:#cbd5e1;font-size:13px}.recording-preview-cover time{font-size:42px;font-weight:800;font-variant-numeric:tabular-nums;letter-spacing:2px}.recording-live-dot{width:18px;height:18px;border-radius:50%;background:#e34f46;box-shadow:0 0 0 8px rgba(227,79,70,.14);animation:pulse 1.3s infinite}.selection-mask{position:absolute;z-index:2;border:2px solid #4b8cff;background:rgba(43,103,209,.08);box-shadow:0 0 0 9999px rgba(3,8,18,.58);cursor:move}.selection-mask.locked{border-color:#e34f46;cursor:default}.selection-size{position:absolute;left:8px;top:8px;padding:4px 7px;border-radius:6px;color:#fff;background:rgba(10,20,38,.72);font-size:10px;pointer-events:none}.selection-handle{position:absolute;width:13px;height:13px;padding:0;border:2px solid #fff;border-radius:50%;background:#2b67d1}.locked .selection-handle{display:none}.handle-n{left:50%;top:-7px;transform:translateX(-50%);cursor:ns-resize}.handle-ne{right:-7px;top:-7px;cursor:nesw-resize}.handle-e{right:-7px;top:50%;transform:translateY(-50%);cursor:ew-resize}.handle-se{right:-7px;bottom:-7px;cursor:nwse-resize}.handle-s{left:50%;bottom:-7px;transform:translateX(-50%);cursor:ns-resize}.handle-sw{left:-7px;bottom:-7px;cursor:nesw-resize}.handle-w{left:-7px;top:50%;transform:translateY(-50%);cursor:ew-resize}.handle-nw{left:-7px;top:-7px;cursor:nwse-resize}.recording-actions{min-height:58px;padding-top:16px;display:flex;align-items:center;justify-content:center;gap:10px}.record-button,.stop-button{background:#d7463e}.record-button:hover:not(:disabled),.stop-button:hover:not(:disabled){background:#ba342d}.recording-success{margin-bottom:16px;padding:13px 15px;border:1px solid #b8dfd5;border-radius:13px;color:#087567;background:#edfaf7;font-size:13px;font-weight:600}.recording-canvas{position:fixed;width:1px;height:1px;left:-10px;top:-10px;opacity:0;pointer-events:none}@keyframes pulse{50%{transform:scale(.75);opacity:.65}}@media(max-width:640px){.recording-panel{padding:12px}.recording-empty{min-height:340px}.recording-status-strip{flex-wrap:wrap}.recording-status-strip time{font-size:22px}.recording-toolbar{align-items:flex-start;flex-wrap:wrap}.recording-toolbar .secondary-button{padding-inline:10px;font-size:10px}.recording-actions{flex-wrap:wrap}}
.recording-bottom-timer{width:max-content;margin:16px auto 0;padding:8px 16px;display:flex;align-items:baseline;gap:6px;border:1px solid #f0b5b1;border-radius:999px;color:#a92f29;background:#fff3f2;font-size:13px;font-weight:600}.recording-bottom-timer.paused{color:#845b13;border-color:#ead39f;background:#fff9e9}.recording-bottom-timer strong{font-size:24px;font-variant-numeric:tabular-nums}.recording-bottom-timer time{margin-left:6px;color:var(--muted);font-size:12px;font-variant-numeric:tabular-nums}.recording-bottom-timer+.recording-actions{padding-top:10px}
</style>
