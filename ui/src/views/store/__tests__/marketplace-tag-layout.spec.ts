import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

describe('marketplace category tag layout', () => {
  it('keeps app and workflow card tags on one truncated line', () => {
    const publicApps = readFileSync(resolve(process.cwd(), 'src/views/store/public-apps/ListView.vue'), 'utf8')
    const workflows = readFileSync(resolve(process.cwd(), 'src/views/store/workflows/ListView.vue'), 'utf8')

    for (const source of [publicApps, workflows]) {
      expect(source).toContain('h-6 items-center gap-1 overflow-hidden whitespace-nowrap')
      expect(source).toContain('max-w-[7rem] truncate')
      expect(source).toContain(':title="getTagName(tag)"')
    }
  })
})
