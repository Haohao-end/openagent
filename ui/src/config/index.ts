type RuntimeLocation = Pick<Location, 'origin'> | undefined

type SocketEndpoint = {
  path: string
  url: string
}

type EndpointResolution = {
  apiBaseUrl: string
  socketEndpoint: SocketEndpoint
}

const LOCAL_API_ORIGIN = 'http://localhost:5001'
const DEFAULT_API_PROXY_PREFIX = '/api'
const DEFAULT_SOCKET_IO_PATH = '/socket.io'
const INVALID_API_PREFIX_MESSAGE = 'VITE_API_PREFIX must be an absolute http(s) URL or start with "/"'

const trimTrailingSlash = (value: string) => {
  return value.replace(/\/+$/, '')
}

const normalizeBasePath = (pathname: string) => {
  const normalized = pathname.trim()
  if (!normalized || normalized === '/') {
    return ''
  }

  const withLeadingSlash = normalized.startsWith('/') ? normalized : `/${normalized}`
  return withLeadingSlash.replace(/\/+$/, '')
}

const resolveLocationOrigin = (loc: RuntimeLocation = globalThis.location) => {
  const origin = loc?.origin?.trim()
  return origin ? trimTrailingSlash(origin) : ''
}

const resolveConfiguredApiUrl = (value: string, loc: RuntimeLocation = globalThis.location) => {
  const normalized = value.trim()
  if (!normalized) {
    return null
  }

  if (/^https?:\/\//iu.test(normalized)) {
    return new URL(normalized)
  }

  if (normalized.startsWith('/')) {
    const origin = resolveLocationOrigin(loc)
    if (!origin) {
      throw new Error('A relative VITE_API_PREFIX requires window.location.origin')
    }
    return new URL(normalized, origin)
  }

  throw new Error(`${INVALID_API_PREFIX_MESSAGE}. Received: ${normalized}`)
}

const buildSocketPath = (apiPathname: string) => {
  const apiBasePath = normalizeBasePath(apiPathname)
  return apiBasePath ? `${apiBasePath}${DEFAULT_SOCKET_IO_PATH}` : DEFAULT_SOCKET_IO_PATH
}

const buildEndpointResolution = (apiUrl: URL): EndpointResolution => {
  const origin = trimTrailingSlash(apiUrl.origin)
  const apiBasePath = normalizeBasePath(apiUrl.pathname)

  return {
    apiBaseUrl: `${origin}${apiBasePath}`,
    socketEndpoint: {
      url: origin,
      path: buildSocketPath(apiUrl.pathname),
    },
  }
}

export function resolveEndpointResolution(
  loc: RuntimeLocation = globalThis.location,
): EndpointResolution {
  const envPrefix = String(import.meta.env.VITE_API_PREFIX || '').trim()
  const resolvedConfiguredUrl = resolveConfiguredApiUrl(envPrefix, loc)
  if (resolvedConfiguredUrl) {
    return buildEndpointResolution(resolvedConfiguredUrl)
  }

  const origin = resolveLocationOrigin(loc)
  if (origin) {
    return {
      apiBaseUrl: `${origin}${DEFAULT_API_PROXY_PREFIX}`,
      socketEndpoint: {
        url: origin,
        path: `${DEFAULT_API_PROXY_PREFIX}${DEFAULT_SOCKET_IO_PATH}`,
      },
    }
  }

  return {
    apiBaseUrl: LOCAL_API_ORIGIN,
    socketEndpoint: {
      url: LOCAL_API_ORIGIN,
      path: DEFAULT_SOCKET_IO_PATH,
    },
  }
}

/**
 * 智能获取 API 前缀
 * 优先级:
 * 1. 环境变量 VITE_API_PREFIX (如果配置了)
 * 2. 当前域名 + /api (通过 Nginx / Vite 代理)
 * 3. 兜底 localhost (开发环境)
 */
export function resolveApiPrefix(loc: RuntimeLocation = globalThis.location): string {
  return resolveEndpointResolution(loc).apiBaseUrl
}

export function resolveSocketEndpoint(loc: RuntimeLocation = globalThis.location): SocketEndpoint {
  return resolveEndpointResolution(loc).socketEndpoint
}

// api请求接口前缀
export const apiPrefix: string = resolveApiPrefix()
export const socketEndpoint: SocketEndpoint = resolveSocketEndpoint()
export const socketConnectionUrl = socketEndpoint.url
export const socketPath = socketEndpoint.path


// 业务状态码
export const httpCode = {
  success: 'success',
  fail: 'fail',
  notFound: 'not_found',
  unauthorized: 'unauthorized',
  forbidden: 'forbidden',
  validateError: 'validate_error',
}

// 类型字符串与中文映射
export const typeMap: { [key: string]: string } = {
  str: '字符串',
  int: '整型',
  float: '浮点型',
  bool: '布尔值',
}

// 智能体事件类型
export const QueueEvent = {
  longTermMemoryRecall: 'long_term_memory_recall',
  agentThought: 'agent_thought',
  agentMessage: 'agent_message',
  agentAction: 'agent_action',
  datasetRetrieval: 'dataset_retrieval',
  agentEnd: 'agent_end',
  stop: 'stop',
  error: 'error',
  timeout: 'timeout',
  ping: 'ping',
}
