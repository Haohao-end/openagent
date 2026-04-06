import { type BaseResponse } from '@/models/base'

export type LoginAuthorizationData = {
  access_token?: string
  expire_at?: number
  challenge_required?: boolean
  challenge_id?: string
  challenge_type?: string
  masked_email?: string
  risk_reason?: string
}

// 账号密码登录响应结构
export type PasswordLoginResponse = BaseResponse<LoginAuthorizationData>

export type VerifyLoginChallengeResponse = BaseResponse<LoginAuthorizationData>
