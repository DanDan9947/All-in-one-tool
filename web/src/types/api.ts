export interface ApiEnvelope<T> {
  success: boolean
  data: T
  code?: string
  message?: string
  requestId: string
}

export class ApiError extends Error {
  readonly code: string
  readonly requestId?: string
  readonly status: number

  constructor(message: string, code = 'REQUEST_FAILED', status = 0, requestId?: string) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
    this.requestId = requestId
  }
}

export interface OcrLine {
  text: string
  score: number
}

export interface OcrResult {
  text: string
  lines: OcrLine[]
}

export interface ExcelHeaderSheet {
  sheetName: string
  headerRow: number
  columnCount: number
  headers: string[]
  originalHeaders: string[]
  previewRows: string[][]
}

export interface ExcelHeaderResult {
  fileName: string
  sheetCount: number
  sheets: ExcelHeaderSheet[]
}

export type PdfOutputFormat = 'xlsx' | 'docx'

export interface PdfConversionResult {
  token: string
  fileName: string
  format: PdfOutputFormat
  expiresAt: string
}

export interface ScreenRecordingSession {
  recordingId: string
  chunkIntervalMs: number
}

export interface ScreenRecordingChunkResult {
  nextSequence: number
  sizeBytes: number
}

export interface ScreenRecordingResult {
  token: string
  fileName: string
  format: 'mp4'
  sizeBytes: number
  expiresAt: string
}

export type CompressionPreset = 'small' | 'balanced' | 'high' | 'custom'
export type ImageOutputFormat = 'auto' | 'jpeg' | 'webp' | 'png'

export interface ImageCompressionOptions {
  preset: CompressionPreset
  maxDimension?: number
  quality?: number
  targetSizeKb?: number
  outputFormat: ImageOutputFormat
}

export interface ImageCompressionResult {
  blob: Blob
  fileName: string
  originalSize: number
  outputSize: number
  width: number
  height: number
  format: string
  ratio: number
  skipped: boolean
  targetReached: boolean
}

export type VideoCompressionStatus =
  | 'queued'
  | 'processing'
  | 'completed'
  | 'failed'
  | 'cancelled'

export interface VideoCompressionOptions {
  preset: CompressionPreset
  maxHeight?: number
  crf?: number
  targetSizeMb?: number
}

export interface VideoCompressionJob {
  jobId: string
  status: VideoCompressionStatus
  progress: number
  fileName: string
  originalSize: number
  outputSize?: number
  durationSeconds?: number
  token?: string
  expiresAt?: string
  errorCode?: string
  errorMessage?: string
}
