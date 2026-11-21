import { describe, expect, it } from 'vitest'

import { createTestI18n } from '@/i18n'
import type { AppLocale } from '@/i18n/locale'

const keys = ['common.conversation.renameFailed', 'workflowEditor.inputData']

describe('common i18n keys used by chat and workflow components', () => {
  it.each<[AppLocale, string, string]>([
    ['zh-CN', 'common.conversation.renameFailed', '重命名会话失败，请重试。'],
    ['en-US', 'common.conversation.renameFailed', 'Failed to rename conversation. Please try again.'],
    ['zh-CN', 'workflowEditor.inputData', '输入数据'],
    ['en-US', 'workflowEditor.inputData', 'Input Data'],
  ])('resolves %s with the %s message', (locale, key, expected) => {
    const i18n = createTestI18n(locale)

    expect(keys).toContain(key)
    expect(i18n.global.t(key)).toBe(expected)
    expect(i18n.global.t(key)).not.toBe(key)
  })
})
