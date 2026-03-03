type UnknownRecord = Record<string, unknown>

export type RequestError = Error & {
  name: 'RequestError'
  isRequestError: true
  code?: string
  status?: number
  response?: unknown
  cause?: unknown
}

export type CreateRequestErrorOptions = {
  message: string
  code?: string
  status?: number
  response?: unknown
  cause?: unknown
}

const isRecord = (value: unknown): value is UnknownRecord => {
  return typeof value === 'object' && value !== null
}

export const createRequestError = (options: CreateRequestErrorOptions): RequestError => {
  const error = new Error(options.message) as RequestError
  error.name = 'RequestError'
  error.isRequestError = true
  error.code = options.code
  error.status = options.status
  error.response = options.response
  error.cause = options.cause
  return error
}

export const isRequestError = (error: unknown): error is RequestError => {
  return isRecord(error) && error.isRequestError === true
}

const getNestedResponseMessage = (error: UnknownRecord): string | null => {
  const response = error.response
  if (!isRecord(response)) return null
  const data = response.data
  if (!isRecord(data)) return null
  if (typeof data.message !== 'string') return null
  return data.message
}

export const getErrorMessage = (error: unknown, fallback: string): string => {
  if (isRequestError(error)) {
    return error.message || fallback
  }

  if (!isRecord(error)) {
    return fallback
  }

  const responseMessage = getNestedResponseMessage(error)
  if (responseMessage) {
    return responseMessage
  }

  if (typeof error.message === 'string' && error.message.trim() !== '') {
    return error.message
  }

  return fallback
}
