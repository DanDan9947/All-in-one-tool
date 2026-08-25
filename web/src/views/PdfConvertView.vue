<script setup lang="ts">
import { ref } from 'vue'

import ErrorNotice from '../components/ErrorNotice.vue'
import FileDropzone from '../components/FileDropzone.vue'
import PageHeading from '../components/PageHeading.vue'
import ResultPlaceholder from '../components/ResultPlaceholder.vue'
import { downloadPdfConversion, uploadPdfForConversion } from '../services/api'
import type { PdfConversionResult, PdfOutputFormat } from '../types/api'
import { formatFileSize, triggerDownload, validatePdfFile } from '../utils/files'

const file = ref<File | null>(null)
const outputFormat = ref<PdfOutputFormat>('xlsx')
const loading = ref(false)
const progress = ref(0)
const stageText = ref('')
const conversion = ref<PdfConversionResult | null>(null)
const resultBlob = ref<Blob | null>(null)
const error = ref<unknown>(null)

function selectFile(nextFile: File): void {
  try {
    file.value = validatePdfFile(nextFile)
    conversion.value = null
    resultBlob.value = null
    progress.value = 0
    stageText.value = ''
    error.value = null
  } catch (reason) {
    error.value = reason
  }
}

function selectFormat(format: PdfOutputFormat): void {
  if (loading.value) return
  outputFormat.value = format
  conversion.value = null
  resultBlob.value = null
}

async function convert(): Promise<void> {
  if (!file.value || loading.value) return
  loading.value = true
  progress.value = 0
  stageText.value = '正在上传 PDF…'
  conversion.value = null
  resultBlob.value = null
  error.value = null
  try {
    const created = await uploadPdfForConversion(file.value, outputFormat.value, value => {
      progress.value = value
      if (value >= 100) stageText.value = '上传完成，正在转换…'
    })
    conversion.value = created
    progress.value = 100
    stageText.value = '转换完成，正在下载…'
    resultBlob.value = await downloadPdfConversion(created.token)
    stageText.value = ''
  } catch (reason) {
    error.value = reason
    stageText.value = ''
  } finally {
    loading.value = false
  }
}

function downloadResult(): void {
  if (conversion.value && resultBlob.value) {
    triggerDownload(resultBlob.value, conversion.value.fileName)
  }
}
</script>

<template>
  <div class="tool-view">
    <PageHeading
      eyebrow="PDF CONVERT"
      title="PDF 转 Excel / Word"
      description="提取 PDF 表格，或生成包含可编辑文字和表格的 Word 文档。"
    />
    <ErrorNotice v-if="error" :error="error" @dismiss="error = null" />
    <div class="workspace-grid">
      <section class="panel input-panel">
        <FileDropzone
          accept="application/pdf,.pdf"
          title="选择 PDF 文件"
          hint="支持 10MB、30 页以内且可以选中文字的 PDF"
          :file="file"
          :disabled="loading"
          @select="selectFile"
        />
        <div v-if="file" class="file-summary">
          <span class="pdf-file-icon">PDF</span>
          <div>
            <strong>{{ file.name }}</strong>
            <span>{{ formatFileSize(file.size) }}</span>
          </div>
        </div>
        <fieldset class="format-fieldset" :disabled="loading">
          <legend>转换格式</legend>
          <div class="format-options">
            <button
              type="button"
              class="format-option excel-option"
              :class="{ selected: outputFormat === 'xlsx' }"
              :aria-pressed="outputFormat === 'xlsx'"
              @click="selectFormat('xlsx')"
            >
              <span>XLSX</span>
              <strong>转换为 Excel</strong>
              <small>提取表格，跨页同表头自动合并</small>
            </button>
            <button
              type="button"
              class="format-option word-option"
              :class="{ selected: outputFormat === 'docx' }"
              :aria-pressed="outputFormat === 'docx'"
              @click="selectFormat('docx')"
            >
              <span>DOCX</span>
              <strong>转换为 Word</strong>
              <small>生成可编辑文字和表格</small>
            </button>
          </div>
        </fieldset>
        <button
          class="primary-button full-button orange-button"
          type="button"
          :disabled="!file || loading"
          @click="convert"
        >
          <span v-if="loading" class="spinner" />
          {{
            loading
              ? '正在处理…'
              : outputFormat === 'xlsx'
                ? '转换为 Excel'
                : '转换为 Word'
          }}
        </button>
        <div v-if="loading" class="progress-panel" aria-live="polite">
          <div class="progress-track">
            <div class="progress-value" :style="{ width: `${progress}%` }" />
          </div>
          <div><span>{{ stageText }}</span><strong>{{ progress }}%</strong></div>
        </div>
      </section>

      <section class="panel result-panel">
        <div v-if="conversion && resultBlob" class="pdf-result">
          <span class="success-mark">✓</span>
          <span class="success-label orange-label">转换完成</span>
          <h2>{{ conversion.fileName }}</h2>
          <p>
            文件已经准备好。转换结果在本机临时保留 30 秒，请及时保存。
          </p>
          <button
            class="primary-button full-button orange-button"
            type="button"
            @click="downloadResult"
          >
            下载 {{ conversion.format.toUpperCase() }} 文件
          </button>
          <small>原 PDF 已在转换完成后删除</small>
        </div>
        <ResultPlaceholder
          v-else
          symbol="PDF"
          title="转换结果会显示在这里"
          description="扫描件、加密文件和纯图片 PDF 暂不支持。"
        />
      </section>
    </div>
  </div>
</template>
