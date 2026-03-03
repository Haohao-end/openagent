import { describe, expect, it } from 'vitest'
import { createRequestError, getErrorMessage, isRequestError } from '@/utils/error'

describe('error utils', () => {
  it('creates standardized request errors', () => {
    const error = createRequestError({
      message: '请求失败',
      code: 'fail',
      status: 500,
    })

    expect(isRequestError(error)).toBe(true)
    expect(error.name).toBe('RequestError')
    expect(error.code).toBe('fail')
    expect(error.status).toBe(500)
    expect(getErrorMessage(error, 'fallback')).toBe('请求失败')
  })

  it('prefers nested response message for generic errors', () => {
    const error = {
      response: {
        data: {
          message: '后端返回错误',
        },
      },
      message: '本地错误',
    }

    expect(getErrorMessage(error, 'fallback')).toBe('后端返回错误')
  })

  it('falls back when error shape is unknown', () => {
    expect(getErrorMessage(null, 'fallback')).toBe('fallback')
    expect(getErrorMessage('error', 'fallback')).toBe('fallback')
  })
})
