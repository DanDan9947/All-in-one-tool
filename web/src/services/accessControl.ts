import { reactive } from 'vue'

export const accessPromptState = reactive({
  visible: false,
  targetPath: '/'
})

export function showLoginRequiredPrompt(targetPath: string): void {
  accessPromptState.targetPath = targetPath.startsWith('/') ? targetPath : '/'
  accessPromptState.visible = true
}

export function closeLoginRequiredPrompt(): void {
  accessPromptState.visible = false
}
