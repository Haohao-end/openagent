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
        baselineErrorType: 'error',
        candidateErrorType: 'timeout',
        baselineTokenCount: 100,
        candidateTokenCount: 118,
      },
    })

    expect(wrapper.find('[data-testid="prompt-compare-diff"]').text()).toContain('最近一次输出差异')
    expect(wrapper.text()).toContain('较默认提示词耗时：+0.45s')
    const errorDiff = wrapper.find('[data-testid="prompt-compare-error-diff"]')
    expect(errorDiff.text()).toContain('错误类型')
    expect(errorDiff.text()).toContain('默认提示词 — 错误')
    expect(errorDiff.text()).toContain('对比提示词 — 超时')
    expect(wrapper.text()).toContain('较默认提示词 Token 数差异：+18')
    expect(wrapper.text()).toContain('The result is old.')
    expect(wrapper.text()).toContain('The result is new.')
    expect(wrapper.find('.bg-red-100').text()).toBe('old')
    expect(wrapper.find('.bg-green-100').text()).toBe('new')
  })

  it('labels an empty response instead of leaving its side blank', () => {
    const wrapper = mount(PromptCompareDiff, {
      props: {
        baselineAnswer: '',
        candidateAnswer: 'Candidate output',
        baselineLatency: 1,
        candidateLatency: 1,
        baselineTokenCount: 12,
        candidateTokenCount: 15,
      },
    })

    expect(wrapper.text()).toContain('无输出')
    expect(wrapper.text()).toContain('Candidate output')
  })

  it('shows a negative token delta when the candidate uses fewer tokens', () => {
    const wrapper = mount(PromptCompareDiff, {
      props: {
        baselineAnswer: 'Answer',
        candidateAnswer: 'Answer',
        baselineLatency: 1,
        candidateLatency: 1,
        baselineTokenCount: 42,
        candidateTokenCount: 37,
      },
    })

    expect(wrapper.text()).toContain('较默认提示词 Token 数差异：-5')
  })
})
