import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import AgentNotification from '../AgentNotification.vue'
import type { AgentNotification as AgentNotificationType } from '@/models/agent-notification'

describe('AgentNotification.vue', () => {
  let wrapper: any

  beforeEach(() => {
    wrapper = mount(AgentNotification)
  })

  it('should render empty notification list initially', () => {
    const notifications = wrapper.vm.notifications
    expect(notifications).toEqual([])
  })

  it('should add notification to list', () => {
    const notification: AgentNotificationType = {
      id: 'test-1',
      user_id: 'user-1',
      app_id: 'app-1',
      app_name: 'Test Agent',
      created_at: new Date().toISOString(),
      is_read: false,
    }

    wrapper.vm.addNotification(notification)

    expect(wrapper.vm.notifications).toHaveLength(1)
    expect(wrapper.vm.notifications[0]).toEqual(notification)
  })

  it('should not add duplicate notifications', () => {
    const notification: AgentNotificationType = {
      id: 'test-1',
      user_id: 'user-1',
      app_id: 'app-1',
      app_name: 'Test Agent',
      created_at: new Date().toISOString(),
      is_read: false,
    }

    wrapper.vm.addNotification(notification)
    wrapper.vm.addNotification(notification)

    expect(wrapper.vm.notifications).toHaveLength(1)
  })

  it('should remove notification', () => {
    const notification: AgentNotificationType = {
      id: 'test-1',
      user_id: 'user-1',
      app_id: 'app-1',
      app_name: 'Test Agent',
      created_at: new Date().toISOString(),
      is_read: false,
    }

    wrapper.vm.addNotification(notification)
    expect(wrapper.vm.notifications).toHaveLength(1)

    wrapper.vm.removeNotification('test-1')
    expect(wrapper.vm.notifications).toHaveLength(0)
  })

  it('should auto-hide notification after 10 seconds', async () => {
    vi.useFakeTimers()

    const notification: AgentNotificationType = {
      id: 'test-1',
      user_id: 'user-1',
      app_id: 'app-1',
      app_name: 'Test Agent',
      created_at: new Date().toISOString(),
      is_read: false,
    }

    wrapper.vm.addNotification(notification)
    expect(wrapper.vm.notifications).toHaveLength(1)

    // Fast-forward 10 seconds
    vi.advanceTimersByTime(10000)

    expect(wrapper.vm.notifications).toHaveLength(0)

    vi.useRealTimers()
  })

  it('should render notification with correct content', async () => {
    const notification: AgentNotificationType = {
      id: 'test-1',
      user_id: 'user-1',
      app_id: 'app-1',
      app_name: 'My Awesome Agent',
      created_at: new Date().toISOString(),
      is_read: false,
    }

    wrapper.vm.addNotification(notification)
    await wrapper.vm.$nextTick()

    const notificationElement = wrapper.find('[class*="bg-white"]')
    expect(notificationElement.exists()).toBe(true)
    expect(notificationElement.text()).toContain('Agent构建完成')
    expect(notificationElement.text()).toContain('My Awesome Agent')
  })

  it('should have correct z-index for layering', () => {
    const container = wrapper.find('.fixed')
    const classes = container.classes()

    // Should have z-50 for Agent notifications
    expect(classes).toContain('z-50')
  })

  it('should have correct position for notifications', () => {
    const container = wrapper.find('.fixed')
    const classes = container.classes()

    // Should be positioned at top-4 right-4
    expect(classes).toContain('top-4')
    expect(classes).toContain('right-4')
  })
})
