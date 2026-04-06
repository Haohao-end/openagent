import storage from '@/utils/storage'

const DEV_ACCESS_TOKEN =
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI0ZjkzYmViMy0xODQ5LTRmNzYtODgwNC1hYjM2ODE2MDkxYjcifQ.-KfeCdzSIpqJrkGssGOa47AUUcNwfF9lsl-4_ZExXXc'

export const CREDENTIAL_STORAGE_KEY = 'credential'

export type CredentialLike = {
  access_token?: string | null
  expire_at?: number | null
}

type EffectiveAccessTokenOptions = {
  allowDevFallback?: boolean
}

const isDevAccessTokenFallbackEnabled = () => {
  return import.meta.env.DEV && import.meta.env.VITE_ENABLE_DEV_ACCESS_TOKEN === 'true'
}

const getCurrentEpochSeconds = () => Math.floor(Date.now() / 1000)

export const getEffectiveAccessToken = (
  accessToken?: string | null,
  options: EffectiveAccessTokenOptions = {},
): string => {
  const normalizedToken = String(accessToken || '').trim()
  if (normalizedToken) {
    return normalizedToken
  }

  if (options.allowDevFallback && isDevAccessTokenFallbackEnabled()) {
    return DEV_ACCESS_TOKEN
  }

  return ''
}

export const getCredentialAccessToken = (
  credential?: CredentialLike | null,
  options: EffectiveAccessTokenOptions = {},
): string => {
  const accessToken = getEffectiveAccessToken(credential?.access_token, options)
  if (!accessToken) {
    return ''
  }

  if (options.allowDevFallback && !credential?.access_token) {
    return accessToken
  }

  const expireAt = Number(credential?.expire_at || 0)
  if (!expireAt || expireAt <= getCurrentEpochSeconds()) {
    return ''
  }

  return accessToken
}

export const isCredentialLoggedIn = (credential?: CredentialLike | null): boolean => {
  return Boolean(getCredentialAccessToken(credential))
}

export const getStoredCredential = (): CredentialLike | null => {
  return storage.get(CREDENTIAL_STORAGE_KEY, null) as CredentialLike | null
}

export const clearStoredCredential = (): void => {
  storage.remove(CREDENTIAL_STORAGE_KEY)
}

export default {
  isLogin: (): boolean => {
    // 1.从LocalStorage中查找授权凭证信息
    const credential = getStoredCredential()

    // 2.判断授权凭证上是否存在有效 access_token，并判断 token 是否过期
    if (!isCredentialLoggedIn(credential)) {
      // 3.账号未登录，直接移除LocalStorage中的数据，涵盖用户数据+授权凭证
      storage.clear()
      return false
    }
    // 4.满足所有条件，返回true
    return true
  },
}
