import { describe, expect, it } from 'vitest'
import { getContinueConversationOutput } from '@/views/openapi/quick-start'

describe('quick-start documentation examples', () => {
  it('returns english continue conversation output without invalid escapes', () => {
    const en = getContinueConversationOutput('en-US')
    expect(en).toContain('you last said "hello"')
    expect(en).toContain('"answer": "Based on the current conversation')
  })

  it('returns chinese continue conversation output without invalid escapes', () => {
    const zh = getContinueConversationOutput('zh-CN')
    expect(zh).toContain('你上次说的是"你好"')
    expect(zh).toContain('"answer": "根据当前的对话记录')
  })
})
