import { beforeEach, describe, expect, it, vi } from 'vitest'

import { createObjectUrlManager } from './objectUrl'

describe('object url manager', () => {
  beforeEach(() => {
    let count = 0
    URL.createObjectURL = vi.fn(() => `blob:test-${++count}`)
    URL.revokeObjectURL = vi.fn()
  })

  it('revokes the replaced URL and clears the final URL', () => {
    const manager = createObjectUrlManager()
    manager.set(new Blob(['first']))
    manager.set(new Blob(['second']))

    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:test-1')
    expect(manager.current).toBe('blob:test-2')

    manager.clear()
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:test-2')
    expect(manager.current).toBe('')
  })
})
