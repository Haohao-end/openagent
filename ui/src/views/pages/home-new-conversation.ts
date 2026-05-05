import type { LocationQuery, LocationQueryRaw } from 'vue-router'

export const HOME_NEW_CONVERSATION_QUERY_KEY = 'new_conversation'

export const buildHomeNewConversationQuery = (
  timestamp: number = Date.now(),
): Record<string, string> => ({
  [HOME_NEW_CONVERSATION_QUERY_KEY]: String(timestamp),
})

export const normalizeHomeNewConversationToken = (value: unknown): string => {
  const rawValue = Array.isArray(value) ? value[0] : value
  return String(rawValue || '').trim()
}

export const hasHomeNewConversationQuery = (query: LocationQuery): boolean => {
  return normalizeHomeNewConversationToken(query[HOME_NEW_CONVERSATION_QUERY_KEY]) !== ''
}

export const stripHomeNewConversationQuery = (
  query: LocationQuery,
): LocationQueryRaw => {
  const nextQuery: LocationQueryRaw = { ...query }
  delete nextQuery[HOME_NEW_CONVERSATION_QUERY_KEY]
  delete nextQuery.conversation_id
  return nextQuery
}

export type ShouldSkipHomeConversationDeleteInput = {
  allowSkip: boolean
  hasCompletedInitialHomeLoad: boolean
  messagesLength: number
  selectedConversationId: string
  isStreamingResponse: boolean
}

export const shouldSkipHomeConversationDelete = ({
  allowSkip,
  hasCompletedInitialHomeLoad,
  messagesLength,
  selectedConversationId,
  isStreamingResponse,
}: ShouldSkipHomeConversationDeleteInput): boolean => {
  return (
    allowSkip &&
    hasCompletedInitialHomeLoad &&
    messagesLength <= 0 &&
    normalizeHomeNewConversationToken(selectedConversationId) === '' &&
    !isStreamingResponse
  )
}
