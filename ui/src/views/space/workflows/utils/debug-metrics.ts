export type DebugNodeResult = {
  node_data: {
    id?: string
    node_type?: string
    type?: string
    title?: string
  }
  status?: string
  outputs: unknown
  latency: number
}

export const formatDebugNodeOutputs = (outputs: unknown): string => {
  if (typeof outputs === 'string') return outputs

  try {
    return JSON.stringify(outputs, null, 2) ?? String(outputs)
  } catch {
    return String(outputs)
  }
}

export const findWorkflowOutputs = (nodeResults: DebugNodeResult[]): unknown => {
  const endNodeResult = nodeResults.find((item) => item.node_data.node_type === 'end')
  return endNodeResult ? endNodeResult.outputs : null
}

export const sumWorkflowLatency = (nodeResults: DebugNodeResult[]): number => {
  return nodeResults.reduce((total, item) => total + item.latency, 0)
}

export const sumWorkflowToolLatency = (nodeResults: DebugNodeResult[]): number => {
  return nodeResults.reduce((total, item) => {
    if (item.node_data.type === 'tool') {
      return total + item.latency
    }
    return total
  }, 0)
}
