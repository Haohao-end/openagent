import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

describe('AppLayoutView', () => {
  it('wraps the routed app content in a flex-1 container', () => {
    const source = readFileSync(
      resolve(process.cwd(), 'src/views/space/apps/AppLayoutView.vue'),
      'utf8',
    )

    expect(source).toContain('<div class="flex min-h-0 flex-1 overflow-hidden">')
    expect(source).toContain(
      ':key="`${String(route.params?.app_id ?? \'\')}-${draftConfigRefreshToken}`"',
    )
    expect(source).toContain('<router-view')
    expect(source).toContain(':app="app"')
    expect(source).toContain(':published-refresh-token="publishedRefreshToken"')
    expect(source).toContain('watch(')
    expect(source).not.toContain('min-h-screen flex flex-col h-full overflow-hidden')
  })
})
