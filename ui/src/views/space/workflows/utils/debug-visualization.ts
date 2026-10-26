const DEBUG_NODE_CLASS = 'workflow-debug-succeeded'
const DEBUG_EDGE_CLASS = 'workflow-debug-edge-succeeded'
const DEBUG_CLASSES = new Set([DEBUG_NODE_CLASS, DEBUG_EDGE_CLASS])

type DebugCanvasElement = {
  id?: string
  source?: string
  target?: string
  class?: unknown
}

const originalClassFunctions = new WeakMap<DebugCanvasElement, (...args: unknown[]) => unknown>()

const getClassNames = (value: unknown): string[] => {
  if (Array.isArray(value)) return value.filter((item): item is string => typeof item === 'string')
  if (typeof value === 'string') return value.split(/\s+/).filter(Boolean)
  if (value && typeof value === 'object') {
    return Object.entries(value)
      .filter(([, active]) => Boolean(active))
      .map(([className]) => className)
  }
  return []
}

const setClasses = (element: DebugCanvasElement, classes: string[]) => {
  const previousClass = element.class
  const originalClassFunction = originalClassFunctions.get(element)
  const classFunction =
    originalClassFunction ??
    (typeof previousClass === 'function'
      ? (previousClass as (...args: unknown[]) => unknown)
      : undefined)

  if (classFunction) {
    if (classes.length === 0) {
      element.class = originalClassFunction ?? classFunction
      originalClassFunctions.delete(element)
      return
    }
    originalClassFunctions.set(element, classFunction)
    element.class = (...args: unknown[]) => [classFunction(...args), ...classes]
    return
  }

  if (previousClass && typeof previousClass === 'object' && !Array.isArray(previousClass)) {
    const classMap = Object.fromEntries(
      Object.entries(previousClass).filter(([className]) => !DEBUG_CLASSES.has(className)),
    )
    classes.forEach((className) => (classMap[className] = true))
    element.class = Object.keys(classMap).length > 0 ? classMap : undefined
    return
  }

  element.class = classes.length > 0 ? classes : undefined
}

const removeDebugClasses = (element: DebugCanvasElement) => {
  setClasses(
    element,
    getClassNames(element.class).filter((className) => !DEBUG_CLASSES.has(className)),
  )
}

export const clearWorkflowDebugVisualization = (
  nodes: DebugCanvasElement[],
  edges: DebugCanvasElement[],
) => {
  nodes.forEach(removeDebugClasses)
  edges.forEach(removeDebugClasses)
}

export const markWorkflowDebugNodeSucceeded = (nodes: DebugCanvasElement[], nodeId: string) => {
  const node = nodes.find((item) => item.id === nodeId)
  if (!node) return

  setClasses(node, [...new Set([...getClassNames(node.class), DEBUG_NODE_CLASS])])
}

export const markWorkflowDebugEdgeSucceeded = (
  edges: DebugCanvasElement[],
  source: string,
  target: string,
) => {
  const edge = edges.find((item) => item.source === source && item.target === target)
  if (!edge) return

  setClasses(edge, [...new Set([...getClassNames(edge.class), DEBUG_EDGE_CLASS])])
}
