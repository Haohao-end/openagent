import { get, post } from '@/utils/request'
import type { RecentConversation } from '@/models/conversation'

export interface SearchConversation extends RecentConversation {
  human_message: string
  ai_message: string
}

export async function searchConversations(query: string, limit: number = 50) {
  return get<SearchConversation[]>('/conversations/search', {
    params: {
      query,
      limit,
    },
  })
}

export async function deleteConversation(conversationId: string) {
  return post(`/conversations/${conversationId}/delete`)
}

export async function updateConversationName(conversationId: string, name: string) {
  return post(`/conversations/${conversationId}/name`, {
    body: { name },
  })
}
