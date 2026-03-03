// 将转义的字符转换成原始字符
import type { GraphEdge, GraphNode } from '@vue-flow/core'

export const unescapeString = (str: string): string => {
  return str
    .replace(/\\n/g, '\n')
    .replace(/\\t/g, '\t')
    .replace(/\\r/g, '\r')
    .replace(/\\'/g, "'")
    .replace(/\\"/g, '"')
    .replace(/\\\\/g, '\\')
}

// 传递数值生成指定长度的随机字符串
export const generateRandomString = (length: number): string => {
  const characters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789' // 可选字符集
  let result = ''

  for (let i = 0; i < length; i++) {
    const randomIndex = Math.floor(Math.random() * characters.length)
    result += characters[randomIndex]
  }

  return result
}

// 构建邻接表，邻接表的key为节点的id，值为该节点的所有直接子节点(后继节点)
export const buildAdjList = (edges: GraphEdge[]): Map<string, string[]> => {
  // 1.构建邻接表，类型为映射
  const adjList = new Map<string, string[]>()

  // 2.循环遍历所有边信息
  edges.forEach((edge) => {
    // 3.如果节点的源节点已存在，则将其目标节点添加到该源节点的子节点列表中
    if (!adjList.has(edge.source)) {
      adjList.set(edge.source, [])
    }
    adjList.get(edge.source)?.push(edge.target)
  })

  return adjList
}

// 构建逆邻接表，逆邻接表的key是每个节点的id，值为该节点的直接父节点
export const buildReverseAdjList = (edges: GraphEdge[]): Map<string, string[]> => {
  // 1.构建逆邻接表，类型为映射
  const reverseAdjList = new Map<string, string[]>()

  // 2.循环遍历所有边信息
  edges.forEach((edge) => {
    // 3.如果节点的目标节点已存在，则将其源节点添加到该目标节点的父节点列表中
    if (!reverseAdjList.has(edge.target)) {
      reverseAdjList.set(edge.target, [])
    }
    reverseAdjList.get(edge.target)?.push(edge.source)
  })

  return reverseAdjList
}

// 根据传递的逆邻接表+目标节点id，获取该节点的所有前置节点
export const getPredecessorsByNodeId = (
  reverseAdjList: Map<string, string[]>,
  targetNodeId: string,
): string[] => {
  // 1.用来标记已访问的所有节点
  const visited = new Set<string>()

  // 2.存储所有前置节点
  const predecessors: string[] = []

  // 3.定义dfs搜索函数
  const dfs = (nodeId: string): void => {
    // 3.1 如果该节点没有被访问过则执行以下逻辑
    if (!visited.has(nodeId)) {
      visited.add(nodeId)

      // 3.2 节点id不等于目标节点id则添加记录
      if (nodeId !== targetNodeId) predecessors.push(nodeId)

      // 3.3 遍历当前节点的所有邻居节点
      const neighbors = reverseAdjList.get(nodeId) || []
      neighbors.forEach((neighbor) => {
        dfs(neighbor)
      })
    }
  }

  // 4.启动深度优先搜索，查找目标节点所在的前置节点
  dfs(targetNodeId)

  return predecessors
}

// 根据传递的节点、边与目标节点id，获取该节点可引用的所有变量信息
export const getReferencedVariables = (
  nodes: GraphNode[],
  edges: GraphEdge[],
  target_node_id: string,
): Record<string, any>[] => {
  // 2.1 构建逆邻接表
  const reverseAdjList = buildReverseAdjList(edges)

  // 2.2 获取当前节点的所有前置节点id
  const predecessors = getPredecessorsByNodeId(reverseAdjList, target_node_id)

  // 2.3 循环遍历节点数据，找出所有前置节点
  const predecessorNodes = nodes.filter((node) => predecessors.includes(node.id))

  // 2.4 遍历节点，提取输出数据变量列表
  const options: any[] = []
  predecessorNodes.forEach((node) => {
    // 2.5 创建节点变量列表
    const node_variables = {
      isGroup: true,
      label: node.data.title,
      options: [] as any,
    }

    // 2.6 根据节点的差异取出可以引用的数据
    if (node.type === 'start') {
      node.data?.inputs.forEach((variable: any) => {
        node_variables.options.push({ label: variable.name, value: `${node.id}/${variable.name}` })
      })
    } else {
      node.data?.outputs.forEach((variable: any) => {
        node_variables.options.push({
          label: `${variable.name}`,
          value: `${node.id}/${variable.name}`,
        })
      })
    }
    options.push(node_variables)
  })

  return options
}
