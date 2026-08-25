import { beforeEach, describe, expect, it, vi } from 'vitest'

import router from './router'
import { accessPromptState, closeLoginRequiredPrompt } from './services/accessControl'
import { authState } from './services/auth'

describe('tool access policy', () => {
  beforeEach(async () => {
    vi.stubGlobal('scrollTo', vi.fn())
    authState.session = null
    authState.settingLoaded = true
    authState.setting = {
      loginRequired: false,
      registerEnabled: true,
      guestUsable: true
    }
    closeLoginRequiredPrompt()
    await router.push('/')
  })

  it('blocks a tool and opens the login prompt when login is required', async () => {
    authState.setting.loginRequired = true

    await router.push('/ocr')

    expect(router.currentRoute.value.path).toBe('/')
    expect(accessPromptState.visible).toBe(true)
    expect(accessPromptState.targetPath).toBe('/ocr')
  })

  it('allows guests when the table policy permits guest use', async () => {
    await router.push('/ocr')

    expect(router.currentRoute.value.path).toBe('/ocr')
    expect(accessPromptState.visible).toBe(false)
  })

  it('blocks guests when guest use is disabled', async () => {
    authState.setting.guestUsable = false

    await router.push('/image-compress')

    expect(router.currentRoute.value.path).toBe('/')
    expect(accessPromptState.visible).toBe(true)
    expect(accessPromptState.targetPath).toBe('/image-compress')
  })

  it('redirects registration to login when registration is disabled', async () => {
    authState.setting.registerEnabled = false

    await router.push('/register')

    expect(router.currentRoute.value.path).toBe('/login')
    expect(router.currentRoute.value.query.registration).toBe('disabled')
  })

  it('always requires login for the personal suggestion and reply page', async () => {
    await router.push('/suggestions')

    expect(router.currentRoute.value.path).toBe('/')
    expect(accessPromptState.visible).toBe(true)
    expect(accessPromptState.targetPath).toBe('/suggestions')
  })

  it('allows a logged-in user to open personal suggestions', async () => {
    authState.session = {
      token: 'c-user-token',
      user: { id: 7, username: 'dandan', nickname: '蛋蛋', status: 1 }
    }

    await router.push('/suggestions')

    expect(router.currentRoute.value.path).toBe('/suggestions')
    expect(accessPromptState.visible).toBe(false)
  })
})
