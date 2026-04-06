import { formatTimestampLong } from '@/utils/time-formatter'
import { type AccountSessionItem } from '@/models/account'

export type SessionMetaItem = {
  label: string
  value: string
}

const EMPTY_TEXT = '暂无记录'
const LEGACY_UNSUPPORTED_TEXT = '旧凭证暂不支持，请重新登录后查看'
const LEGACY_TYPE_TEXT = '旧版登录凭证'

const formatTime = (timestamp?: number) => formatTimestampLong(timestamp) || EMPTY_TEXT

export const buildSessionMetaItems = (
  session: Pick<AccountSessionItem, 'legacy' | 'created_at' | 'last_active_at' | 'expires_at'>,
): SessionMetaItem[] => {
  if (session.legacy) {
    return [
      { label: '凭证类型', value: LEGACY_TYPE_TEXT },
      { label: '最近登录时间', value: formatTime(session.created_at) },
      { label: '会话到期时间', value: LEGACY_UNSUPPORTED_TEXT },
    ]
  }

  return [
    { label: '首次登录时间', value: formatTime(session.created_at) },
    { label: '最近活跃时间', value: formatTime(session.last_active_at) },
    { label: '会话到期时间', value: formatTime(session.expires_at) },
  ]
}
