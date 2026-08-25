<script setup lang="ts">
const tools = [
  {
    to: '/excel-headers',
    symbol: 'XLS',
    tone: 'green',
    title: '提取 Excel 标题',
    description: '自动定位真实标题行，并将繁体字段转换为简体输出。',
    meta: 'XLS · XLSX · CSV · 最大 50MB'
  },
  {
    to: '/image-compress',
    symbol: 'IMG',
    tone: 'green',
    title: '图片压缩',
    description: '智能压缩 JPG、PNG 和 WebP，支持目标大小与分辨率设置。',
    meta: '智能格式 · 最大 50MB'
  },
  {
    to: '/video-compress',
    symbol: 'MP4',
    tone: 'red',
    title: '视频压缩',
    description: '压缩 MP4、MOV、MKV 和 WebM，统一生成兼容的 MP4。',
    meta: '本机最大 2GB · H.264'
  },
  {
    to: '/screen-record',
    symbol: 'REC',
    tone: 'red',
    title: '电脑录屏',
    description: '录制电脑画面与系统声音，支持框选任意录制范围。',
    meta: 'MP4 · 本机保存 · 不限时长'
  },
  {
    to: '/ocr',
    symbol: '文',
    tone: 'blue',
    title: '提取图片文字',
    description: '识别中文、英文和混排内容，一键复制结果。',
    meta: 'JPG · PNG · WebP'
  },
  {
    to: '/pdf-convert',
    symbol: 'PDF',
    tone: 'orange',
    title: 'PDF 转 Excel / Word',
    description: '提取表格，或生成包含可编辑文字和表格的文档。',
    meta: '最大 10MB · 30 页'
  },
  {
    to: '/cutout',
    symbol: '像',
    tone: 'purple',
    title: '人像背景移除',
    description: '生成透明 PNG，并在浏览器内更换证件照背景色。',
    meta: '透明 · 白 · 蓝 · 红'
  },
  {
    to: '/ink-cutout',
    symbol: '章',
    tone: 'teal',
    title: '文字 / 印章抠图',
    description: '保留印章、文字和手写内容，去除白色或近白背景。',
    meta: '强度可调'
  }
]
</script>

<template>
  <div class="home-view">
    <section class="home-hero">
      <div>
        <span class="eyebrow">FREE · PRIVATE · SIMPLE</span>
        <h1>日常文件处理，<br /><em>简单一点。</em></h1>
        <p>使用本地开源模型完成识别与抠图，不接入按次收费的 AI 服务。</p>
      </div>
      <div class="privacy-card">
        <span class="privacy-shield">✓</span>
        <div>
          <strong>文件仅在本机处理</strong>
          <p>不上传互联网、不保留处理历史；除您主动保存的结果外，临时文件会自动清理。</p>
        </div>
      </div>
    </section>

    <section class="tools-section" aria-labelledby="tools-title">
      <div class="section-heading">
        <div>
          <span class="eyebrow">TOOLS</span>
          <h2 id="tools-title">选择一个工具</h2>
        </div>
        <p>电脑和手机浏览器均可使用</p>
      </div>
      <div class="tool-grid">
        <RouterLink v-for="tool in tools" :key="tool.to" class="tool-card" :to="tool.to">
          <span class="tool-symbol" :class="tool.tone">{{ tool.symbol }}</span>
          <div class="tool-copy">
            <h3>{{ tool.title }}</h3>
            <p>{{ tool.description }}</p>
            <span>{{ tool.meta }}</span>
          </div>
          <span class="card-arrow">→</span>
        </RouterLink>
      </div>
    </section>
  </div>
</template>
