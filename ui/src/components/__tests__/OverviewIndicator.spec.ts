import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import OverviewIndicator from '../OverviewIndicator.vue'

describe('OverviewIndicator', () => {
  it('shows unavailable values instead of reporting zero', () => {
    const wrapper = mount(OverviewIndicator, {
      props: { title: 'RAG retrieval latency', data: null, pop: null, unit: 'seconds' },
    })

    expect(wrapper.text().match(/—/g)).toHaveLength(2)
    expect(wrapper.text()).not.toContain('0.00%')
  })

  it('keeps legitimate zero-valued metrics visible', () => {
    const wrapper = mount(OverviewIndicator, {
      props: { title: 'Sample metrics', data: 0, pop: 0, unit: 'seconds' },
    })

    expect(wrapper.find('.text-2xl').text()).toBe('0')
    expect(wrapper.text()).toContain('0.00%')
    expect(wrapper.text()).not.toContain('—')
  })
})
