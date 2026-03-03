export type HomeLoginNavigationDecision =
  | { type: 'redirect'; target: string }
  | { type: 'replace-home'; query: Record<string, string> }
  | { type: 'stay-home' }

export type HomeLoginNavigationInput = {
  redirectTarget: string
  hasLoginQueryFlag: boolean
  hasRouteRedirectParam: boolean
  hasRouteTimestampParam: boolean
  selectedConversationId: string
}

export const buildHomeConversationQuery = (
  selectedConversationId: string,
): Record<string, string> => {
  const normalizedConversationId = String(selectedConversationId || '').trim()
  if (!normalizedConversationId) return {}
  return { conversation_id: normalizedConversationId }
}

export const shouldRedirectToOtherPage = (redirectTarget: string): boolean => {
  if (!redirectTarget) return false
  return redirectTarget !== '/home' && !redirectTarget.startsWith('/home?')
}

export const resolveHomeLoginNavigation = (
  input: HomeLoginNavigationInput,
): HomeLoginNavigationDecision => {
  if (shouldRedirectToOtherPage(input.redirectTarget)) {
    return {
      type: 'redirect',
      target: input.redirectTarget,
    }
  }

  if (input.hasLoginQueryFlag || input.hasRouteRedirectParam || input.hasRouteTimestampParam) {
    return {
      type: 'replace-home',
      query: buildHomeConversationQuery(input.selectedConversationId),
    }
  }

  return {
    type: 'stay-home',
  }
}
