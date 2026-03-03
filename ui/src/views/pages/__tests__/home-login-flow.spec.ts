import { describe, expect, it } from 'vitest'
import {
  buildHomeConversationQuery,
  resolveHomeLoginNavigation,
  shouldRedirectToOtherPage,
} from '@/views/pages/home-login-flow'

describe('home-login-flow', () => {
  it('builds conversation query from selected id', () => {
    expect(buildHomeConversationQuery('conversation-1')).toEqual({
      conversation_id: 'conversation-1',
    })
    expect(buildHomeConversationQuery('   ')).toEqual({})
  })

  it('detects redirect to non-home page', () => {
    expect(shouldRedirectToOtherPage('/space/apps')).toBe(true)
    expect(shouldRedirectToOtherPage('/home')).toBe(false)
    expect(shouldRedirectToOtherPage('/home?login=1')).toBe(false)
    expect(shouldRedirectToOtherPage('')).toBe(false)
  })

  it('returns redirect decision when redirect target is external to home', () => {
    const decision = resolveHomeLoginNavigation({
      redirectTarget: '/space/apps',
      hasLoginQueryFlag: true,
      hasRouteRedirectParam: true,
      hasRouteTimestampParam: true,
      selectedConversationId: 'conversation-1',
    })

    expect(decision).toEqual({
      type: 'redirect',
      target: '/space/apps',
    })
  })

  it('returns home replace decision when login query params exist', () => {
    const decision = resolveHomeLoginNavigation({
      redirectTarget: '/home',
      hasLoginQueryFlag: true,
      hasRouteRedirectParam: false,
      hasRouteTimestampParam: false,
      selectedConversationId: 'conversation-1',
    })

    expect(decision).toEqual({
      type: 'replace-home',
      query: {
        conversation_id: 'conversation-1',
      },
    })
  })

  it('returns stay-home decision when no navigation mutation is needed', () => {
    const decision = resolveHomeLoginNavigation({
      redirectTarget: '',
      hasLoginQueryFlag: false,
      hasRouteRedirectParam: false,
      hasRouteTimestampParam: false,
      selectedConversationId: '',
    })

    expect(decision).toEqual({
      type: 'stay-home',
    })
  })
})
