const MAX_FILE_BYTES = 10 * 1024 * 1024
const MAX_COMPRESSION_FILE_BYTES = 50 * 1024 * 1024

export interface SelectedImage {
  path: string
  size: number
}

export function chooseSingleImage(): Promise<SelectedImage> {
  return chooseImageWithLimit(MAX_FILE_BYTES)
}

export function chooseCompressionImage(): Promise<SelectedImage> {
  return chooseImageWithLimit(MAX_COMPRESSION_FILE_BYTES)
}

function chooseImageWithLimit(maxFileBytes: number): Promise<SelectedImage> {
  return new Promise((resolve, reject) => {
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['album', 'camera'],
      sizeType: ['original'],
      success(result) {
        const file = result.tempFiles[0]
        if (!file) {
          reject(new Error('没有选择图片'))
          return
        }
        if (file.size > maxFileBytes) {
          reject(new Error(`图片不能超过 ${Math.round(maxFileBytes / 1024 / 1024)}MB`))
          return
        }
        resolve({ path: file.tempFilePath, size: file.size })
      },
      fail(error) {
        if (error.errMsg.includes('cancel')) return
        reject(new Error('选择图片失败'))
      }
    })
  })
}

export function showError(error: unknown): void {
  const message = error instanceof Error ? error.message : '操作失败，请稍后重试'
  wx.showToast({ title: message, icon: 'none', duration: 2500 })
}
