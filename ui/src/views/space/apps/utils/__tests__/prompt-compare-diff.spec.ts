import { describe, expect, it } from 'vitest'
import { buildPromptCompareDiff, getPromptCompareLatencyDelta } from '../prompt-compare-diff'

describe('prompt compare diff', () => {
  it('highlights removed and added text while preserving common text', () => {
    expect(buildPromptCompareDiff('Hello old world', 'Hello new world', 'baseline')).toEqual([
      { type: 'equal', text: 'Hello ' },
      { type: 'removed', text: 'old' },
      { type: 'equal', text: ' world' },
    ])
    expect(buildPromptCompareDiff('Hello old world', 'Hello new world', 'candidate')).toEqual([
      { type: 'equal', text: 'Hello ' },
      { type: 'added', text: 'new' },
      { type: 'equal', text: ' world' },
    ])
  })

  it('handles unchanged text and Unicode without splitting surrogate pairs', () => {
    expect(buildPromptCompareDiff('天气 ☀️', '天气 ☀️', 'candidate')).toEqual([
      { type: 'equal', text: '天气 ☀️' },
    ])
    expect(buildPromptCompareDiff('天气', '天气晴朗', 'candidate')).toEqual([
      { type: 'equal', text: '天气' },
      { type: 'added', text: '晴朗' },
    ])
  })

  it('compares the measured elapsed time between lanes', () => {
    expect(getPromptCompareLatencyDelta(1.25, 1.6)).toBe(0.35)
    expect(getPromptCompareLatencyDelta(2.4, 1.2)).toBe(-1.2)
  })
})
