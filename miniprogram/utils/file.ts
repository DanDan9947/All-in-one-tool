const MAX_PDF_BYTES = 10 * 1024 * 1024

export interface SelectedPdf {
  path: string
  name: string
  size: number
}

export function chooseSinglePdf(): Promise<SelectedPdf | null> {
  return new Promise((resolve, reject) => {
    wx.chooseMessageFile({
      count: 1,
      type: 'file',
      extension: ['pdf'],
      success(result) {
        const file = result.tempFiles[0]
        if (!file) {
          reject(new Error('没有选择 PDF 文件'))
          return
        }
        if (!file.name.toLowerCase().endsWith('.pdf')) {
          reject(new Error('请选择 PDF 文件'))
          return
        }
        if (file.size > MAX_PDF_BYTES) {
          reject(new Error('PDF 不能超过 10MB'))
          return
        }
        resolve({
          path: file.path,
          name: file.name,
          size: file.size
        })
      },
      fail(error) {
        if (error.errMsg.includes('cancel')) {
          resolve(null)
          return
        }
        reject(new Error('选择 PDF 文件失败'))
      }
    })
  })
}

export function formatFileSize(size: number): string {
  if (size < 1024 * 1024) {
    return `${Math.max(1, Math.round(size / 1024))} KB`
  }
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}
