import { uploadForImageCompression, type ImageCompressionResult } from '../../services/api'
import { chooseCompressionImage, showError } from '../../utils/image'

function formatSize(bytes: number): string {
  return bytes < 1024 * 1024
    ? `${(bytes / 1024).toFixed(1)}KB`
    : `${(bytes / 1024 / 1024).toFixed(2)}MB`
}

Page({
  data: {
    imagePath: '',
    preset: 'balanced',
    targetSizeKb: '',
    loading: false,
    result: null as ImageCompressionResult | null,
    originalSizeText: '',
    outputSizeText: '',
    resultHint: ''
  },
  async chooseImage() {
    try {
      const image = await chooseCompressionImage()
      this.setData({ imagePath: image.path, result: null, originalSizeText: '', outputSizeText: '', resultHint: '' })
    } catch (error) {
      showError(error)
    }
  },
  selectPreset(event: { currentTarget: { dataset: { preset: string } } }) {
    this.setData({ preset: event.currentTarget.dataset.preset, result: null })
  },
  selectTargetSize(event: { currentTarget: { dataset: { size: number } } }) {
    this.setData({
      preset: 'custom',
      targetSizeKb: String(event.currentTarget.dataset.size),
      result: null,
      originalSizeText: '',
      outputSizeText: '',
      resultHint: ''
    })
  },
  onTargetInput(event: { detail: { value: string } }) {
    this.setData({ targetSizeKb: event.detail.value })
  },
  async compress() {
    if (!this.data.imagePath || this.data.loading) return
    this.setData({ loading: true })
    try {
      const target = this.data.preset === 'custom' ? Number(this.data.targetSizeKb) || undefined : undefined
      const result = await uploadForImageCompression(this.data.imagePath, this.data.preset, target)
      this.setData({
        result,
        originalSizeText: formatSize(result.originalSize),
        outputSizeText: formatSize(result.outputSize),
        resultHint: result.skipped
          ? '原图已经接近最优'
          : `压缩率 ${result.ratio}% · ${result.format.toUpperCase()}`
      })
    } catch (error) {
      showError(error)
    } finally {
      this.setData({ loading: false })
    }
  },
  saveResult() {
    const result = this.data.result
    if (!result) return
    wx.saveImageToPhotosAlbum({
      filePath: result.path,
      success: () => wx.showToast({ title: '已保存到相册', icon: 'success' }),
      fail: error => {
        if (!error.errMsg.includes('cancel')) showError(new Error('保存失败，请检查相册权限'))
      }
    })
  }
})
