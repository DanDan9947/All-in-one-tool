import {
  ApiError,
  type ApiEnvelope,
  type OcrResult,
  type PdfConversionResult,
  type PdfOutputFormat,
  type ScreenRecordingSession,
  type ScreenRecordingChunkResult,
  type ScreenRecordingResult,
  type ImageCompressionOptions,
  type ImageCompressionResult,
  type VideoCompressionOptions,
  type VideoCompressionJob,
  type ExcelHeaderResult
} from '../types/api'

const API_ROOT = '/api/v1'

interface ErrorPayload {
  code?: string
  message?: string
  requestId?: string
}

export function apiErrorFromPayload(
  payload: string,
  status: number,
  fallbackRequestId?: string | null
): ApiError {
  try {
    const body = JSON.parse(payload) as ErrorPayload
    return new ApiError(
      body.message || defaultMessage(status),
      body.code || 'REQUEST_FAILED',
      status,
      body.requestId || fallbackRequestId || undefined
    )
  } catch {
    return new ApiError(
      defaultMessage(status),
      'REQUEST_FAILED',
      status,
      fallbackRequestId || undefined
    )
  }
}

async function responseError(response: Response): Promise<ApiError> {
  const payload = await response.text()
  return apiErrorFromPayload(payload, response.status, response.headers.get('X-Request-Id'))
}

function defaultMessage(status: number): string {
  if (status === 413) return '文件超过 10MB，请压缩后重试'
  if (status === 415) return '暂不支持这种文件格式'
  if (status === 503) return '当前使用人数较多，请稍后重试'
  return '处理失败，请稍后重试'
}

async function postFile<T>(endpoint: string, file: File): Promise<T> {
  const form = new FormData()
  form.append('file', file, file.name)
  let response: Response
  try {
    response = await fetch(`${API_ROOT}${endpoint}`, { method: 'POST', body: form })
  } catch {
    throw new ApiError('无法连接本机处理服务，请确认“蛋蛋小工具”仍在运行', 'LOCAL_SERVICE_ERROR')
  }
  if (!response.ok) throw await responseError(response)
  const envelope = (await response.json()) as ApiEnvelope<T>
  return envelope.data
}

async function postImageForBlob(endpoint: string, file: File): Promise<Blob> {
  const form = new FormData()
  form.append('file', file, file.name)
  let response: Response
  try {
    response = await fetch(`${API_ROOT}${endpoint}`, { method: 'POST', body: form })
  } catch {
    throw new ApiError('无法连接本机处理服务，请确认“蛋蛋小工具”仍在运行', 'LOCAL_SERVICE_ERROR')
  }
  if (!response.ok) throw await responseError(response)
  return response.blob()
}

export function uploadForOcr(file: File): Promise<OcrResult> {
  return postFile<OcrResult>('/ocr', file)
}

export function uploadForExcelHeaders(file: File): Promise<ExcelHeaderResult> {
  return postFile<ExcelHeaderResult>('/excel-headers', file)
}

export function uploadForCutout(file: File): Promise<Blob> {
  return postImageForBlob('/cutout', file)
}

export function uploadForInkCutout(file: File, threshold: number): Promise<Blob> {
  return postImageForBlob(`/ink-cutout?threshold=${encodeURIComponent(threshold)}`, file)
}

export function uploadPdfForConversion(
  file: File,
  outputFormat: PdfOutputFormat,
  onProgress?: (progress: number) => void
): Promise<PdfConversionResult> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest()
    const form = new FormData()
    form.append('file', file, file.name)
    form.append('outputFormat', outputFormat)

    request.open('POST', `${API_ROOT}/pdf-conversions`)
    request.timeout = 180_000
    request.upload.onprogress = event => {
      if (event.lengthComputable) {
        onProgress?.(Math.round((event.loaded / event.total) * 100))
      }
    }
    request.onerror = () =>
      reject(new ApiError('无法连接本机处理服务，请确认“蛋蛋小工具”仍在运行', 'LOCAL_SERVICE_ERROR'))
    request.ontimeout = () =>
      reject(new ApiError('转换时间较长，请稍后重试', 'REQUEST_TIMEOUT'))
    request.onload = () => {
      if (request.status < 200 || request.status >= 300) {
        reject(
          apiErrorFromPayload(
            request.responseText,
            request.status,
            request.getResponseHeader('X-Request-Id')
          )
        )
        return
      }
      try {
        const envelope = JSON.parse(
          request.responseText
        ) as ApiEnvelope<PdfConversionResult>
        resolve(envelope.data)
      } catch {
        reject(new ApiError('本机处理程序返回了无法识别的结果', 'INVALID_RESPONSE'))
      }
    }
    request.send(form)
  })
}

export async function downloadPdfConversion(token: string): Promise<Blob> {
  let response: Response
  try {
    response = await fetch(
      `${API_ROOT}/pdf-conversions/${encodeURIComponent(token)}/download`
    )
  } catch {
    throw new ApiError('无法读取本机转换结果，请确认“蛋蛋小工具”仍在运行', 'LOCAL_SERVICE_ERROR')
  }
  if (!response.ok) throw await responseError(response)
  return response.blob()
}

async function jsonRequest<T>(url: string, init: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(url, init)
  } catch {
    throw new ApiError('无法连接本机服务，请确认程序仍在运行', 'NETWORK_ERROR')
  }
  if (!response.ok) throw await responseError(response)
  const envelope = (await response.json()) as ApiEnvelope<T>
  return envelope.data
}

export function createScreenRecording(mimeType: string): Promise<ScreenRecordingSession> {
  return jsonRequest(`${API_ROOT}/screen-recordings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mimeType })
  })
}

export async function uploadScreenRecordingChunk(
  recordingId: string,
  sequence: number,
  chunk: Blob
): Promise<ScreenRecordingChunkResult> {
  let lastError: unknown
  for (let attempt = 0; attempt < 3; attempt += 1) {
    try {
      return await jsonRequest(
        `${API_ROOT}/screen-recordings/${encodeURIComponent(recordingId)}/chunks/${sequence}`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/octet-stream' },
          body: chunk
        }
      )
    } catch (error) {
      lastError = error
      if (error instanceof ApiError && error.status > 0 && error.status < 500) throw error
      await new Promise(resolve => window.setTimeout(resolve, 300 * (attempt + 1)))
    }
  }
  throw lastError
}

export function completeScreenRecording(
  recordingId: string,
  fileName: string,
  durationSeconds: number
): Promise<ScreenRecordingResult> {
  return jsonRequest(
    `${API_ROOT}/screen-recordings/${encodeURIComponent(recordingId)}/complete`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fileName, durationSeconds })
    }
  )
}

export async function cancelScreenRecording(recordingId: string): Promise<void> {
  try {
    await fetch(`${API_ROOT}/screen-recordings/${encodeURIComponent(recordingId)}`, {
      method: 'DELETE',
      keepalive: true
    })
  } catch {
    // The server cleans abandoned recordings if the local app exits unexpectedly.
  }
}

export function screenRecordingDownloadUrl(token: string): string {
  return `${API_ROOT}/screen-recordings/${encodeURIComponent(token)}/download`
}

export async function deleteScreenRecordingResult(token: string): Promise<void> {
  await jsonRequest(
    `${API_ROOT}/screen-recordings/results/${encodeURIComponent(token)}`,
    { method: 'DELETE' }
  )
}

function fileNameFromDisposition(disposition: string | null, fallback: string): string {
  const encoded = disposition?.match(/filename\*=UTF-8''([^;]+)/i)?.[1]
  if (!encoded) return fallback
  try {
    return decodeURIComponent(encoded)
  } catch {
    return fallback
  }
}

export async function compressImage(
  file: File,
  options: ImageCompressionOptions
): Promise<ImageCompressionResult> {
  const form = new FormData()
  form.append('file', file, file.name)
  form.append('preset', options.preset)
  form.append('outputFormat', options.outputFormat)
  if (options.maxDimension) form.append('maxDimension', String(options.maxDimension))
  if (options.quality) form.append('quality', String(options.quality))
  if (options.targetSizeKb) form.append('targetSizeKb', String(options.targetSizeKb))
  let response: Response
  try {
    response = await fetch(`${API_ROOT}/image-compressions`, { method: 'POST', body: form })
  } catch {
    throw new ApiError('无法连接图片压缩服务', 'LOCAL_SERVICE_ERROR')
  }
  if (!response.ok) throw await responseError(response)
  const blob = await response.blob()
  return {
    blob,
    fileName: fileNameFromDisposition(
      response.headers.get('Content-Disposition'),
      `${file.name.replace(/\.[^.]+$/, '')}-compressed.jpg`
    ),
    originalSize: Number(response.headers.get('X-Original-Size')) || file.size,
    outputSize: Number(response.headers.get('X-Output-Size')) || blob.size,
    width: Number(response.headers.get('X-Image-Width')),
    height: Number(response.headers.get('X-Image-Height')),
    format: response.headers.get('X-Output-Format') || 'image',
    ratio: Number(response.headers.get('X-Compression-Ratio')) || 0,
    skipped: response.headers.get('X-Compression-Skipped') === 'true',
    targetReached: response.headers.get('X-Target-Reached') !== 'false'
  }
}

export function createVideoCompression(
  file: File,
  options: VideoCompressionOptions,
  onProgress?: (progress: number) => void
): Promise<VideoCompressionJob> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest()
    const form = new FormData()
    form.append('file', file, file.name)
    form.append('preset', options.preset)
    if (options.maxHeight) form.append('maxHeight', String(options.maxHeight))
    if (options.crf) form.append('crf', String(options.crf))
    if (options.targetSizeMb) form.append('targetSizeMb', String(options.targetSizeMb))
    request.open('POST', `${API_ROOT}/video-compressions`)
    request.timeout = 30 * 60 * 1000
    request.upload.onprogress = event => {
      if (event.lengthComputable) onProgress?.(Math.round((event.loaded / event.total) * 100))
    }
    request.onerror = () => reject(new ApiError('无法连接视频压缩服务', 'LOCAL_SERVICE_ERROR'))
    request.ontimeout = () => reject(new ApiError('视频上传超时', 'REQUEST_TIMEOUT'))
    request.onload = () => {
      if (request.status < 200 || request.status >= 300) {
        reject(apiErrorFromPayload(request.responseText, request.status))
        return
      }
      resolve((JSON.parse(request.responseText) as ApiEnvelope<VideoCompressionJob>).data)
    }
    request.send(form)
  })
}

export function getVideoCompression(jobId: string): Promise<VideoCompressionJob> {
  return jsonRequest(`${API_ROOT}/video-compressions/${encodeURIComponent(jobId)}`, {
    method: 'GET'
  })
}

export function videoCompressionDownloadUrl(token: string): string {
  return `${API_ROOT}/video-compressions/results/${encodeURIComponent(token)}`
}

export async function cancelVideoCompression(jobId: string): Promise<void> {
  await fetch(`${API_ROOT}/video-compressions/${encodeURIComponent(jobId)}`, {
    method: 'DELETE',
    keepalive: true
  })
}
