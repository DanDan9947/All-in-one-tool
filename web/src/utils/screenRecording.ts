export interface NormalizedRect {
  x: number
  y: number
  width: number
  height: number
}

export type SelectionHandle =
  | 'move'
  | 'n'
  | 'ne'
  | 'e'
  | 'se'
  | 's'
  | 'sw'
  | 'w'
  | 'nw'

export const FULL_SELECTION: NormalizedRect = { x: 0, y: 0, width: 1, height: 1 }

export function isFullSelection(selection: NormalizedRect): boolean {
  return Math.abs(selection.x) < 0.0001 &&
    Math.abs(selection.y) < 0.0001 &&
    Math.abs(selection.width - 1) < 0.0001 &&
    Math.abs(selection.height - 1) < 0.0001
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(maximum, Math.max(minimum, value))
}

export function transformSelection(
  initial: NormalizedRect,
  handle: SelectionHandle,
  deltaX: number,
  deltaY: number,
  minimumWidth: number,
  minimumHeight: number
): NormalizedRect {
  if (handle === 'move') {
    return {
      ...initial,
      x: clamp(initial.x + deltaX, 0, 1 - initial.width),
      y: clamp(initial.y + deltaY, 0, 1 - initial.height)
    }
  }

  let left = initial.x
  let top = initial.y
  let right = initial.x + initial.width
  let bottom = initial.y + initial.height

  if (handle.includes('w')) left = clamp(left + deltaX, 0, right - minimumWidth)
  if (handle.includes('e')) right = clamp(right + deltaX, left + minimumWidth, 1)
  if (handle.includes('n')) top = clamp(top + deltaY, 0, bottom - minimumHeight)
  if (handle.includes('s')) bottom = clamp(bottom + deltaY, top + minimumHeight, 1)

  return { x: left, y: top, width: right - left, height: bottom - top }
}

export function sourceRectangle(
  selection: NormalizedRect,
  videoWidth: number,
  videoHeight: number
): { x: number; y: number; width: number; height: number } {
  const x = Math.round(selection.x * videoWidth)
  const y = Math.round(selection.y * videoHeight)
  return {
    x,
    y,
    width: Math.max(1, Math.min(videoWidth - x, Math.round(selection.width * videoWidth))),
    height: Math.max(1, Math.min(videoHeight - y, Math.round(selection.height * videoHeight)))
  }
}

export function preferredWebmMimeType(): string | null {
  if (typeof MediaRecorder === 'undefined') return null
  const candidates = [
    'video/webm;codecs=vp9,opus',
    'video/webm;codecs=vp8,opus',
    'video/webm'
  ]
  return candidates.find(candidate => MediaRecorder.isTypeSupported(candidate)) ?? null
}

export function screenRecordingFileName(now = new Date()): string {
  const date = [now.getFullYear(), now.getMonth() + 1, now.getDate()]
    .map((value, index) => String(value).padStart(index === 0 ? 4 : 2, '0')).join('')
  const time = [now.getHours(), now.getMinutes(), now.getSeconds()]
    .map(value => String(value).padStart(2, '0')).join('')
  return `屏幕录制_${date}_${time}.mp4`
}

export function numberedFileName(fileName: string, index: number): string {
  if (index <= 0) return fileName
  const dot = fileName.lastIndexOf('.')
  if (dot < 0) return `${fileName}(${index})`
  return `${fileName.slice(0, dot)}(${index})${fileName.slice(dot)}`
}
