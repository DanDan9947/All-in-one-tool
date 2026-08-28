import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  authState,
  featurePermissionState,
  getCaptcha,
  login,
  loginIsRequired,
  logout,
  refreshUserSetting,
  refreshFeaturePermissions,
  registrationIsEnabled,
  register,
  saveSession
} from './auth'

describe('C user authentication service', () => {
  beforeEach(() => {
    localStorage.clear()
    authState.session = null
    featurePermissionState.codes = []
    vi.restoreAllMocks()
  })

  it('uses the configured CUserController login endpoint', async () => {
    const session = {
      token: 'jwt-token',
      user: { id: 1, username: 'alice', nickname: 'Alice', status: 1 }
    }
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ success: true, data: session }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      })
    )

    await expect(login(' alice ', 'secret123', 'captcha-1', 'A7K9')).resolves.toEqual(session)
    expect(fetchMock).toHaveBeenCalledWith(
      'https://danyy.cn/api/c/user/login',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          userType: 'TOOL',
          username: 'alice',
          password: 'secret123',
          captchaId: 'captcha-1',
          captchaCode: 'A7K9'
        })
      })
    )
  })

  it('submits registration fields and exposes backend failures', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ success: true, data: { id: 2 } }), { status: 200 })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ success: false, message: '用户名已被注册', data: null }), {
          status: 200
        })
      )

    await register({
      username: ' bob ',
      password: 'secret123',
      nickname: ' Bob ',
      captchaId: 'captcha-2',
      captchaCode: ' B3M8 '
    })
    expect(fetchMock.mock.calls[0][0]).toBe(
      'https://danyy.cn/api/c/user/register'
    )
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toEqual(
      {
        userType: 'TOOL',
        username: 'bob',
        password: 'secret123',
        nickname: 'Bob',
        captchaId: 'captcha-2',
        captchaCode: 'B3M8'
      }
    )
    await expect(login('bob', 'wrong-password', 'captcha-3', 'C4N7')).rejects.toThrow(
      '用户名已被注册'
    )
  })

  it('loads a backend-generated image captcha', async () => {
    const challenge = {
      captchaId: 'captcha-1',
      imageBase64: 'data:image/png;base64,abc',
      expiresInSeconds: 300
    }
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ success: true, data: challenge }), { status: 200 })
    )

    await expect(getCaptcha()).resolves.toEqual(challenge)
    expect(fetchMock.mock.calls[0][0]).toBe(
      'https://danyy.cn/api/c/user/captcha'
    )
  })

  it('persists and clears the current session', () => {
    const session = {
      token: 'jwt-token',
      user: { id: 1, username: 'alice', nickname: 'Alice', status: 1 }
    }
    saveSession(session)
    expect(authState.session).toEqual(session)
    expect(localStorage.getItem('dandan-c-user-auth')).toContain('jwt-token')

    logout()
    expect(authState.session).toBeNull()
    expect(localStorage.getItem('dandan-c-user-auth')).toBeNull()
  })

  it('loads feature permissions for the current user', async () => {
    authState.session = {
      token: 'jwt-token',
      user: { id: 1, username: 'alice', nickname: 'Alice', status: 1 }
    }
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({
        success: true,
        data: { userId: 1, permissionCodes: ['windows-build'] }
      }), { status: 200 })
    )

    await expect(refreshFeaturePermissions()).resolves.toEqual(['windows-build'])
    expect(fetchMock).toHaveBeenCalledWith(
      'https://danyy.cn/api/c/user/permission/me',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ Authorization: 'Bearer jwt-token' })
      })
    )
    expect(featurePermissionState.codes).toEqual(['windows-build'])
  })

  it('loads the access policy from t_c_user_setting', async () => {
    const setting = {
      userType: 'TOOL',
      loginRequired: true,
      registerEnabled: false,
      guestUsable: false
    }
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ success: true, data: setting }), { status: 200 })
    )

    await expect(refreshUserSetting()).resolves.toEqual(setting)
    expect(fetchMock.mock.calls[0][0]).toBe(
      'https://danyy.cn/api/c/user/setting/detail'
    )
    expect(fetchMock.mock.calls[0][1]?.body).toBe(
      JSON.stringify({ userType: 'TOOL' })
    )
    expect(authState.setting).toEqual(setting)
    expect(loginIsRequired()).toBe(true)
    expect(registrationIsEnabled()).toBe(false)
  })

  it('requires login when guest use is disabled independently', () => {
    authState.setting = {
      loginRequired: false,
      registerEnabled: true,
      guestUsable: false
    }

    expect(loginIsRequired()).toBe(true)
    expect(registrationIsEnabled()).toBe(true)
  })
})
