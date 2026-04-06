import { get, post } from '@/utils/request'
import { type BaseResponse } from '@/models/base'
import {
  type GetAccountLoginHistoryResponse,
  type GetAccountSessionsResponse,
  type GetCurrentUserResponse,
} from '@/models/account'

// 获取当前登录账号信息
export const getCurrentUser = () => {
  return get<GetCurrentUserResponse>(`/account`)
}

// 修改当前登录账号密码
export const updatePassword = (current_password: string, new_password: string) => {
  return post<BaseResponse<any>>(`/account/password`, {
    body: { current_password, new_password },
  })
}

// 修改当前登录账号名称
export const updateName = (name: string) => {
  return post<BaseResponse<any>>(`/account/name`, {
    body: { name },
  })
}

// 修改当前登录账号头像
export const updateAvatar = (avatar: string) => {
  return post<BaseResponse<any>>(`/account/avatar`, {
    body: { avatar },
  })
}

// 发送换绑邮箱验证码
export const sendChangeEmailCode = (email: string) => {
  return post<BaseResponse<any>>(`/account/email/send-code`, {
    body: { email },
  })
}

// 更新当前登录账号邮箱
export const updateEmail = (email: string, code: string, current_password: string = '') => {
  return post<BaseResponse<any>>(`/account/email`, {
    body: { email, code, current_password },
  })
}

// 获取当前账号的登录会话
export const getAccountSessions = () => {
  return get<GetAccountSessionsResponse>(`/account/sessions`)
}

// 获取当前账号最近的登录历史
export const getAccountLoginHistory = (params?: {
  status?: string
  search?: string
  current_page?: number
  page_size?: number
}) => {
  return get<GetAccountLoginHistoryResponse>(`/account/login-history`, {
    params,
  })
}

// 下线指定登录会话
export const revokeAccountSession = (session_id: string) => {
  return post<BaseResponse<any>>(`/account/sessions/${session_id}/revoke`)
}

// 下线除当前设备外的其他会话
export const revokeOtherAccountSessions = () => {
  return post<BaseResponse<any>>(`/account/sessions/revoke-others`)
}

// 解绑当前第三方账号
export const unbindOAuth = (provider_name: string) => {
  return post<BaseResponse<any>>(`/account/oauth/${provider_name}/unbind`)
}
