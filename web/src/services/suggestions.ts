import { authState } from './auth'
import { fetchAccountApi } from '../config/accountApi'

interface ApiEnvelope<T> {
  success: boolean
  message?: string
  data: T
  total?: number
  current?: number
  pages?: number
  size?: number
}

export interface FeatureSuggestion {
  id: number
  title: string
  content: string
  contact?: string
  status: number
  reply?: string
  createTime: string
  updateTime: string
}

export interface SuggestionPage {
  items: FeatureSuggestion[]
  total: number
  current: number
  pages: number
}

export interface SubmitSuggestionPayload {
  title: string
  content: string
  contact?: string
}

export class SuggestionError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'SuggestionError'
  }
}

async function post<T>(path: string, body: object): Promise<ApiEnvelope<T>> {
  const token = authState.session?.token
  if (!token) throw new SuggestionError('请先登录后使用功能建议')

  let response: Response
  try {
    response = await fetchAccountApi(path, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify(body)
    })
  } catch {
    throw new SuggestionError('无法连接建议服务，请稍后重试')
  }

  let envelope: ApiEnvelope<T> | null = null
  try {
    envelope = (await response.json()) as ApiEnvelope<T>
  } catch {
    // Use the status fallback below when the backend did not return JSON.
  }
  if (!response.ok || !envelope?.success) {
    throw new SuggestionError(envelope?.message || `建议服务请求失败（${response.status}）`)
  }
  return envelope
}

export async function submitSuggestion(payload: SubmitSuggestionPayload): Promise<FeatureSuggestion> {
  const response = await post<FeatureSuggestion>('/c/suggestion/submit', {
    title: payload.title.trim(),
    content: payload.content.trim(),
    contact: payload.contact?.trim() || undefined
  })
  return response.data
}

export async function listMySuggestions(current = 1, size = 20): Promise<SuggestionPage> {
  const response = await post<FeatureSuggestion[]>('/c/suggestion/my/list', { current, size })
  return {
    items: response.data || [],
    total: response.total || 0,
    current: response.current || current,
    pages: response.pages || 0
  }
}
