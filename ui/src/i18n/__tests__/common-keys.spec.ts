import { describe, expect, it } from 'vitest'

import { createTestI18n } from '@/i18n'
import type { AppLocale } from '@/i18n/locale'

const keys = ['common.conversation.renameFailed']

describe('common i18n keys used by chat and conversation modals', () => {
  it.each<[AppLocale, string]>([
    ['zh-CN', '重命名会话失败，请重试。'],
    ['en-US', 'Failed to rename conversation. Please try again.'],
  ])('resolves the rename failure message in %s', (locale, expected) => {
    const i18n = createTestI18n(locale)

    for (const key of keys) {
      expect(i18n.global.t(key)).toBe(expected)
      expect(i18n.global.t(key)).not.toBe(key)
    }
  })
})
