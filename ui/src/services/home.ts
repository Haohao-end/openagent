import { get } from '@/utils/request'
import type { GetHomeIntentResponse } from '@/models/home'

export const getHomeIntent = () => {
  return get<GetHomeIntentResponse>(`/home/intent`)
}
