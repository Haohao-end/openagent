import { describe, expect, it } from 'vitest'
import { getAuthGuardRedirect } from '@/router'

describe('getAuthGuardRedirect', () => {
  it('allows public routes for anonymous users', () => {
    expect(
      getAuthGuardRedirect({
        routeName: 'pages-home',
        isLoggedIn: false,
      }),
    ).toBeNull()
  })

  it('allows anonymous users to access login-prompt workspace routes', () => {
    expect(
      getAuthGuardRedirect({
        routeName: 'space-apps-list',
        isLoggedIn: false,
      }),
    ).toBeNull()

    expect(
      getAuthGuardRedirect({
        routeName: 'openapi-api-keys-list',
        isLoggedIn: false,
      }),
    ).toBeNull()
  })

  it('redirects anonymous users away from private workspace detail routes', () => {
    expect(
      getAuthGuardRedirect({
        routeName: 'space-apps-detail',
        isLoggedIn: false,
      }),
    ).toEqual({ path: '/home' })

    expect(
      getAuthGuardRedirect({
        routeName: 'space-workflows-detail',
        isLoggedIn: false,
      }),
    ).toEqual({ path: '/home' })
  })

  it('redirects anonymous users away from unnamed private routes by default', () => {
    expect(
      getAuthGuardRedirect({
        routeName: '',
        isLoggedIn: false,
      }),
    ).toEqual({ path: '/home' })
  })

  it('allows authenticated users to access private routes', () => {
    expect(
      getAuthGuardRedirect({
        routeName: 'space-apps-detail',
        isLoggedIn: true,
      }),
    ).toBeNull()
  })
})
