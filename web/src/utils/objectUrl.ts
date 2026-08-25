export interface ObjectUrlManager {
  readonly current: string
  set(blob: Blob): string
  clear(): void
}

export function createObjectUrlManager(): ObjectUrlManager {
  let current = ''
  return {
    get current() {
      return current
    },
    set(blob: Blob) {
      if (current) URL.revokeObjectURL(current)
      current = URL.createObjectURL(blob)
      return current
    },
    clear() {
      if (current) URL.revokeObjectURL(current)
      current = ''
    }
  }
}
