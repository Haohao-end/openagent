import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

describe('request layer policy', () => {
  it('does not toast errors in base request layer', () => {
    const content = readFileSync(resolve(process.cwd(), 'src/utils/request.ts'), 'utf-8')
    expect(content.includes('Message.error(')).toBe(false)
  })
})
