import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import FileDropzone from './FileDropzone.vue'

describe('FileDropzone', () => {
  it('emits the selected file', async () => {
    const wrapper = mount(FileDropzone, {
      props: {
        accept: 'image/png',
        title: '选择图片',
        hint: 'PNG only'
      }
    })
    const file = new File(['image'], 'sample.png', { type: 'image/png' })
    const input = wrapper.find('input:not([capture])')
    Object.defineProperty(input.element, 'files', {
      value: [file],
      configurable: true
    })

    await input.trigger('change')

    expect(wrapper.emitted('select')?.[0]).toEqual([file])
  })

  it('disables both available pickers while processing', () => {
    const wrapper = mount(FileDropzone, {
      props: {
        accept: 'image/*',
        title: '选择图片',
        hint: '选择一张图片',
        camera: true,
        disabled: true
      }
    })

    expect(wrapper.findAll('input').every(input => input.attributes('disabled') !== undefined)).toBe(
      true
    )
    expect(
      wrapper.findAll('button').every(button => button.attributes('disabled') !== undefined)
    ).toBe(true)
  })
})
