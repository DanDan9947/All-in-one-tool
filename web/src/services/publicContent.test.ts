import { beforeEach, describe, expect, it, vi } from 'vitest'

import { publicContentState, refreshPublicContent, safeExternalUrl } from './publicContent'

describe('public C content', () => {
  beforeEach(() => {
    publicContentState.announcements = []
    publicContentState.ads = []
    publicContentState.loaded = false
    vi.restoreAllMocks()
  })

  it('loads enabled announcements and currently active ads', async () => {
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify({
        success: true,
        data: [
          { id: 1, title: '公告', content: '内容', status: 1, sort: 1, publishTime: '2020-01-01 00:00:00' },
          { id: 2, title: '未来公告', content: '内容', status: 1, sort: 0, publishTime: '2099-01-01 00:00:00' }
        ]
      }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        success: true,
        data: [
          { id: 1, title: '广告', image: '/ad.png', position: 'default', sort: 1, status: 1 },
          { id: 2, title: '过期广告', image: '/old.png', position: 'default', sort: 0, status: 1, endTime: '2020-01-01 00:00:00' }
        ]
      }), { status: 200 }))

    await refreshPublicContent()

    expect(publicContentState.announcements.map(item => item.id)).toEqual([1])
    expect(publicContentState.ads.map(item => item.id)).toEqual([1])
    expect(publicContentState.loaded).toBe(true)
  })

  it('rejects unsafe advertisement links', () => {
    expect(safeExternalUrl('javascript:alert(1)')).toBeUndefined()
    expect(safeExternalUrl('https://example.com/path')).toBe('https://example.com/path')
  })
})
