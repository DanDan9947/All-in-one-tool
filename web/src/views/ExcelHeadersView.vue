<script setup lang="ts">
import { ref } from 'vue'

import ErrorNotice from '../components/ErrorNotice.vue'
import FileDropzone from '../components/FileDropzone.vue'
import PageHeading from '../components/PageHeading.vue'
import ResultPlaceholder from '../components/ResultPlaceholder.vue'
import { uploadForExcelHeaders } from '../services/api'
import type { ExcelHeaderResult } from '../types/api'
import { formatFileSize, validateExcelFile } from '../utils/files'

const file = ref<File | null>(null)
const result = ref<ExcelHeaderResult | null>(null)
const loading = ref(false)
const error = ref<unknown>(null)
const copiedSheet = ref('')

function selectFile(nextFile: File): void {
  try {
    file.value = validateExcelFile(nextFile)
    result.value = null
    error.value = null
    copiedSheet.value = ''
  } catch (reason) {
    error.value = reason
  }
}

async function extractHeaders(): Promise<void> {
  if (!file.value || loading.value) return
  loading.value = true
  result.value = null
  error.value = null
  try {
    result.value = await uploadForExcelHeaders(file.value)
  } catch (reason) {
    error.value = reason
  } finally {
    loading.value = false
  }
}

async function copyHeaders(sheetName: string, headers: string[]): Promise<void> {
  const text = headers.join('\t')
  try {
    await navigator.clipboard.writeText(text)
  } catch {
    const textarea = document.createElement('textarea')
    textarea.value = text
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    textarea.remove()
  }
  copiedSheet.value = sheetName
  window.setTimeout(() => (copiedSheet.value = ''), 1600)
}
</script>

<template>
  <div class="tool-view">
    <PageHeading
      eyebrow="EXCEL HEADERS"
      title="提取 Excel 标题"
      description="自动识别报表中的真实标题行，并把繁体字段统一转换为简体中文。"
    />
    <ErrorNotice v-if="error" :error="error" @dismiss="error = null" />
    <div class="workspace-grid excel-workspace">
      <section class="panel input-panel">
        <FileDropzone
          accept=".xls,.xlsx,.csv,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv"
          title="选择 Excel 文件"
          hint="支持 XLS、XLSX、CSV，文件不超过 50MB"
          :file="file"
          :disabled="loading"
          @select="selectFile"
        />
        <div v-if="file" class="file-summary">
          <span class="excel-file-icon">XLS</span>
          <div>
            <strong>{{ file.name }}</strong>
            <span>{{ formatFileSize(file.size) }}</span>
          </div>
        </div>
        <button
          class="primary-button full-button teal-button"
          type="button"
          :disabled="!file || loading"
          @click="extractHeaders"
        >
          <span v-if="loading" class="spinner" />
          {{ loading ? '正在读取标题…' : '读取并转换标题' }}
        </button>
        <p class="excel-privacy-note">文件仅在内存中读取，不保存上传内容。</p>
      </section>

      <section class="panel result-panel excel-result-panel">
        <div v-if="result" class="excel-header-result">
          <div class="result-heading">
            <div>
              <span class="success-label teal-label">识别完成</span>
              <h2>{{ result.fileName }}</h2>
            </div>
            <span class="sheet-count">{{ result.sheetCount }} 个有效工作表</span>
          </div>

          <article v-for="sheet in result.sheets" :key="sheet.sheetName" class="sheet-result">
            <div class="sheet-result-heading">
              <div>
                <h3>{{ sheet.sheetName }}</h3>
                <p>标题位于第 {{ sheet.headerRow }} 行，共 {{ sheet.columnCount }} 列</p>
              </div>
              <button
                class="secondary-button compact-button"
                type="button"
                @click="copyHeaders(sheet.sheetName, sheet.headers)"
              >
                {{ copiedSheet === sheet.sheetName ? '已复制' : '复制简体标题' }}
              </button>
            </div>
            <div class="header-table-wrap">
              <table class="header-table">
                <thead>
                  <tr><th>列</th><th>简体标题</th><th>原始标题</th></tr>
                </thead>
                <tbody>
                  <tr v-for="(header, index) in sheet.headers" :key="index">
                    <td>{{ index + 1 }}</td>
                    <td><strong>{{ header }}</strong></td>
                    <td>{{ sheet.originalHeaders[index] }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </article>
        </div>
        <ResultPlaceholder
          v-else
          symbol="XLS"
          title="简体标题会显示在这里"
          description="能够跳过报表名称、空白行，并自动定位字段标题。"
        />
      </section>
    </div>
  </div>
</template>
