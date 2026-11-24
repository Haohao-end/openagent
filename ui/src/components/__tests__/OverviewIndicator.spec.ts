import { config, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import OverviewIndicator from '../OverviewIndicator.vue'

config.global.stubs = {
  'a-avatar': { template: '<div class="arco-avatar"><slot /></div>' },
  'a-tooltip': { props: ['content'], template: '<div class="arco-tooltip" :data-content="content"><slot /></div>' },
  'icon-question-circle': true,
  'icon-sync': true,
}

describe('OverviewIndicator', () => {
  it('shows unavailable values instead of reporting zero', () => {
    const wrapper = mount(OverviewIndicator, {
      props: { title: 'RAG retrieval latency', help: 'latency tip', data: null, pop: null, unit: 'seconds' },
      slots: { icon: '<span class="custom-icon">icon</span>' },
    })

    expect(wrapper.text().match(/—/g)).toHaveLength(2)
    expect(wrapper.text()).not.toContain('0.00%')
    expect(wrapper.find('.custom-icon').exists()).toBe(true)
    expect(wrapper.find('.arco-tooltip').attributes('data-content')).toBe('latency tip')
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
