import { describe, expect, it } from 'vitest'

import { createTestI18n } from '@/i18n'
import type { AppLocale } from '@/i18n/locale'

const keys = [
  'common.conversation.renameFailed',
  'workflowEditor.inputData',
  'space.tools.loadFailed',
  'space.tools.edit',
  'space.tools.parameters',
  'space.mcp.aiDescriptionRequired',
]

describe('i18n keys rendered by chat, workflow and space pages', () => {
  it.each<[AppLocale, string]>([
    ['zh-CN', 'common.conversation.renameFailed'],
    ['en-US', 'common.conversation.renameFailed'],
    ['zh-CN', 'workflowEditor.inputData'],
    ['en-US', 'workflowEditor.inputData'],
    ['zh-CN', 'space.tools.loadFailed'],
    ['en-US', 'space.tools.loadFailed'],
    ['zh-CN', 'space.tools.edit'],
    ['en-US', 'space.tools.edit'],
    ['zh-CN', 'space.tools.parameters'],
    ['en-US', 'space.tools.parameters'],
    ['zh-CN', 'space.mcp.aiDescriptionRequired'],
    ['en-US', 'space.mcp.aiDescriptionRequired'],
  ])('resolves %s for %s', (locale, key) => {
    const i18n = createTestI18n(locale)
    const message = i18n.global.t(key)

    expect(keys).toContain(key)
    expect(message).not.toBe(key)
    expect(message.trim().length).toBeGreaterThan(0)
  })
})
