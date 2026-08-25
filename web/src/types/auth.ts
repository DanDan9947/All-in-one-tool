export interface CUser {
  id: number
  username: string
  nickname: string
  avatar?: string
  mobile?: string
  email?: string
  gender?: number
  birthday?: string
  status: number
  lastLoginTime?: string
  createTime?: string
  updateTime?: string
}

export interface AuthSession {
  token: string
  user: CUser
}

export interface RegisterPayload {
  username: string
  password: string
  captchaId: string
  captchaCode: string
  nickname?: string
  mobile?: string
  email?: string
}

export interface CaptchaChallenge {
  captchaId: string
  imageBase64: string
  expiresInSeconds: number
}

export interface CUserSetting {
  loginRequired: boolean
  registerEnabled: boolean
  guestUsable: boolean
  createTime?: string
  updateTime?: string
}
