import { describe, expect, it, vi } from 'vitest'

import { renderBackground } from './image'

describe('renderBackground', () => {
  it('paints the selected background before drawing the cutout', () => {
    const context = {
      clearRect: vi.fn(),
      fillRect: vi.fn(),
      drawImage: vi.fn(),
      fillStyle: ''
    } as unknown as CanvasRenderingContext2D
    const image = {} as CanvasImageSource

    renderBackground(context, image, 640, 800, '#438EDB')

    expect(context.clearRect).toHaveBeenCalledWith(0, 0, 640, 800)
    expect(context.fillStyle).toBe('#438EDB')
    expect(context.fillRect).toHaveBeenCalledWith(0, 0, 640, 800)
    expect(context.drawImage).toHaveBeenCalledWith(image, 0, 0, 640, 800)
  })
})
