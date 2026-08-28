import { reactive } from 'vue'

import { fetchAccountApi } from '../config/accountApi'
import type {
  AuthSession,
  CaptchaChallenge,
  CUser,
  CUserSetting,
  RegisterPayload
} from '../types/auth'

const AUTH_STORAGE_KEY = 'dandan-c-user-auth'
const USER_TYPE = 'TOOL'

interface AuthEnvelope<T> {
  success: boolean
  errorCode?: string
  message?: string
  data: T
}

export class AuthError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'AuthError'
  }
}

function readStoredSession(): AuthSession | null {
  try {
    const value = localStorage.getItem(AUTH_STORAGE_KEY)
    if (!value) return null
    const session = JSON.parse(value) as AuthSession
    return session?.token && session?.user ? session : null
  } catch {
    localStorage.removeItem(AUTH_STORAGE_KEY)
    return null
  }
}

const DEFAULT_USER_SETTING: CUserSetting = {
  loginRequired: false,
  registerEnabled: true,
  guestUsable: true
}

export const authState = reactive<{
  session: AuthSession | null
  setting: CUserSetting
  settingLoaded: boolean
}>({
  session: readStoredSession(),
  setting: DEFAULT_USER_SETTING,
  settingLoaded: false
})

export const featurePermissionState = reactive<{
  codes: string[]
  loaded: boolean
}>({
  codes: [],
  loaded: false
})

let settingRequest: Promise<CUserSetting> | null = null
let settingLoadedAt = 0
const SETTING_CACHE_MS = 15_000

async function post<T>(path: string, data: object): Promise<T> {
  let response: Response
  try {
    response = await fetchAccountApi(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    })
  } catch {
    throw new AuthError('无法连接账号服务，请确认当前配置的服务器可访问')
  }

  let body: AuthEnvelope<T> | null = null
  try {
    body = (await response.json()) as AuthEnvelope<T>
  } catch {
    // The status-based fallback below is clearer than exposing a JSON parse error.
  }
  if (!response.ok || !body?.success) {
    throw new AuthError(body?.message || `账号服务请求失败（${response.status}）`)
  }
  return body.data
}

export function getCaptcha(): Promise<CaptchaChallenge> {
  return post<CaptchaChallenge>('/c/user/captcha', {})
}

export function login(
  username: string,
  password: string,
  captchaId: string,
  captchaCode: string
): Promise<AuthSession> {
  return post<AuthSession>('/c/user/login', {
    userType: USER_TYPE,
    username: username.trim(),
    password,
    captchaId,
    captchaCode: captchaCode.trim()
  })
}

export function register(payload: RegisterPayload): Promise<CUser> {
  return post<CUser>('/c/user/register', {
    ...payload,
    userType: USER_TYPE,
    username: payload.username.trim(),
    captchaCode: payload.captchaCode.trim(),
    nickname: payload.nickname?.trim() || undefined,
    mobile: payload.mobile?.trim() || undefined,
    email: payload.email?.trim() || undefined
  })
}

export async function refreshUserSetting(): Promise<CUserSetting> {
  try {
    const setting = await post<CUserSetting>('/c/user/setting/detail', {
      userType: USER_TYPE
    })
    authState.setting = setting
    settingLoadedAt = Date.now()
    return setting
  } finally {
    authState.settingLoaded = true
  }
}

export function ensureUserSetting(): Promise<CUserSetting> {
  if (authState.settingLoaded && Date.now() - settingLoadedAt < SETTING_CACHE_MS) {
    return Promise.resolve(authState.setting)
  }
  if (!settingRequest) {
    settingRequest = refreshUserSetting().finally(() => {
      settingRequest = null
    })
  }
  return settingRequest
}

export function loginIsRequired(): boolean {
  return authState.setting.loginRequired || !authState.setting.guestUsable
}

export function registrationIsEnabled(): boolean {
  return authState.setting.registerEnabled
}

export function saveSession(session: AuthSession): void {
  localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(session))
  authState.session = session
  refreshFeaturePermissions().catch(() => {
    featurePermissionState.codes = []
  })
}

export function logout(): void {
  localStorage.removeItem(AUTH_STORAGE_KEY)
  authState.session = null
  featurePermissionState.codes = []
  featurePermissionState.loaded = false
}

export async function refreshFeaturePermissions(): Promise<string[]> {
  const session = authState.session
  if (!session) {
    featurePermissionState.codes = []
    featurePermissionState.loaded = true
    return []
  }
  let response: Response
  try {
    response = await fetchAccountApi('/c/user/permission/me', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${session.token}`
      }
    })
  } catch {
    featurePermissionState.codes = []
    featurePermissionState.loaded = true
    throw new AuthError('无法连接权限服务，请稍后重试')
  }
  const body = (await response.json()) as AuthEnvelope<{
    userId: number
    permissionCodes: string[]
  }>
  if (!response.ok || !body.success) {
    featurePermissionState.codes = []
    featurePermissionState.loaded = true
    throw new AuthError(body.message || '读取功能权限失败')
  }
  featurePermissionState.codes = body.data?.permissionCodes || []
  featurePermissionState.loaded = true
  return featurePermissionState.codes
}

export function hasFeaturePermission(code: string): boolean {
  return featurePermissionState.codes.includes(code)
}
