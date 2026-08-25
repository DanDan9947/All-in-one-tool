import { API_BASE_URL } from '../config'

export interface OcrLine {
  text: string
  score: number
}

export interface OcrResult {
  text: string
  lines: OcrLine[]
}

interface ApiEnvelope<T> {
  success: boolean
  data: T
  code?: string
  message?: string
  requestId: string
}

export type PdfOutputFormat = 'xlsx' | 'docx'

export interface PdfConversionResult {
  token: string
  fileName: string
  format: PdfOutputFormat
  expiresAt: string
}

export interface ImageCompressionResult {
  path: string
  originalSize: number
  outputSize: number
  format: string
  ratio: number
  skipped: boolean
  targetReached: boolean
}

function messageFromPayload(payload: string): string {
  try {
    const body = JSON.parse(payload)
    return body.message || '处理失败，请稍后重试'
  } catch (_) {
    return '处理失败，请稍后重试'
  }
}

export function uploadForOcr(filePath: string): Promise<OcrResult> {
  return new Promise((resolve, reject) => {
    wx.uploadFile({
      url: `${API_BASE_URL}/api/v1/ocr`,
      filePath,
      name: 'file',
      timeout: 60000,
      success(response) {
        if (response.statusCode < 200 || response.statusCode >= 300) {
          reject(new Error(messageFromPayload(response.data)))
          return
        }
        try {
          const body = JSON.parse(response.data) as ApiEnvelope<OcrResult>
          resolve(body.data)
        } catch (_) {
          reject(new Error('服务器返回格式不正确'))
        }
      },
      fail(error) {
        reject(new Error(error.errMsg || '网络请求失败'))
      }
    })
  })
}

export function uploadForCutout(filePath: string): Promise<string> {
  return uploadForPngResult(filePath, '/api/v1/cutout', 'cutout', '抠图失败，请稍后重试')
}

export function uploadForInkCutout(filePath: string, threshold: number): Promise<string> {
  return uploadForPngResult(
    filePath,
    `/api/v1/ink-cutout?threshold=${threshold}`,
    'ink-cutout',
    '文字抠图失败，请稍后重试'
  )
}

export function uploadForImageCompression(
  filePath: string,
  preset: string,
  targetSizeKb?: number
): Promise<ImageCompressionResult> {
  const fileSystem = wx.getFileSystemManager()
  return new Promise((resolve, reject) => {
    fileSystem.readFile({
      filePath,
      success(readResult) {
        const query = [
          `preset=${encodeURIComponent(preset)}`,
          'outputFormat=auto',
          targetSizeKb ? `targetSizeKb=${targetSizeKb}` : ''
        ].filter(Boolean).join('&')
        wx.request({
          url: `${API_BASE_URL}/api/v1/image-compressions?${query}`,
          method: 'POST',
          data: readResult.data,
          header: { 'Content-Type': contentTypeFor(filePath) },
          responseType: 'arraybuffer',
          timeout: 120000,
          success(response) {
            if (response.statusCode < 200 || response.statusCode >= 300) {
              reject(new Error('图片压缩失败，请稍后重试'))
              return
            }
            const headers = response.header || {}
            const value = (name: string) => String(headers[name] || headers[name.toLowerCase()] || '')
            const format = value('X-Output-Format') || 'jpeg'
            const extension = format === 'jpeg' ? 'jpg' : format
            const outputPath = `${wx.env.USER_DATA_PATH}/compressed-${Date.now()}.${extension}`
            fileSystem.writeFile({
              filePath: outputPath,
              data: response.data as ArrayBuffer,
              success: () => resolve({
                path: outputPath,
                originalSize: Number(value('X-Original-Size')),
                outputSize: Number(value('X-Output-Size')),
                format,
                ratio: Number(value('X-Compression-Ratio')),
                skipped: value('X-Compression-Skipped') === 'true',
                targetReached: value('X-Target-Reached') !== 'false'
              }),
              fail: () => reject(new Error('无法保存压缩结果'))
            })
          },
          fail: error => reject(new Error(error.errMsg || '网络请求失败'))
        })
      },
      fail: () => reject(new Error('无法读取所选图片'))
    })
  })
}

export function uploadPdfForConversion(
  filePath: string,
  outputFormat: PdfOutputFormat,
  onProgress?: (progress: number) => void
): Promise<PdfConversionResult> {
  return new Promise((resolve, reject) => {
    const task = wx.uploadFile({
      url: `${API_BASE_URL}/api/v1/pdf-conversions`,
      filePath,
      name: 'file',
      formData: { outputFormat },
      timeout: 180000,
      success(response) {
        if (response.statusCode < 200 || response.statusCode >= 300) {
          reject(new Error(messageFromPayload(response.data)))
          return
        }
        try {
          const body = JSON.parse(response.data) as ApiEnvelope<PdfConversionResult>
          resolve(body.data)
        } catch (_) {
          reject(new Error('服务器返回格式不正确'))
        }
      },
      fail(error) {
        reject(new Error(error.errMsg || 'PDF 上传失败'))
      }
    })
    if (onProgress) {
      task.onProgressUpdate(result => onProgress(result.progress))
    }
  })
}

export function downloadPdfConversion(
  token: string,
  outputFormat: PdfOutputFormat
): Promise<string> {
  const outputPath =
    `${wx.env.USER_DATA_PATH}/pdf-conversion-${Date.now()}.${outputFormat}`
  return new Promise((resolve, reject) => {
    wx.downloadFile({
      url: `${API_BASE_URL}/api/v1/pdf-conversions/${encodeURIComponent(token)}/download`,
      filePath: outputPath,
      timeout: 120000,
      success(response) {
        if (response.statusCode < 200 || response.statusCode >= 300) {
          reject(new Error('转换结果不存在或已过期，请重新转换'))
          return
        }
        resolve(response.filePath || outputPath)
      },
      fail(error) {
        reject(new Error(error.errMsg || '下载转换结果失败'))
      }
    })
  })
}

function uploadForPngResult(
  filePath: string,
  endpoint: string,
  outputPrefix: string,
  failureMessage: string
): Promise<string> {
  const fileSystem = wx.getFileSystemManager()
  return new Promise((resolve, reject) => {
    fileSystem.readFile({
      filePath,
      success(readResult) {
        wx.request({
          url: `${API_BASE_URL}${endpoint}`,
          method: 'POST',
          data: readResult.data,
          header: { 'Content-Type': contentTypeFor(filePath) },
          responseType: 'arraybuffer',
          timeout: 60000,
          success(response) {
            if (response.statusCode < 200 || response.statusCode >= 300) {
              reject(new Error(failureMessage))
              return
            }
            const outputPath = `${wx.env.USER_DATA_PATH}/${outputPrefix}-${Date.now()}.png`
            fileSystem.writeFile({
              filePath: outputPath,
              data: response.data as ArrayBuffer,
              success: () => resolve(outputPath),
              fail: () => reject(new Error('无法保存处理结果'))
            })
          },
          fail: error => reject(new Error(error.errMsg || '网络请求失败'))
        })
      },
      fail: () => reject(new Error('无法读取所选图片'))
    })
  })
}

function contentTypeFor(filePath: string): string {
  const lower = filePath.toLowerCase()
  if (lower.endsWith('.png')) return 'image/png'
  if (lower.endsWith('.webp')) return 'image/webp'
  return 'image/jpeg'
}
