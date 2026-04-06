import moment from 'moment'

/**
 * 将 Unix 时间戳（秒）格式化为 Asia/Shanghai 时区的字符串
 * @param timestamp - Unix 时间戳（秒级）
 * @param format - 格式化字符串，默认为 'MM-DD HH:mm'
 * @returns 格式化后的时间字符串
 */
export function formatTimestamp(timestamp: number | null | undefined, format: string = 'MM-DD HH:mm'): string {
  if (!timestamp) {
    return ''
  }

  // 将秒级时间戳转换为毫秒
  const milliseconds = timestamp * 1000

  // 创建 moment 对象并转换为 Asia/Shanghai 时区
  // 使用 UTC 时间戳创建，然后转换为目标时区
  const date = moment.utc(milliseconds).utcOffset(8 * 60) // UTC+8 是 Asia/Shanghai

  return date.format(format)
}

/**
 * 格式化为 'MM-DD HH:mm' 格式
 */
export function formatTimestampShort(timestamp: number | null | undefined): string {
  return formatTimestamp(timestamp, 'MM-DD HH:mm')
}

/**
 * 格式化为 'YYYY-MM-DD HH:mm:ss' 格式
 */
export function formatTimestampLong(timestamp: number | null | undefined): string {
  return formatTimestamp(timestamp, 'YYYY-MM-DD HH:mm:ss')
}

/**
 * 格式化为 'YYYY-MM-DD' 格式
 */
export function formatTimestampDate(timestamp: number | null | undefined): string {
  return formatTimestamp(timestamp, 'YYYY-MM-DD')
}

/**
 * 格式化为 'HH:mm:ss' 格式
 */
export function formatTimestampTime(timestamp: number | null | undefined): string {
  return formatTimestamp(timestamp, 'HH:mm:ss')
}
