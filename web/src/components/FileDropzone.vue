<script setup lang="ts">
import { ref } from 'vue'

const props = withDefaults(
  defineProps<{
    accept: string
    title: string
    hint: string
    disabled?: boolean
    camera?: boolean
    file?: File | null
  }>(),
  {
    disabled: false,
    camera: false,
    file: null
  }
)

const emit = defineEmits<{
  select: [file: File]
}>()

const fileInput = ref<HTMLInputElement>()
const cameraInput = ref<HTMLInputElement>()
const dragging = ref(false)

function emitFirst(files: FileList | null): void {
  const file = files?.[0]
  if (file) emit('select', file)
}

function onDrop(event: DragEvent): void {
  dragging.value = false
  if (props.disabled) return
  emitFirst(event.dataTransfer?.files || null)
}

function openFilePicker(): void {
  if (!props.disabled) fileInput.value?.click()
}

function openCamera(): void {
  if (!props.disabled) cameraInput.value?.click()
}
</script>

<template>
  <section
    class="dropzone"
    :class="{ dragging, disabled }"
    @dragenter.prevent="dragging = true"
    @dragover.prevent
    @dragleave.prevent="dragging = false"
    @drop.prevent="onDrop"
  >
    <input
      ref="fileInput"
      class="visually-hidden"
      type="file"
      :accept="accept"
      :disabled="disabled"
      @change="emitFirst(($event.target as HTMLInputElement).files)"
    />
    <input
      v-if="camera"
      ref="cameraInput"
      class="visually-hidden"
      type="file"
      :accept="accept"
      capture="environment"
      :disabled="disabled"
      @change="emitFirst(($event.target as HTMLInputElement).files)"
    />
    <div class="upload-symbol" aria-hidden="true">＋</div>
    <div>
      <h2>{{ title }}</h2>
      <p>{{ hint }}</p>
      <p v-if="file" class="selected-file">
        <strong>{{ file.name }}</strong>
        <span>已选择</span>
      </p>
    </div>
    <div class="dropzone-actions">
      <button class="secondary-button" type="button" :disabled="disabled" @click="openFilePicker">
        {{ file ? '重新选择' : '选择文件' }}
      </button>
      <button
        v-if="camera"
        class="text-button camera-button"
        type="button"
        :disabled="disabled"
        @click="openCamera"
      >
        使用相机
      </button>
    </div>
    <span class="desktop-drop-hint">也可以将文件拖到这里</span>
  </section>
</template>
