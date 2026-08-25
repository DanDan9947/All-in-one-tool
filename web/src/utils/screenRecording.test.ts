import {
  FULL_SELECTION,
  isFullSelection,
  numberedFileName,
  preferredWebmMimeType,
  screenRecordingFileName,
  sourceRectangle,
  transformSelection
} from './screenRecording'

describe('screen recording selection', () => {
  it('moves a selection without leaving the source bounds', () => {
    const moved = transformSelection(
      { x: 0.1, y: 0.2, width: 0.5, height: 0.4 },
      'move',
      0.8,
      -0.5,
      0.05,
      0.05
    )
    expect(moved).toEqual({ x: 0.5, y: 0, width: 0.5, height: 0.4 })
  })

  it('resizes from a corner and keeps the minimum size', () => {
    const resized = transformSelection(
      { x: 0.2, y: 0.2, width: 0.5, height: 0.5 },
      'nw',
      0.8,
      0.8,
      0.1,
      0.1
    )
    expect(resized.x).toBeCloseTo(0.6)
    expect(resized.y).toBeCloseTo(0.6)
    expect(resized.width).toBeCloseTo(0.1)
    expect(resized.height).toBeCloseTo(0.1)
  })

  it('maps a normalized rectangle to source pixels', () => {
    expect(sourceRectangle({ x: 0.25, y: 0.1, width: 0.5, height: 0.75 }, 1920, 1080)).toEqual({
      x: 480,
      y: 108,
      width: 960,
      height: 810
    })
    expect(sourceRectangle(FULL_SELECTION, 1920, 1080)).toEqual({
      x: 0,
      y: 0,
      width: 1920,
      height: 1080
    })
  })

  it('detects when the full source can bypass canvas recording', () => {
    expect(isFullSelection(FULL_SELECTION)).toBe(true)
    expect(isFullSelection({ x: 0, y: 0, width: 0.99, height: 1 })).toBe(false)
  })

  it('chooses the first supported WebM MIME type', () => {
    const original = globalThis.MediaRecorder
    class FakeMediaRecorder {
      static isTypeSupported(value: string) {
        return value.includes('vp8')
      }
    }
    Object.defineProperty(globalThis, 'MediaRecorder', {
      configurable: true,
      value: FakeMediaRecorder
    })
    expect(preferredWebmMimeType()).toBe('video/webm;codecs=vp8,opus')
    Object.defineProperty(globalThis, 'MediaRecorder', {
      configurable: true,
      value: original
    })
  })

  it('generates an MP4 name and numbered collision names', () => {
    const fileName = screenRecordingFileName(new Date(2026, 7, 5, 17, 14, 10))
    expect(fileName).toBe('屏幕录制_20260805_171410.mp4')
    expect(numberedFileName(fileName, 0)).toBe(fileName)
    expect(numberedFileName(fileName, 2)).toBe('屏幕录制_20260805_171410(2).mp4')
  })
})
