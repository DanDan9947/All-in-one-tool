const DEFAULT_ACCOUNT_API_ROOT = 'https://danyy.cn/api'

/**
 * Unified account-service root.
 *
 * Local development is configured in web/.env.development and production is
 * configured in web/.env.production. Endpoint paths are appended by services.
 */
export const ACCOUNT_API_ROOT = (
  import.meta.env.VITE_C_USER_API_URL || DEFAULT_ACCOUNT_API_ROOT
).replace(/\/$/, '')

const ACCOUNT_API_TIMEOUT_MS = 8_000

export async function fetchAccountApi(path: string, init: RequestInit): Promise<Response> {
  const controller = new AbortController()
  const timeoutId = globalThis.setTimeout(() => controller.abort(), ACCOUNT_API_TIMEOUT_MS)
  try {
    return await fetch(`${ACCOUNT_API_ROOT}${path}`, {
      ...init,
      signal: controller.signal
    })
  } finally {
    globalThis.clearTimeout(timeoutId)
  }
}
