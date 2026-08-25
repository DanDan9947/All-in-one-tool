let navigationInProgress = false

function openPage(url: string) {
  if (navigationInProgress) {
    return
  }

  navigationInProgress = true
  wx.navigateTo({
    url,
    fail() {
      navigationInProgress = false
    }
  })
}

Page({
  onShow() {
    navigationInProgress = false
  },
  openOcr() {
    openPage('/pages/ocr/ocr')
  },
  openImageCompress() {
    openPage('/pages/imagecompress/imagecompress')
  },
  openPdfConvert() {
    openPage('/pages/pdfconvert/pdfconvert')
  },
  openCutout() {
    openPage('/pages/cutout/cutout')
  },
  openInkCutout() {
    openPage('/pages/inkcutout/inkcutout')
  }
})
