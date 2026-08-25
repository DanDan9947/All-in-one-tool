import { describe, expect, it } from 'vitest'

import { ApiError } from '../types/api'
import {
  MAX_FILE_BYTES,
  formatFileSize,
  validateExcelFile,
  validateImageFile,
  validatePdfFile
} from './files'

describe('file validation', () => {
  it('accepts supported images and PDFs', () => {
    const image = new File(['image'], 'portrait.webp', { type: 'image/webp' })
    const pdf = new File(['pdf'], 'report.pdf', { type: 'application/pdf' })

    expect(validateImageFile(image)).toBe(image)
    expect(validatePdfFile(pdf)).toBe(pdf)
  })

  it('accepts Excel formats and rejects unrelated files', () => {
    const legacy = new File(['excel'], 'SMP061.xls')
    const modern = new File(['excel'], 'report.xlsx')
    const csv = new File(['a,b'], 'report.csv', { type: 'text/csv' })

    expect(validateExcelFile(legacy)).toBe(legacy)
    expect(validateExcelFile(modern)).toBe(modern)
    expect(validateExcelFile(csv)).toBe(csv)
    expect(() => validateExcelFile(new File(['text'], 'report.txt'))).toThrow('请选择 XLS、XLSX 或 CSV')
  })

  it('rejects unsupported and oversized files', () => {
    const text = new File(['text'], 'notes.txt', { type: 'text/plain' })
    const large = new File([new Uint8Array(MAX_FILE_BYTES + 1)], 'large.png', {
      type: 'image/png'
    })

    expect(() => validateImageFile(text)).toThrow(ApiError)
    expect(() => validateImageFile(large)).toThrow('文件超过 10MB')
  })

  it('formats file sizes for the UI', () => {
    expect(formatFileSize(512)).toBe('512 B')
    expect(formatFileSize(1536)).toBe('1.5 KB')
    expect(formatFileSize(2 * 1024 * 1024)).toBe('2.0 MB')
  })
})
