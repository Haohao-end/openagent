import { afterEach, describe, expect, it, vi } from 'vitest'

const importConfigModule = async () => {
  vi.resetModules()
  return import('@/config')
}

describe('config endpoint resolution', () => {
  afterEach(() => {
    vi.unstubAllEnvs()
    vi.unstubAllGlobals()
  })

  it('uses the configured api prefix and derives the socket endpoint from its base path', async () => {
    vi.stubEnv('VITE_API_PREFIX', 'https://openllm.cloud/api')

    const configModule = await importConfigModule()

    expect(configModule.apiPrefix).toBe('https://openllm.cloud/api')
    expect(configModule.socketConnectionUrl).toBe('https://openllm.cloud')
    expect(configModule.socketPath).toBe('/api/socket.io')
  })

  it('keeps direct localhost api connections on the default socket path', async () => {
    vi.stubEnv('VITE_API_PREFIX', 'http://localhost:5001')

    const configModule = await importConfigModule()

    expect(configModule.apiPrefix).toBe('http://localhost:5001')
    expect(configModule.socketConnectionUrl).toBe('http://localhost:5001')
    expect(configModule.socketPath).toBe('/socket.io')
  })

  it('resolves a relative proxy prefix against the current origin for both rest and websocket', async () => {
    vi.stubEnv('VITE_API_PREFIX', '/api/')
    vi.stubGlobal('location', {
      origin: 'https://openllm.cloud',
    })

    const configModule = await importConfigModule()

    expect(configModule.apiPrefix).toBe('https://openllm.cloud/api')
    expect(configModule.socketConnectionUrl).toBe('https://openllm.cloud')
    expect(configModule.socketPath).toBe('/api/socket.io')
  })

  it('falls back to the current origin api proxy when no env prefix is provided', async () => {
    vi.stubEnv('VITE_API_PREFIX', '')
    vi.stubGlobal('location', {
      origin: 'http://localhost:5173',
    })

    const configModule = await importConfigModule()

    expect(configModule.apiPrefix).toBe('http://localhost:5173/api')
    expect(configModule.socketConnectionUrl).toBe('http://localhost:5173')
    expect(configModule.socketPath).toBe('/api/socket.io')
  })

  it('normalizes trailing slashes on absolute api prefixes', async () => {
    vi.stubEnv('VITE_API_PREFIX', 'https://openllm.cloud/api/')

    const configModule = await importConfigModule()

    expect(configModule.apiPrefix).toBe('https://openllm.cloud/api')
    expect(configModule.socketConnectionUrl).toBe('https://openllm.cloud')
    expect(configModule.socketPath).toBe('/api/socket.io')
  })

  it('rejects malformed non-empty api prefixes so rest and websocket cannot diverge', async () => {
    vi.stubEnv('VITE_API_PREFIX', 'api')

    await expect(importConfigModule()).rejects.toThrow(
      'VITE_API_PREFIX must be an absolute http(s) URL or start with "/"',
    )
  })
})
