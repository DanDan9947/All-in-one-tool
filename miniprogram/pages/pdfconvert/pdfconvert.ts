import {
  downloadPdfConversion,
  PdfOutputFormat,
  uploadPdfForConversion
} from '../../services/api'
import { chooseSinglePdf, formatFileSize } from '../../utils/file'
import { showError } from '../../utils/image'

Page({
  data: {
    filePath: '',
    fileName: '',
    fileSizeLabel: '',
    outputFormat: 'xlsx' as PdfOutputFormat,
    loading: false,
    progress: 0,
    stageText: '',
    resultPath: '',
    resultName: ''
  },

  async choosePdf() {
    if (this.data.loading) return
    try {
      const file = await chooseSinglePdf()
      if (!file) return
      this.setData({
        filePath: file.path,
        fileName: file.name,
        fileSizeLabel: formatFileSize(file.size),
        progress: 0,
        stageText: '',
        resultPath: '',
        resultName: ''
      })
    } catch (error) {
      showError(error)
    }
  },

  selectFormat(event: any) {
    if (this.data.loading) return
    const outputFormat = String(event.currentTarget.dataset.format) as PdfOutputFormat
    if (outputFormat !== 'xlsx' && outputFormat !== 'docx') return
    this.setData({
      outputFormat,
      resultPath: '',
      resultName: ''
    })
  },

  async convert() {
    if (!this.data.filePath || this.data.loading) return
    this.setData({
      loading: true,
      progress: 0,
      stageText: '正在上传 PDF…',
      resultPath: '',
      resultName: ''
    })
    try {
      const conversion = await uploadPdfForConversion(
        this.data.filePath,
        this.data.outputFormat,
        progress => this.setData({ progress })
      )
      this.setData({ stageText: '转换完成，正在下载…', progress: 100 })
      const resultPath = await downloadPdfConversion(
        conversion.token,
        conversion.format
      )
      this.setData({
        resultPath,
        resultName: conversion.fileName,
        stageText: ''
      })
      wx.showToast({ title: '转换完成', icon: 'success' })
    } catch (error) {
      showError(error)
    } finally {
      this.setData({ loading: false })
    }
  },

  exportResult() {
    if (!this.data.resultPath) return
    const platformApi = wx as any
    if (typeof platformApi.saveFileToDisk === 'function') {
      platformApi.saveFileToDisk({
        filePath: this.data.resultPath,
        success: () => {
          wx.showToast({ title: '文件已导出', icon: 'success' })
        },
        fail: (error: any) => {
          this.shareResultFile(error)
        }
      })
      return
    }
    this.shareResultFile()
  },

  shareResultFile(previousError?: any) {
    const platformApi = wx as any
    if (typeof platformApi.shareFileMessage !== 'function') {
      const detail = previousError?.errMsg || '当前环境不支持文件导出'
      wx.showModal({
        title: '无法导出',
        content: `${detail}\n请使用手机微信真机预览后重试。`,
        showCancel: false
      })
      return
    }
    platformApi.shareFileMessage({
      filePath: this.data.resultPath,
      fileName: this.data.resultName,
      success: () => {
        wx.showToast({ title: '请选择接收人', icon: 'none' })
      },
      fail: (error: any) => {
        const detail = error?.errMsg || previousError?.errMsg || '文件导出失败'
        wx.showModal({
          title: '导出失败',
          content: detail,
          showCancel: false
        })
      }
    })
  },

  async openResult() {
    if (!this.data.resultPath) return
    try {
      await this.openDocument(this.data.resultPath, this.data.outputFormat)
    } catch (error) {
      this.showPreviewError(error)
    }
  },

  showPreviewError(error: unknown) {
    const detail = error instanceof Error ? error.message : '微信文档预览失败'
    wx.showModal({
      title: '转换已完成',
      content: `${detail}\n文件已保存在小程序本地，可点击按钮重试。`,
      showCancel: false
    })
  },

  openDocument(filePath: string, fileType: PdfOutputFormat): Promise<void> {
    return new Promise((resolve, reject) => {
      wx.openDocument({
        filePath,
        fileType,
        showMenu: true,
        success: () => resolve(),
        fail: error => {
          const detail = error.errMsg || '未知原因'
          console.error('wx.openDocument failed', {
            filePath,
            fileType,
            errMsg: detail
          })
          reject(new Error(`无法打开转换结果：${detail}`))
        }
      })
    })
  }
})
