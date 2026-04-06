import type { BaseResponse } from '@/models/base'

export type HomeIntentSuggestedAction = {
  label: string
  action: string
  icon: string
}

export type HomeIntentData = {
  intent: string
  confidence: number
  suggested_actions: HomeIntentSuggestedAction[]
  is_default: boolean
}

export type GetHomeIntentResponse = BaseResponse<HomeIntentData>
