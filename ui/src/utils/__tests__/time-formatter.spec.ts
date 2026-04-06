import { describe, it, expect } from 'vitest'
import { formatTimestamp, formatTimestampShort, formatTimestampLong, formatTimestampDate, formatTimestampTime } from '@/utils/time-formatter'

describe('time-formatter', () => {
  // 使用一个已知的时间戳进行测试
  // 2024-01-15 14:30:45 UTC 对应的时间戳是 1705329045
  const testTimestamp = 1705329045

  it('should format timestamp to Asia/Shanghai timezone', () => {
    // 2024-01-15 14:30:45 UTC = 2024-01-15 22:30:45 Asia/Shanghai (UTC+8)
    const result = formatTimestamp(testTimestamp, 'YYYY-MM-DD HH:mm:ss')
    expect(result).toBe('2024-01-15 22:30:45')
  })

  it('should format timestamp short format', () => {
    const result = formatTimestampShort(testTimestamp)
    expect(result).toBe('01-15 22:30')
  })

  it('should format timestamp long format', () => {
    const result = formatTimestampLong(testTimestamp)
    expect(result).toBe('2024-01-15 22:30:45')
  })

  it('should format timestamp date format', () => {
    const result = formatTimestampDate(testTimestamp)
    expect(result).toBe('2024-01-15')
  })

  it('should format timestamp time format', () => {
    const result = formatTimestampTime(testTimestamp)
    expect(result).toBe('22:30:45')
  })

  it('should handle null timestamp', () => {
    expect(formatTimestamp(null)).toBe('')
    expect(formatTimestampShort(null)).toBe('')
    expect(formatTimestampLong(null)).toBe('')
    expect(formatTimestampDate(null)).toBe('')
    expect(formatTimestampTime(null)).toBe('')
  })

  it('should handle undefined timestamp', () => {
    expect(formatTimestamp(undefined)).toBe('')
    expect(formatTimestampShort(undefined)).toBe('')
    expect(formatTimestampLong(undefined)).toBe('')
    expect(formatTimestampDate(undefined)).toBe('')
    expect(formatTimestampTime(undefined)).toBe('')
  })

  it('should handle zero timestamp', () => {
    expect(formatTimestamp(0)).toBe('')
    expect(formatTimestampShort(0)).toBe('')
    expect(formatTimestampLong(0)).toBe('')
    expect(formatTimestampDate(0)).toBe('')
    expect(formatTimestampTime(0)).toBe('')
  })
})
