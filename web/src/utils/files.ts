import { ApiError } from '../types/api'

export const MAX_FILE_BYTES = 10 * 1024 * 1024
export const MAX_IMAGE_COMPRESSION_BYTES = 50 * 1024 * 1024
export const MAX_VIDEO_BYTES = 2 * 1024 * 1024 * 1024
export const MAX_EXCEL_BYTES = 50 * 1024 * 1024

const IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp']
const IMAGE_MIME_TYPES = ['image/jpeg', 'image/png', 'image/webp']

function extensionAllowed(file: File, extensions: string[]): boolean {
  const lower = file.name.toLowerCase()
  return extensions.some(extension => lower.endsWith(extension))
}

function validateSize(file: File): void {
  if (file.size === 0) throw new ApiError('文件内容为空，请重新选择', 'EMPTY_FILE')
  if (file.size > MAX_FILE_BYTES) {
    throw new ApiError('文件超过 10MB，请压缩后重试', 'FILE_TOO_LARGE', 413)
  }
}

function validateSizeLimit(file: File, limit: number, label: string): void {
  if (file.size === 0) throw new ApiError('文件内容为空，请重新选择', 'EMPTY_FILE')
  if (file.size > limit) throw new ApiError(`${label}超过大小限制`, 'FILE_TOO_LARGE', 413)
}

export function validateImageFile(file: File): File {
  validateSize(file)
  if (
    !IMAGE_MIME_TYPES.includes(file.type.toLowerCase()) &&
    !extensionAllowed(file, IMAGE_EXTENSIONS)
  ) {
    throw new ApiError('请选择 JPG、PNG 或 WebP 图片', 'INVALID_IMAGE_TYPE', 415)
  }
  return file
}

export function validatePdfFile(file: File): File {
  validateSize(file)
  if (file.type.toLowerCase() !== 'application/pdf' && !extensionAllowed(file, ['.pdf'])) {
    throw new ApiError('请选择 PDF 文件', 'INVALID_PDF', 415)
  }
  return file
}

export function validateExcelFile(file: File): File {
  validateSizeLimit(file, MAX_EXCEL_BYTES, 'Excel 文件')
  if (!extensionAllowed(file, ['.xls', '.xlsx', '.csv'])) {
    throw new ApiError('请选择 XLS、XLSX 或 CSV 文件', 'INVALID_EXCEL', 415)
  }
  return file
}

export function validateCompressionImageFile(file: File): File {
  validateSizeLimit(file, MAX_IMAGE_COMPRESSION_BYTES, '图片')
  if (
    !IMAGE_MIME_TYPES.includes(file.type.toLowerCase()) &&
    !extensionAllowed(file, IMAGE_EXTENSIONS)
  ) {
    throw new ApiError('请选择 JPG、PNG 或 WebP 图片', 'INVALID_IMAGE_TYPE', 415)
  }
  return file
}

export function validateVideoFile(file: File): File {
  validateSizeLimit(file, MAX_VIDEO_BYTES, '视频')
  if (!extensionAllowed(file, ['.mp4', '.mov', '.mkv', '.webm'])) {
    throw new ApiError('请选择 MP4、MOV、MKV 或 WebM 视频', 'INVALID_VIDEO_TYPE', 415)
  }
  return file
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

export function triggerDownload(blob: Blob, fileName: string): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = fileName
  link.style.display = 'none'
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 0)
}
