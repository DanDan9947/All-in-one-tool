import { uploadForCutout } from '../../services/api'
import { chooseSingleImage, showError } from '../../utils/image'

interface BackgroundSelection {
  key: string
  color: string
  label: string
  generation: number
}

let pendingBackground: BackgroundSelection | null = null
let processingBackground = false
let photoGeneration = 0
let paletteRect: { left: number; top: number; width: number; height: number } | null = null
let hueRect: { left: number; top: number; width: number; height: number } | null = null

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

function hsvToHex(hue: number, saturation: number, value: number): string {
  const h = ((hue % 360) + 360) % 360
  const chroma = value * saturation
  const x = chroma * (1 - Math.abs((h / 60) % 2 - 1))
  const match = value - chroma
  let red = 0
  let green = 0
  let blue = 0

  if (h < 60) [red, green, blue] = [chroma, x, 0]
  else if (h < 120) [red, green, blue] = [x, chroma, 0]
  else if (h < 180) [red, green, blue] = [0, chroma, x]
  else if (h < 240) [red, green, blue] = [0, x, chroma]
  else if (h < 300) [red, green, blue] = [x, 0, chroma]
  else [red, green, blue] = [chroma, 0, x]

  return `#${[red, green, blue]
    .map(channel => Math.round((channel + match) * 255).toString(16).padStart(2, '0'))
    .join('')}`.toUpperCase()
}

function pointFromTouchEvent(event: any): { x: number; y: number } | null {
  const touch = event.touches && event.touches[0]
  if (!touch) return null
  return {
    x: Number(touch.clientX ?? touch.pageX),
    y: Number(touch.clientY ?? touch.pageY)
  }
}

Page({
  data: {
    imagePath: '',
    transparentPath: '',
    resultPath: '',
    loading: false,
    compositing: false,
    selectedBackground: 'transparent',
    selectedBackgroundColor: '',
    customColor: '#F5C6D6',
    pickerHue: 340,
    pickerSaturation: 0.192,
    pickerValue: 0.961,
    pickerHueColor: '#FF0055',
    pickerX: 19.2,
    pickerY: 3.9,
    hueX: 94.4,
    saveButtonText: '保存透明 PNG',
    canvasWidth: 1,
    canvasHeight: 1
  },
  async chooseImage() {
    try {
      const image = await chooseSingleImage()
      photoGeneration += 1
      pendingBackground = null
      this.setData({
        imagePath: image.path,
        transparentPath: '',
        resultPath: '',
        selectedBackground: 'transparent',
        selectedBackgroundColor: '',
        saveButtonText: '保存透明 PNG'
      })
    } catch (error) {
      showError(error)
    }
  },
  async cutout() {
    if (!this.data.imagePath || this.data.loading) return
    this.setData({ loading: true })
    try {
      const path = await uploadForCutout(this.data.imagePath)
      photoGeneration += 1
      pendingBackground = null
      this.setData({
        transparentPath: path,
        resultPath: path,
        selectedBackground: 'transparent',
        selectedBackgroundColor: '',
        saveButtonText: '保存透明 PNG'
      })
    } catch (error) {
      showError(error)
    } finally {
      this.setData({ loading: false })
    }
  },
  selectBackground(event: any) {
    if (!this.data.transparentPath) return
    const { key, color, label } = event.currentTarget.dataset
    this.enqueueBackground(String(key), String(color || ''), String(label || ''))
  },
  onPaletteTouchStart(event: any) {
    const point = pointFromTouchEvent(event)
    if (!point) return
    this.createSelectorQuery().select('#colorPalette').boundingClientRect((rect: any) => {
      if (!rect) return
      paletteRect = rect
      this.updatePaletteColor(point)
    }).exec()
  },
  onPaletteTouchMove(event: any) {
    const point = pointFromTouchEvent(event)
    if (!point || !paletteRect) return
    this.updatePaletteColor(point)
  },
  updatePaletteColor(point: { x: number; y: number }) {
    if (!paletteRect) return
    const saturation = clamp((point.x - paletteRect.left) / paletteRect.width, 0, 1)
    const value = 1 - clamp((point.y - paletteRect.top) / paletteRect.height, 0, 1)
    this.setData({
      pickerSaturation: saturation,
      pickerValue: value,
      pickerX: saturation * 100,
      pickerY: (1 - value) * 100,
      customColor: hsvToHex(this.data.pickerHue, saturation, value)
    })
  },
  onHueTouchStart(event: any) {
    const point = pointFromTouchEvent(event)
    if (!point) return
    this.createSelectorQuery().select('#huePicker').boundingClientRect((rect: any) => {
      if (!rect) return
      hueRect = rect
      this.updateHueColor(point)
    }).exec()
  },
  onHueTouchMove(event: any) {
    const point = pointFromTouchEvent(event)
    if (!point || !hueRect) return
    this.updateHueColor(point)
  },
  updateHueColor(point: { x: number; y: number }) {
    if (!hueRect) return
    const position = clamp((point.x - hueRect.left) / hueRect.width, 0, 1)
    const hue = position * 360
    this.setData({
      pickerHue: hue,
      hueX: position * 100,
      pickerHueColor: hsvToHex(hue, 1, 1),
      customColor: hsvToHex(hue, this.data.pickerSaturation, this.data.pickerValue)
    })
  },
  applyCustomColor() {
    if (!this.data.transparentPath) return
    this.enqueueBackground('custom', this.data.customColor, '自定义')
  },
  enqueueBackground(key: string, color: string, label: string) {
    pendingBackground = { key, color, label, generation: photoGeneration }
    if (!processingBackground) {
      void this.processBackgroundQueue()
    }
  },
  async processBackgroundQueue() {
    processingBackground = true
    this.setData({ compositing: true })
    try {
      while (pendingBackground) {
        const selection = pendingBackground
        pendingBackground = null
        let outputPath = this.data.transparentPath

        try {
          if (selection.key !== 'transparent') {
            outputPath = await this.composeBackground(selection.color)
          }
        } catch (error) {
          if (!pendingBackground && selection.generation === photoGeneration) {
            showError(error)
          }
          continue
        }

        if (!pendingBackground && selection.generation === photoGeneration) {
          this.setData({
            resultPath: outputPath,
            selectedBackground: selection.key,
            selectedBackgroundColor: selection.color,
            saveButtonText: selection.key === 'transparent' ? '保存透明 PNG' : '保存证件照'
          })
        }
      }
    } finally {
      processingBackground = false
      this.setData({ compositing: false })
    }
  },
  composeBackground(color: string): Promise<string> {
    const sourcePath = this.data.transparentPath
    return new Promise((resolve, reject) => {
      wx.getImageInfo({
        src: sourcePath,
        success: image => {
          const width = image.width
          const height = image.height
          this.setData({ canvasWidth: width, canvasHeight: height }, () => {
            const context = wx.createCanvasContext('photoCanvas', this)
            context.setFillStyle(color)
            context.fillRect(0, 0, width, height)
            context.drawImage(sourcePath, 0, 0, width, height)
            context.draw(false, () => {
              wx.canvasToTempFilePath({
                canvasId: 'photoCanvas',
                width,
                height,
                destWidth: width,
                destHeight: height,
                fileType: 'png',
                success: result => resolve(result.tempFilePath),
                fail: () => reject(new Error('生成证件照失败'))
              }, this)
            })
          })
        },
        fail: () => reject(new Error('无法读取透明背景图片'))
      })
    })
  },
  saveResult() {
    if (!this.data.resultPath || this.data.compositing) return
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
  },
  onUnload() {
    photoGeneration += 1
    pendingBackground = null
    paletteRect = null
    hueRect = null
  }
})
