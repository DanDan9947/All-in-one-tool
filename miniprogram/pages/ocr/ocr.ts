import { uploadForOcr } from '../../services/api'
import { chooseSingleImage, showError } from '../../utils/image'

Page({
  data: {
    imagePath: '',
    resultText: '',
    loading: false
  },
  async chooseImage() {
    try {
      const image = await chooseSingleImage()
      this.setData({ imagePath: image.path, resultText: '' })
    } catch (error) {
      showError(error)
    }
  },
  async recognize() {
    if (!this.data.imagePath || this.data.loading) return
    this.setData({ loading: true })
    try {
      const result = await uploadForOcr(this.data.imagePath)
      this.setData({ resultText: result.text })
    } catch (error) {
      showError(error)
    } finally {
      this.setData({ loading: false })
    }
  },
  copyText() {
    if (!this.data.resultText) return
    wx.setClipboardData({ data: this.data.resultText })
  }
})
