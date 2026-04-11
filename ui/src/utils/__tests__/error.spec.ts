import { describe, expect, it } from 'vitest'
import {
  createRequestError,
  getErrorCode,
  getErrorMessage,
  getErrorReasonCode,
  getErrorResponseData,
  isRequestError,
} from '@/utils/error'

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

  it('extracts structured error data and reason codes', () => {
    const error = createRequestError({
      message: '账号不存在或者密码错误',
      code: 'fail',
      response: {
        code: 'fail',
        message: '账号不存在或者密码错误',
        data: {
          reason_code: 'INVALID_CREDENTIALS',
          providers: ['google'],
        },
      },
    })

    expect(getErrorCode(error)).toBe('fail')
    expect(getErrorReasonCode(error)).toBe('INVALID_CREDENTIALS')
    expect(getErrorResponseData(error)).toEqual({
      reason_code: 'INVALID_CREDENTIALS',
      providers: ['google'],
    })
  })

  it('falls back when error shape is unknown', () => {
    expect(getErrorMessage(null, 'fallback')).toBe('fallback')
    expect(getErrorMessage('error', 'fallback')).toBe('fallback')
    expect(getErrorReasonCode(null)).toBeNull()
    expect(getErrorCode('error')).toBeNull()
  })
})
