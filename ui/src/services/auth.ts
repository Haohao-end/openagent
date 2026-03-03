import { post } from '@/utils/request'
import { type BaseResponse } from '@/models/base'
import { type PasswordLoginResponse } from '@/models/auth'

// 账号密码登录请求
export const passwordLogin = (email: string, password: string) => {
  return post<PasswordLoginResponse>(`/auth/password-login`, {
    body: { email, password },
  })
}

// 退出登录请求
export const logout = () => {
  return post<BaseResponse<any>>(`/auth/logout`)
}

// 发送密码重置验证码
export const sendResetCode = (email: string) => {
  return post<BaseResponse<any>>(`/auth/send-reset-code`, {
    body: { email },
  })
}

// 重置密码
export const resetPassword = (email: string, code: string, new_password: string) => {
  return post<BaseResponse<any>>(`/auth/reset-password`, {
    body: { email, code, new_password },
  })
}
