export type DebugNodeResult = {
  node_data: {
    node_type?: string
    type?: string
    title?: string
  }
  outputs: unknown
  latency: number
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
