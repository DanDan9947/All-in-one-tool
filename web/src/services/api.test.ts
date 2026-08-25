import { describe, expect, it } from 'vitest'

import { apiErrorFromPayload } from './api'

describe('apiErrorFromPayload', () => {
  it('reads the backend error envelope and request id', () => {
    const error = apiErrorFromPayload(
      JSON.stringify({
        code: 'NO_TEXT_FOUND',
        message: '没有识别到文字',
        requestId: 'request-123'
      }),
      422
    )

    expect(error.message).toBe('没有识别到文字')
    expect(error.code).toBe('NO_TEXT_FOUND')
    expect(error.requestId).toBe('request-123')
    expect(error.status).toBe(422)
  })

  it('uses a safe fallback for a non-json response', () => {
    const error = apiErrorFromPayload('<html>bad gateway</html>', 503, 'proxy-456')

    expect(error.message).toBe('当前使用人数较多，请稍后重试')
    expect(error.requestId).toBe('proxy-456')
  })
})
