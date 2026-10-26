import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import PromptCompareDiff from '../PromptCompareDiff.vue'

describe('PromptCompareDiff', () => {
  it('shows removed and added output text with measured latency delta', () => {
    const wrapper = mount(PromptCompareDiff, {
      props: {
        baselineAnswer: 'The result is old.',
        candidateAnswer: 'The result is new.',
        baselineLatency: 1.2,
        candidateLatency: 1.65,
      },
    })

    expect(wrapper.find('[data-testid="prompt-compare-diff"]').text()).toContain('最近一次输出差异')
    expect(wrapper.text()).toContain('较默认提示词耗时：+0.45s')
    expect(wrapper.text()).toContain('The result is old.')
    expect(wrapper.text()).toContain('The result is new.')
    expect(wrapper.find('.bg-red-100').text()).toBe('old')
    expect(wrapper.find('.bg-green-100').text()).toBe('new')
  })
})
