import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

describe('CreateOrUpdateAppModal name length', () => {
  it('limits app names to 40 characters and provides localized validation messages', () => {
    const component = readFileSync(resolve(process.cwd(), 'src/views/space/apps/components/CreateOrUpdateAppModal.vue'), 'utf8')
    const en = readFileSync(resolve(process.cwd(), 'src/i18n/messages/en-US.ts'), 'utf8')
    const zh = readFileSync(resolve(process.cwd(), 'src/i18n/messages/zh-CN.ts'), 'utf8')

    expect(component).toContain(':max-length="40"')
    expect(component).toContain('{ max: 40, message: t(\'appStudio.createModal.nameTooLong\') }')
    expect(en).toContain("nameTooLong: 'App name must be 40 characters or fewer'")
    expect(zh).toContain("nameTooLong: '应用名称最多40个字符'")
  })
})
