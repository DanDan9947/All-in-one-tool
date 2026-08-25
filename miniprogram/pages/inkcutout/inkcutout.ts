import { uploadForInkCutout } from '../../services/api'
import { chooseSingleImage, showError } from '../../utils/image'

Page({
  data: {
    imagePath: '',
    resultPath: '',
    threshold: 18,
    loading: false
  },
  async chooseImage() {
    try {
      const image = await chooseSingleImage()
      this.setData({ imagePath: image.path, resultPath: '' })
    } catch (error) {
      showError(error)
    }
  },
  onThresholdChange(event: any) {
    this.setData({ threshold: Number(event.detail.value) })
  },
  async processImage() {
    if (!this.data.imagePath || this.data.loading) return
    this.setData({ loading: true })
    try {
      const path = await uploadForInkCutout(this.data.imagePath, this.data.threshold)
      this.setData({ resultPath: path })
    } catch (error) {
      showError(error)
    } finally {
      this.setData({ loading: false })
    }
  },
  saveResult() {
    if (!this.data.resultPath) return
    wx.saveImageToPhotosAlbum({
      filePath: this.data.resultPath,
      success: () => wx.showToast({ title: '已保存' }),
      fail: error => {
        if (error.errMsg.includes('auth deny') || error.errMsg.includes('auth denied')) {
          wx.showModal({
            title: '需要相册权限',
            content: '请在设置中允许保存图片到相册。',
            confirmText: '去设置',
            success: result => result.confirm && wx.openSetting({})
          })
          return
        }
        showError(new Error('保存图片失败'))
      }
    })
  }
})
