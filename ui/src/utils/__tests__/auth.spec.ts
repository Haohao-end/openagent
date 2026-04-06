import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  getCredentialAccessToken,
  getEffectiveAccessToken,
  isCredentialLoggedIn,
} from '@/utils/auth'

describe('auth utils', () => {
  afterEach(() => {
    vi.unstubAllEnvs()
  })

  it('returns the normalized access token when provided', () => {
    expect(getEffectiveAccessToken('  token-123  ')).toBe('token-123')
  })

  it('returns an empty string when access token is missing', () => {
    expect(getEffectiveAccessToken()).toBe('')
  })

  it('does not enable dev fallback by default even when env flag is present', () => {
    vi.stubEnv('DEV', true)
    vi.stubEnv('VITE_ENABLE_DEV_ACCESS_TOKEN', 'true')

    expect(getEffectiveAccessToken()).toBe('')
  })

  it('returns the dev fallback token only when explicitly allowed', () => {
    vi.stubEnv('DEV', true)
    vi.stubEnv('VITE_ENABLE_DEV_ACCESS_TOKEN', 'true')

    expect(getEffectiveAccessToken('', { allowDevFallback: true })).toMatch(/^eyJ/)
  })

  it('returns an empty token and logged-out state when the credential is expired', () => {
    expect(
      getCredentialAccessToken({
        access_token: 'expired-token',
        expire_at: Math.floor(Date.now() / 1000) - 60,
      }),
    ).toBe('')
    expect(
      isCredentialLoggedIn({
        access_token: 'expired-token',
        expire_at: Math.floor(Date.now() / 1000) - 60,
      }),
    ).toBe(false)
  })

  it('returns the credential token and logged-in state when the credential is valid', () => {
    const credential = {
      access_token: 'valid-token',
      expire_at: Math.floor(Date.now() / 1000) + 3600,
    }

    expect(getCredentialAccessToken(credential)).toBe('valid-token')
    expect(isCredentialLoggedIn(credential)).toBe(true)
  })
})
