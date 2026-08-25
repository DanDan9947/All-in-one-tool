import { createRouter, createWebHistory } from 'vue-router'

import HomeView from './views/HomeView.vue'
import { showLoginRequiredPrompt } from './services/accessControl'
import { authState, ensureUserSetting, loginIsRequired, registrationIsEnabled } from './services/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    {
      path: '/login',
      name: 'login',
      component: () => import('./views/LoginView.vue')
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('./views/RegisterView.vue')
    },
    {
      path: '/suggestions',
      name: 'suggestions',
      meta: { requiresAuth: true },
      component: () => import('./views/SuggestionsView.vue')
    },
    {
      path: '/excel-headers',
      name: 'excel-headers',
      meta: { tool: true },
      component: () => import('./views/ExcelHeadersView.vue')
    },
    {
      path: '/ocr',
      name: 'ocr',
      meta: { tool: true },
      component: () => import('./views/OcrView.vue')
    },
    {
      path: '/pdf-convert',
      name: 'pdf-convert',
      meta: { tool: true },
      component: () => import('./views/PdfConvertView.vue')
    },
    {
      path: '/cutout',
      name: 'cutout',
      meta: { tool: true },
      component: () => import('./views/CutoutView.vue')
    },
    {
      path: '/ink-cutout',
      name: 'ink-cutout',
      meta: { tool: true },
      component: () => import('./views/InkCutoutView.vue')
    },
    {
      path: '/screen-record',
      name: 'screen-record',
      meta: { tool: true },
      component: () => import('./views/ScreenRecordView.vue')
    },
    {
      path: '/image-compress',
      name: 'image-compress',
      meta: { tool: true },
      component: () => import('./views/ImageCompressView.vue')
    },
    {
      path: '/video-compress',
      name: 'video-compress',
      meta: { tool: true },
      component: () => import('./views/VideoCompressView.vue')
    },
    { path: '/:pathMatch(.*)*', redirect: '/' }
  ],
  scrollBehavior: () => ({ top: 0 })
})

router.beforeEach(async to => {
  try {
    await ensureUserSetting()
  } catch {
    // Keep the last known/default policy when the setting service is temporarily unavailable.
  }

  if (to.name === 'register' && !registrationIsEnabled()) {
    return { name: 'login', query: { registration: 'disabled' } }
  }
  if ((to.meta.requiresAuth || (to.meta.tool && loginIsRequired())) && !authState.session) {
    showLoginRequiredPrompt(to.fullPath)
    return false
  }
  return true
})

export default router
