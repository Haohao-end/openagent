import { ref } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import { useWorkflowNodeSidebar, type SelectedWorkflowNode } from '../use-workflow-node-sidebar'

describe('useWorkflowNodeSidebar', () => {
  it('reopens the panel and refreshes node data when the same node is selected again', () => {
    const currentNode: SelectedWorkflowNode = {
      id: 'node-1',
      type: 'template_transform',
      data: { title: 'Before update' },
    }
    const sidebar = useWorkflowNodeSidebar({
      nodes: ref([currentNode]),
      triggerDraftGraphSave: vi.fn(),
    })

    sidebar.openNodePanel(currentNode)
    sidebar.nodeInfoVisible.value = false

    const refreshedNode: SelectedWorkflowNode = {
      ...currentNode,
      data: { title: 'After update' },
    }
    sidebar.openNodePanel(refreshedNode)

    expect(sidebar.nodeInfoVisible.value).toBe(true)
    expect(sidebar.selectedNode.value?.data.title).toBe('After update')
  })
})
