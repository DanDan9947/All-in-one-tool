<script setup lang="ts">
import { onMounted } from 'vue'

import { ensurePublicContent, publicContentState, safeExternalUrl } from '../services/publicContent'

onMounted(() => {
  ensurePublicContent().catch(() => undefined)
})

function dateLabel(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return new Intl.DateTimeFormat('zh-CN', { month: '2-digit', day: '2-digit' }).format(date)
}
</script>

<template>
  <aside class="global-rail ad-rail" aria-label="广告">
    <div class="rail-heading"><span>AD</span><strong>推荐</strong></div>
    <div v-if="publicContentState.ads.length" class="rail-list">
      <a
        v-for="ad in publicContentState.ads"
        :key="ad.id"
        class="ad-card"
        :href="safeExternalUrl(ad.url)"
        :target="safeExternalUrl(ad.url) ? '_blank' : undefined"
        :rel="safeExternalUrl(ad.url) ? 'noopener noreferrer' : undefined"
      >
        <img :src="ad.image" :alt="ad.title" loading="lazy" />
        <span>{{ ad.title }}</span>
      </a>
    </div>
    <div v-else-if="publicContentState.loaded" class="rail-empty">暂无广告</div>
    <div v-else class="rail-loading">加载中…</div>
  </aside>

  <aside class="global-rail announcement-rail" aria-label="公告">
    <div class="rail-heading"><span>NOTICE</span><strong>公告</strong></div>
    <div v-if="publicContentState.announcements.length" class="rail-list announcement-list">
      <article v-for="announcement in publicContentState.announcements" :key="announcement.id" class="announcement-card">
        <img v-if="announcement.image" :src="announcement.image" :alt="announcement.title" loading="lazy" />
        <div class="announcement-meta">
          <strong>{{ announcement.title }}</strong>
          <time :datetime="announcement.publishTime">{{ dateLabel(announcement.publishTime) }}</time>
        </div>
        <p>{{ announcement.content }}</p>
      </article>
    </div>
    <div v-else-if="publicContentState.loaded" class="rail-empty">暂无公告</div>
    <div v-else class="rail-loading">加载中…</div>
  </aside>
</template>
