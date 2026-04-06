import { describe, expect, it } from 'vitest'
import { buildSessionMetaItems } from '@/views/layouts/components/setting-session-display'

describe('setting-session-display', () => {
  it('should build normal session meta items', () => {
    const items = buildSessionMetaItems({
      legacy: false,
      created_at: 1704067200,
      last_active_at: 1704070800,
      expires_at: 1706659200,
    })

    expect(items).toEqual([
      { label: '首次登录时间', value: '2024-01-01 08:00:00' },
      { label: '最近活跃时间', value: '2024-01-01 09:00:00' },
      { label: '会话到期时间', value: '2024-01-31 08:00:00' },
    ])
  })

  it('should build legacy session meta items with compatibility copy', () => {
    const items = buildSessionMetaItems({
      legacy: true,
      created_at: 1704067200,
      last_active_at: 1704067200,
      expires_at: 0,
    })

    expect(items).toEqual([
      { label: '凭证类型', value: '旧版登录凭证' },
      { label: '最近登录时间', value: '2024-01-01 08:00:00' },
      { label: '会话到期时间', value: '旧凭证暂不支持，请重新登录后查看' },
    ])
  })
})
