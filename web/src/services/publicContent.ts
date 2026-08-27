import { reactive } from 'vue'

import { fetchAccountApi } from '../config/accountApi'

interface PageEnvelope<T> {
  success: boolean
  message?: string
  data: T[] | null
}

export interface Announcement {
  id: number
  title: string
  content: string
  image?: string
  status: number
  sort: number
  publishTime: string
}

export interface Ad {
  id: number
  title: string
  image: string
  url?: string
  position: string
  sort: number
  status: number
  startTime?: string
  endTime?: string
}

export const publicContentState = reactive<{
  announcements: Announcement[]
  ads: Ad[]
  loaded: boolean
}>({ announcements: [], ads: [], loaded: false })

let contentRequest: Promise<void> | null = null

async function fetchPage<T>(path: string, body: object): Promise<T[]> {
  const response = await fetchAccountApi(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })
  const envelope = (await response.json()) as PageEnvelope<T>
  if (!response.ok || !envelope.success) {
    throw new Error(envelope.message || `内容接口请求失败（${response.status}）`)
  }
  return envelope.data || []
}

function isPublished(item: Announcement, now: number): boolean {
  return item.status === 1 && (!item.publishTime || new Date(item.publishTime).getTime() <= now)
}

function isActiveAd(item: Ad, now: number): boolean {
  if (item.status !== 1) return false
  if (item.startTime && new Date(item.startTime).getTime() > now) return false
  if (item.endTime && new Date(item.endTime).getTime() < now) return false
  return true
}

export async function refreshPublicContent(): Promise<void> {
  const [announcementResult, adResult] = await Promise.allSettled([
    fetchPage<Announcement>('/c/announcement/list', { current: 1, size: 20, status: 1 }),
    fetchPage<Ad>('/c/ad/list', { current: 1, size: 20, status: 1 })
  ])
  const now = Date.now()
  publicContentState.announcements = announcementResult.status === 'fulfilled'
    ? announcementResult.value.filter(item => isPublished(item, now))
    : []
  publicContentState.ads = adResult.status === 'fulfilled'
    ? adResult.value.filter(item => isActiveAd(item, now))
    : []
  publicContentState.loaded = true
}

export function ensurePublicContent(): Promise<void> {
  if (publicContentState.loaded) return Promise.resolve()
  if (!contentRequest) {
    contentRequest = refreshPublicContent().finally(() => {
      contentRequest = null
    })
  }
  return contentRequest
}

export function safeExternalUrl(value?: string): string | undefined {
  if (!value) return undefined
  try {
    const url = new URL(value)
    return url.protocol === 'http:' || url.protocol === 'https:' ? url.toString() : undefined
  } catch {
    return undefined
  }
}
