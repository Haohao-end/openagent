import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import OverviewIndicator from '../OverviewIndicator.vue'

describe('OverviewIndicator', () => {
  it('shows unavailable values instead of reporting zero', () => {
    const wrapper = mount(OverviewIndicator, {
      props: { title: 'RAG retrieval latency', data: null, pop: null, unit: 'seconds' },
    })

    expect(wrapper.text().match(/—/g)).toHaveLength(2)
  })
})
