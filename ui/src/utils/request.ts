import { apiPrefix, httpCode } from '@/config'
import router from '@/router'
import { useCredentialStore } from '@/stores/credential'
import { createRequestError, getErrorMessage, isRequestError } from '@/utils/error'

// 1.超时时间为100s
const TIME_OUT = 100000

type QueryValue = string | number | boolean | null | undefined
type RequestParams = object
type RequestBody = BodyInit | Record<string, unknown> | null

type FetchOptionType = Omit<RequestInit, 'body' | 'headers'> & {
  params?: RequestParams
  headers?: HeadersInit
  body?: RequestBody
}

type ApiResponse<T = unknown> = {
  code: string
  message: string
  data: T
}

type StreamEventPayload<TData = unknown> = {
  event: string
  data: TData
}

type UploadOptions = {
  method?: string
  url?: string
  headers?: Record<string, string>
  data?: Document | XMLHttpRequestBodyInit | null
  onprogress?: NonNullable<XMLHttpRequestUpload['onprogress']>
}

type RequestOptions = RequestInit & {
  params?: RequestParams
  body?: RequestBody
  headers: Headers
}

type UnknownRecord = Record<string, unknown>

const isRecord = (value: unknown): value is UnknownRecord => {
  return typeof value === 'object' && value !== null
}

const isApiResponse = (value: unknown): value is ApiResponse => {
  if (!isRecord(value)) return false
  return (
    typeof value.code === 'string' &&
    typeof value.message === 'string' &&
    Object.prototype.hasOwnProperty.call(value, 'data')
  )
}

const isJsonBodyRecord = (body: unknown): body is Record<string, unknown> => {
  if (!isRecord(body)) return false
  return (
    !(body instanceof FormData) &&
    !(body instanceof Blob) &&
    !(body instanceof URLSearchParams) &&
    !(body instanceof ArrayBuffer) &&
    !ArrayBuffer.isView(body)
  )
}

const createDefaultHeaders = () => {
  return new Headers({
    'Content-Type': 'application/json',
  })
}

const mergeHeaders = (customHeaders?: HeadersInit) => {
  const headers = createDefaultHeaders()
  if (!customHeaders) return headers

  const nextHeaders = new Headers(customHeaders)
  nextHeaders.forEach((value, key) => headers.set(key, value))
  return headers
}

const createBaseFetchOptions = (): RequestOptions => {
  return {
    method: 'GET',
    mode: 'cors',
    credentials: 'include',
    headers: createDefaultHeaders(),
    redirect: 'follow',
  }
}

const appendParamsToUrl = (url: string, params?: RequestParams): string => {
  if (!params) return url
  const query = new URLSearchParams()

  Object.entries(params as Record<string, unknown>).forEach(([key, value]) => {
    if (value === null || value === undefined) return
    if (typeof value === 'object') {
      query.append(key, JSON.stringify(value))
      return
    }
    const scalarValue = value as QueryValue
    query.append(key, String(scalarValue))
  })

  const queryString = query.toString()
  if (!queryString) return url

  return url.includes('?') ? `${url}&${queryString}` : `${url}?${queryString}`
}

const normalizeRequestBody = (body: RequestBody | undefined): BodyInit | null | undefined => {
  if (body === undefined || body === null) return body
  if (isJsonBodyRecord(body)) return JSON.stringify(body)
  return body
}

const normalizeUnknownError = (error: unknown, fallback: string) => {
  if (isRequestError(error)) return error
  return createRequestError({
    message: getErrorMessage(error, fallback),
    cause: error,
  })
}

export const AUTH_REQUIRED_EVENT = 'llmops:auth-required'

const emitAuthRequired = (redirect: string) => {
  if (typeof window === 'undefined') return
  window.dispatchEvent(
    new CustomEvent(AUTH_REQUIRED_EVENT, {
      detail: { redirect },
    }),
  )
}

const handleUnauthorized = (clearCredential: () => void) => {
  clearCredential()
  const currentRoute = router.currentRoute.value
  emitAuthRequired(currentRoute.fullPath)
}

const NO_PROMPT_PUBLIC_GET_ROUTE_NAMES = new Set([
  'web-apps-index',
  'store-public-apps-list',
  'store-public-apps-preview',
  'store-public-apps-analysis',
  'store-tools-list',
  'store-workflows-list',
  'store-workflows-preview',
  'openapi-index',
])

const shouldPromptLoginForMethod = (
  method: string | undefined,
  routeName: string,
) => {
  const normalizedMethod = String(method || '').toUpperCase()
  if (normalizedMethod !== 'GET') return true
  return !NO_PROMPT_PUBLIC_GET_ROUTE_NAMES.has(routeName)
}

const buildRequestOptions = (
  fetchOptions: FetchOptionType,
  forceMethod?: string,
): RequestOptions => {
  const headers = mergeHeaders(fetchOptions.headers)
  const options = Object.assign({}, createBaseFetchOptions(), fetchOptions, {
    headers,
  }) as RequestOptions

  if (forceMethod) {
    options.method = forceMethod
  }

  return options
}

const resolveApiUrl = (url: string) => {
  return `${apiPrefix}${url.startsWith('/') ? url : `/${url}`}`
}

// 4.封装基础的fetch请求
const baseFetch = async <T>(url: string, fetchOptions: FetchOptionType): Promise<T> => {
  const options = buildRequestOptions(fetchOptions)
  const { credential, clear: clearCredential } = useCredentialStore()
  let accessToken = credential.access_token

  // 开发环境下，如果没有token，使用测试token
  if (!accessToken && import.meta.env.DEV) {
    accessToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI0ZjkzYmViMy0xODQ5LTRmNzYtODgwNC1hYjM2ODE2MDkxYjcifQ.-KfeCdzSIpqJrkGssGOa47AUUcNwfF9lsl-4_ZExXXc'
  }

  if (accessToken) {
    options.headers.set('Authorization', `Bearer ${accessToken}`)
  }

  const method = String(options.method || 'GET').toUpperCase()
  const requestUrl = appendParamsToUrl(resolveApiUrl(url), method === 'GET' ? options.params : undefined)
  const normalizedBody = method === 'GET' ? undefined : normalizeRequestBody(options.body)

  const { params, body, signal: externalSignal, ...rawRequestInit } = options
  void params
  void body

  let isTimeoutAbort = false
  const controller = new AbortController()
  const timeoutId = globalThis.setTimeout(() => {
    isTimeoutAbort = true
    controller.abort()
  }, TIME_OUT)

  const abortListener = () => controller.abort()
  if (externalSignal) {
    if (externalSignal.aborted) {
      controller.abort()
    } else {
      externalSignal.addEventListener('abort', abortListener, { once: true })
    }
  }

  const requestInit: RequestInit = {
    ...rawRequestInit,
    method,
    signal: controller.signal,
  }

  if (normalizedBody !== undefined) {
    requestInit.body = normalizedBody
    if (normalizedBody instanceof FormData) {
      const headers = new Headers(requestInit.headers)
      headers.delete('Content-Type')
      requestInit.headers = headers
    }
  }

  try {
    const response = await globalThis.fetch(requestUrl, requestInit)
    const json: unknown = await response.json()

    if (!isApiResponse(json)) {
      throw createRequestError({
        message: '响应数据格式错误',
        status: response.status,
        response: json,
      })
    }

    if (json.code === httpCode.success) {
      return json as T
    }

    if (json.code === httpCode.unauthorized) {
      const routeName = String(router.currentRoute.value.name || '')
      if (shouldPromptLoginForMethod(method, routeName)) {
        handleUnauthorized(clearCredential)
      } else {
        clearCredential()
      }
      throw createRequestError({
        message: 'unauthorized',
        code: json.code,
        status: response.status,
        response: json,
      })
    }

    if (json.code === httpCode.notFound) {
      await router.push({ name: 'errors-not-found' })
      throw createRequestError({
        message: json.message || '资源不存在',
        code: json.code,
        status: response.status,
        response: json,
      })
    }

    if (json.code === httpCode.forbidden) {
      await router.push({ name: 'errors-forbidden' })
      throw createRequestError({
        message: json.message || '无权限访问',
        code: json.code,
        status: response.status,
        response: json,
      })
    }

    throw createRequestError({
      message: json.message || '请求失败',
      code: json.code,
      status: response.status,
      response: json,
    })
  } catch (error: unknown) {
    if (isRequestError(error)) {
      throw error
    }

    if (error instanceof DOMException && error.name === 'AbortError') {
      throw createRequestError({
        message: isTimeoutAbort ? '接口已超时' : '请求已取消',
        cause: error,
      })
    }

    throw normalizeUnknownError(error, '请求失败')
  } finally {
    globalThis.clearTimeout(timeoutId)
    externalSignal?.removeEventListener('abort', abortListener)
  }
}

const parseStreamPayload = <TData>(payload: string): TData => {
  return JSON.parse(payload) as TData
}

const handleStream = <TData>(
  response: Response,
  onData: (data: StreamEventPayload<TData>) => void,
): Promise<void> => {
  return new Promise((resolve, reject) => {
    if (!response.ok) {
      reject(
        createRequestError({
          message: '网络请求失败',
          status: response.status,
        }),
      )
      return
    }

    const reader = response.body?.getReader()
    if (!reader) {
      reject(
        createRequestError({
          message: '流式响应不可读',
          status: response.status,
        }),
      )
      return
    }

    const decoder = new TextDecoder('utf-8')
    let buffer = ''
    let event = ''
    let data = ''

    const emitEvent = () => {
      if (event === '' || data === '') return
      const parsedData = parseStreamPayload<TData>(data)
      onData({ event, data: parsedData })
      event = ''
      data = ''
    }

    const read = () => {
      reader
        .read()
        .then((result: ReadableStreamReadResult<Uint8Array>) => {
          if (result.done) {
            try {
              emitEvent()
              resolve()
            } catch (error: unknown) {
              reject(normalizeUnknownError(error, '解析流式数据失败'))
            }
            return
          }

          buffer += decoder.decode(result.value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''

          try {
            lines.forEach((rawLine) => {
              const line = rawLine.trim()
              if (line.startsWith('event:')) {
                event = line.slice(6).trim()
              } else if (line.startsWith('data:')) {
                const payload = line.slice(5).trim()
                data = data ? `${data}\n${payload}` : payload
              }

              // 每个事件以空行结束，只有event和data同时存在才视为完整事件
              if (line === '') {
                emitEvent()
              }
            })
          } catch (error: unknown) {
            reject(normalizeUnknownError(error, '解析流式数据失败'))
            return
          }

          read()
        })
        .catch((error: unknown) => {
          reject(normalizeUnknownError(error, '读取流式数据失败'))
        })
    }

    read()
  })
}

// 5.封装基于post的sse(流式事件响应)请求
export const ssePost = async <TData = unknown, TResponse = unknown>(
  url: string,
  fetchOptions: FetchOptionType,
  onData: (data: StreamEventPayload<TData>) => void,
): Promise<TResponse | void> => {
  const options = buildRequestOptions(fetchOptions, 'POST')
  const { credential, clear: clearCredential } = useCredentialStore()
  const accessToken = credential.access_token
  if (accessToken) {
    options.headers.set('Authorization', `Bearer ${accessToken}`)
  }

  const requestUrl = resolveApiUrl(url)
  const normalizedBody = normalizeRequestBody(options.body)
  const { params, body, ...rawRequestInit } = options
  void params
  void body

  const requestInit: RequestInit = {
    ...rawRequestInit,
    method: 'POST',
  }

  if (normalizedBody !== undefined) {
    requestInit.body = normalizedBody
    if (normalizedBody instanceof FormData) {
      const headers = new Headers(requestInit.headers)
      headers.delete('Content-Type')
      requestInit.headers = headers
    }
  }

  const response = await globalThis.fetch(requestUrl, requestInit)

  if (response.status === 401) {
    handleUnauthorized(clearCredential)
    throw createRequestError({
      message: 'unauthorized',
      code: httpCode.unauthorized,
      status: response.status,
    })
  }

  const contentType = response.headers.get('Content-Type')
  if (contentType?.includes('application/json')) {
    const json: unknown = await response.json()
    if (isApiResponse(json) && json.code === httpCode.unauthorized) {
      handleUnauthorized(clearCredential)
      throw createRequestError({
        message: 'unauthorized',
        code: json.code,
        status: response.status,
        response: json,
      })
    }
    return json as TResponse
  }

  return await handleStream(response, onData)
}

export const upload = <T>(url: string, options: UploadOptions = {}): Promise<T> => {
  const urlWithPrefix = resolveApiUrl(url)

  const defaultOptions: Required<Pick<UploadOptions, 'method' | 'url' | 'headers'>> & {
    data: Document | XMLHttpRequestBodyInit | null
  } = {
    method: 'POST',
    url: urlWithPrefix,
    headers: {},
    data: null,
  }

  const mergedOptions = {
    ...defaultOptions,
    ...options,
    headers: {
      ...defaultOptions.headers,
      ...(options.headers || {}),
    },
  }

  const { credential, clear: clearCredential } = useCredentialStore()
  const accessToken = credential.access_token
  if (accessToken) {
    mergedOptions.headers.Authorization = `Bearer ${accessToken}`
  }

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()

    xhr.open(mergedOptions.method, mergedOptions.url)
    Object.entries(mergedOptions.headers).forEach(([key, value]) => {
      xhr.setRequestHeader(key, value)
    })

    xhr.withCredentials = true
    xhr.responseType = 'json'

    xhr.onreadystatechange = () => {
      if (xhr.readyState !== 4) return

      if (xhr.status !== 200) {
        reject(
          createRequestError({
            message: '上传失败',
            status: xhr.status,
            response: xhr.response,
          }),
        )
        return
      }

      const response: unknown = xhr.response

      // 添加调试日志
      console.log('[Upload] Response:', response)

      if (!isApiResponse(response)) {
        console.error('[Upload] Invalid response format:', response)
        reject(
          createRequestError({
            message: '上传失败: 响应格式错误',
            status: xhr.status,
            response,
          }),
        )
        return
      }

      if (response.code === httpCode.success) {
        resolve(response as T)
        return
      }

      if (response.code === httpCode.unauthorized) {
        handleUnauthorized(clearCredential)
        reject(
          createRequestError({
            message: 'unauthorized',
            code: response.code,
            status: xhr.status,
            response,
          }),
        )
        return
      }

      reject(
        createRequestError({
          message: response.message || '上传失败',
          code: response.code,
          status: xhr.status,
          response,
        }),
      )
    }

    xhr.onerror = () => {
      console.error('[Upload] Network error')
      reject(
        createRequestError({
          message: '网络错误',
          status: xhr.status,
        }),
      )
    }

    xhr.upload.onprogress = mergedOptions.onprogress || null
    xhr.send(mergedOptions.data)
  })
}

export const request = <T>(url: string, options: FetchOptionType = {}) => {
  return baseFetch<T>(url, options)
}

export const get = <T>(url: string, options: FetchOptionType = {}) => {
  return request<T>(url, Object.assign({}, options, { method: 'GET' }))
}

export const post = <T>(url: string, options: FetchOptionType = {}) => {
  return request<T>(url, Object.assign({}, options, { method: 'POST' }))
}
