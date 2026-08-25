<script setup lang="ts">
defineProps<{
  symbol: string
  title: string
  description: string
}>()
</script>

<template>
  <div class="result-placeholder">
    <span>{{ symbol }}</span>
    <h2>{{ title }}</h2>
    <p>{{ description }}</p>
  </div>
</template>
