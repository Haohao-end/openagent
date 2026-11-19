import { post } from '@/utils/request'
import type { CreateFeedbackRequest, CreateFeedbackResponse } from '@/models/feedback'

// 提交用户反馈（绑定到 message 或 span）
export const createFeedback = (app_id: string, req: CreateFeedbackRequest) => {
  return post<CreateFeedbackResponse>(`/apps/${app_id}/feedbacks`, { body: req })
}
