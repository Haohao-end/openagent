import { get } from '@/utils/request'
import type { GetAppAnalysisResponse } from '@/models/analysis'

// 获取应用统计分析服务
export const getAppAnalysis = (app_id: string) => {
  return get<GetAppAnalysisResponse>(`/analysis/${app_id}`)
}
