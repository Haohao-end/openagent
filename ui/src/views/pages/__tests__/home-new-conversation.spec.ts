import { describe, expect, it, vi } from 'vitest'

import {
  HOME_NEW_CONVERSATION_QUERY_KEY,
  buildHomeNewConversationQuery,
  hasHomeNewConversationQuery,
  normalizeHomeNewConversationToken,
  shouldSkipHomeConversationDelete,
  stripHomeNewConversationQuery,
} from '@/views/pages/home-new-conversation'

describe('home-new-conversation', () => {
  it('builds a timestamped new conversation query', () => {
    expect(buildHomeNewConversationQuery(1710835200000)).toEqual({
      [HOME_NEW_CONVERSATION_QUERY_KEY]: '1710835200000',
    })
  })

  it('uses Date.now by default', () => {
    vi.spyOn(Date, 'now').mockReturnValue(1710835200123)

    expect(buildHomeNewConversationQuery()).toEqual({
      [HOME_NEW_CONVERSATION_QUERY_KEY]: '1710835200123',
    })
  })

  it('normalizes route query values', () => {
    expect(normalizeHomeNewConversationToken('  token-1  ')).toBe('token-1')
    expect(normalizeHomeNewConversationToken(['token-2', 'token-3'])).toBe('token-2')
    expect(normalizeHomeNewConversationToken(undefined)).toBe('')
  })

  it('detects and strips new conversation route state', () => {
    const query = {
      [HOME_NEW_CONVERSATION_QUERY_KEY]: '1710835200000',
      conversation_id: 'old-conversation',
      settings: 'account',
    }

    expect(hasHomeNewConversationQuery(query)).toBe(true)
    expect(stripHomeNewConversationQuery(query)).toEqual({
      settings: 'account',
    })
  })

  it('skips backend deletion only for an initialized empty home conversation', () => {
    expect(
      shouldSkipHomeConversationDelete({
        allowSkip: true,
        hasCompletedInitialHomeLoad: true,
        messagesLength: 0,
        selectedConversationId: '',
        isStreamingResponse: false,
      }),
    ).toBe(true)

    expect(
      shouldSkipHomeConversationDelete({
        allowSkip: true,
        hasCompletedInitialHomeLoad: false,
        messagesLength: 0,
        selectedConversationId: '',
        isStreamingResponse: false,
      }),
    ).toBe(false)

    expect(
      shouldSkipHomeConversationDelete({
        allowSkip: true,
        hasCompletedInitialHomeLoad: true,
        messagesLength: 1,
        selectedConversationId: '',
        isStreamingResponse: false,
      }),
    ).toBe(false)

    expect(
      shouldSkipHomeConversationDelete({
        allowSkip: true,
        hasCompletedInitialHomeLoad: true,
        messagesLength: 0,
        selectedConversationId: 'conversation-1',
        isStreamingResponse: false,
      }),
    ).toBe(false)
  })
})
