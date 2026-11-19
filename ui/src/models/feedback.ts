import type { BaseResponse } from './base'

export type FeedbackTargetType = 'message' | 'span'
export type FeedbackRating = 1 | -1

export type CreateFeedbackRequest = {
  target_id: string
  target_type: FeedbackTargetType
  rating?: FeedbackRating
  content?: string
}

export type CreateFeedbackData = {
  id: string
}

export type CreateFeedbackResponse = BaseResponse<CreateFeedbackData>
