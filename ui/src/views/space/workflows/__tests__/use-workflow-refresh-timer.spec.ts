import { defineComponent } from 'vue'
import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useWorkflowRefreshTimer } from '../use-workflow-refresh-timer'

describe('useWorkflowRefreshTimer', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('cancels a pending workflow refresh when its view unmounts', () => {
    vi.useFakeTimers()
    const refresh = vi.fn()
    const View = defineComponent({
      setup() {
        useWorkflowRefreshTimer()(refresh)
        return () => null
      },
    })
    const wrapper = mount(View)

    wrapper.unmount()
    vi.advanceTimersByTime(500)
    expect(refresh).not.toHaveBeenCalled()
  })
})
