<script setup lang="ts">
import { computed } from 'vue'

import { ApiError } from '../types/api'

const props = defineProps<{
  error: unknown
}>()

defineEmits<{
  dismiss: []
}>()

const message = computed(() =>
  props.error instanceof Error ? props.error.message : '处理失败，请稍后重试'
)

const requestId = computed(() =>
  props.error instanceof ApiError ? props.error.requestId : undefined
)
</script>

<template>
  <div class="error-notice" role="alert">
    <span class="error-icon">!</span>
    <div>
      <strong>{{ message }}</strong>
      <small v-if="requestId">请求编号：{{ requestId }}</small>
    </div>
    <button type="button" aria-label="关闭错误提示" @click="$emit('dismiss')">×</button>
  </div>
</template>
