import { beforeEach, describe, expect, it, vi } from 'vitest'

import { authState } from './auth'
import { listMySuggestions, submitSuggestion } from './suggestions'

describe('C user feature suggestions', () => {
  beforeEach(() => {
    authState.session = {
      token: 'c-user-token',
      user: { id: 7, username: 'dandan', nickname: '蛋蛋', status: 1 }
    }
    vi.restoreAllMocks()
  })

  it('submits a suggestion with the current C-user token', async () => {
    const suggestion = {
      id: 12,
      title: '批量转换',
      content: '希望增加批量转换',
      status: 0,
      createTime: '2026-08-25 10:00:00',
      updateTime: '2026-08-25 10:00:00'
    }
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ success: true, data: suggestion }), { status: 200 })
    )

    await expect(
      submitSuggestion({ title: ' 批量转换 ', content: ' 希望增加批量转换 ', contact: ' ' })
    ).resolves.toEqual(suggestion)
    expect(fetchMock).toHaveBeenCalledWith(
      'http://172.23.31.184:8081/prod-api/c/suggestion/submit',
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer c-user-token' }),
        body: JSON.stringify({ title: '批量转换', content: '希望增加批量转换' })
      })
    )
  })

  it('loads only the current user suggestions including administrator replies', async () => {
    const items = [
      {
        id: 12,
        title: '批量转换',
        content: '希望增加批量转换',
        status: 1,
        reply: '已经列入开发计划',
        createTime: '2026-08-25 10:00:00',
        updateTime: '2026-08-25 11:00:00'
      }
    ]
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({ success: true, data: items, total: 1, current: 1, pages: 1 }),
        { status: 200 }
      )
    )

    await expect(listMySuggestions()).resolves.toEqual({
      items,
      total: 1,
      current: 1,
      pages: 1
    })
  })
})
