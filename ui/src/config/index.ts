/**
 * 智能获取 API 前缀
 * 优先级:
 * 1. 环境变量 VITE_API_PREFIX (如果配置了)
 * 2. 当前域名 + /api (通过 Nginx 代理)
 * 3. 兜底 localhost (开发环境)
 */
function getApiPrefix(): string {
  // 1. 如果环境变量配置了完整的 API 地址,直接使用
  const envPrefix = import.meta.env.VITE_API_PREFIX
  if (envPrefix && envPrefix.trim() !== '') {
    return envPrefix.trim()
  }

  // 2. 获取当前访问的域名/IP
  const origin = globalThis.location?.origin

  if (origin) {
    // 生产环境或通过 Nginx 访问: 使用当前域名 + /api
    return `${origin}/api`
  }

  // 3. 兜底: 开发环境 localhost
  return 'http://localhost:5001'
}

// api请求接口前缀
export const apiPrefix: string = getApiPrefix()


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
