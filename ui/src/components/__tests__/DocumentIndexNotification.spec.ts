import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { markNotificationAsRead } from '@/services/notification'
import DocumentIndexNotification from '../DocumentIndexNotification.vue'
import type { DocumentIndexNotification as DocumentNotificationType } from '@/models/notification'

vi.mock('@/services/notification', () => ({
  markNotificationAsRead: vi.fn().mockResolvedValue(undefined),
}))

describe('DocumentIndexNotification.vue', () => {
  let wrapper: any

  beforeEach(() => {
    vi.clearAllMocks()
    wrapper = mount(DocumentIndexNotification, {
      global: {
        stubs: {
          'icon-close': true,
        },
      },
    })
  })

  it('should render empty notification list initially', () => {
    const notifications = wrapper.vm.notifications
    expect(notifications).toEqual([])
  })

  it('should add success notification', () => {
    const notification: DocumentNotificationType = {
      id: 'doc-1',
      user_id: 'user-1',
      dataset_id: 'dataset-1',
      document_id: 'document-1',
      document_name: 'test.pdf',
      segment_count: 10,
      index_duration: 5.5,
      created_at: new Date().toISOString(),
      status: 'success',
      error_message: '',
      is_read: false,
    }

    wrapper.vm.addNotification(notification)

    expect(wrapper.vm.notifications).toHaveLength(1)
    expect(wrapper.vm.notifications[0]).toEqual(notification)
    expect(markNotificationAsRead).toHaveBeenCalledWith('doc-1')
  })

  it('should add error notification', () => {
    const notification: DocumentNotificationType = {
      id: 'doc-1',
      user_id: 'user-1',
      dataset_id: 'dataset-1',
      document_id: 'document-1',
      document_name: 'test.pdf',
      segment_count: 0,
      index_duration: 2.5,
      created_at: new Date().toISOString(),
      status: 'error',
      error_message: 'File format not supported',
      is_read: false,
    }

    wrapper.vm.addNotification(notification)

    expect(wrapper.vm.notifications).toHaveLength(1)
    expect(wrapper.vm.notifications[0].status).toBe('error')
  })

  it('should not add duplicate notifications', () => {
    const notification: DocumentNotificationType = {
      id: 'doc-1',
      user_id: 'user-1',
      dataset_id: 'dataset-1',
      document_id: 'document-1',
      document_name: 'test.pdf',
      segment_count: 10,
      index_duration: 5.5,
      created_at: new Date().toISOString(),
      status: 'success',
      error_message: '',
      is_read: false,
    }

    wrapper.vm.addNotification(notification)
    wrapper.vm.addNotification(notification)

    expect(wrapper.vm.notifications).toHaveLength(1)
  })

  it('should remove notification', () => {
    const notification: DocumentNotificationType = {
      id: 'doc-1',
      user_id: 'user-1',
      dataset_id: 'dataset-1',
      document_id: 'document-1',
      document_name: 'test.pdf',
      segment_count: 10,
      index_duration: 5.5,
      created_at: new Date().toISOString(),
      status: 'success',
      error_message: '',
      is_read: false,
    }

    wrapper.vm.addNotification(notification)
    expect(wrapper.vm.notifications).toHaveLength(1)

    wrapper.vm.removeNotification('doc-1')
    expect(wrapper.vm.notifications).toHaveLength(0)
  })

  it('should auto-hide notification after 10 seconds', async () => {
    vi.useFakeTimers()

    const notification: DocumentNotificationType = {
      id: 'doc-1',
      user_id: 'user-1',
      dataset_id: 'dataset-1',
      document_id: 'document-1',
      document_name: 'test.pdf',
      segment_count: 10,
      index_duration: 5.5,
      created_at: new Date().toISOString(),
      status: 'success',
      error_message: '',
      is_read: false,
    }

    wrapper.vm.addNotification(notification)
    expect(wrapper.vm.notifications).toHaveLength(1)

    // Fast-forward 10 seconds
    vi.advanceTimersByTime(10000)

    expect(wrapper.vm.notifications).toHaveLength(0)

    vi.useRealTimers()
  })

  it('should render success notification with correct content', async () => {
    const notification: DocumentNotificationType = {
      id: 'doc-1',
      user_id: 'user-1',
      dataset_id: 'dataset-1',
      document_id: 'document-1',
      document_name: 'important.pdf',
      segment_count: 10,
      index_duration: 5.5,
      created_at: new Date().toISOString(),
      status: 'success',
      error_message: '',
      is_read: false,
    }

    wrapper.vm.addNotification(notification)
    await wrapper.vm.$nextTick()

    const notificationElement = wrapper.find('[class*="bg-white"]')
    expect(notificationElement.exists()).toBe(true)
    expect(notificationElement.text()).toContain('文档索引完成')
    expect(notificationElement.text()).toContain('important.pdf')
  })

  it('should render error notification with error message', async () => {
    const notification: DocumentNotificationType = {
      id: 'doc-1',
      user_id: 'user-1',
      dataset_id: 'dataset-1',
      document_id: 'document-1',
      document_name: 'bad.pdf',
      segment_count: 0,
      index_duration: 2.5,
      created_at: new Date().toISOString(),
      status: 'error',
      error_message: 'File format not supported',
      is_read: false,
    }

    wrapper.vm.addNotification(notification)
    await wrapper.vm.$nextTick()

    const notificationElement = wrapper.find('[class*="bg-white"]')
    expect(notificationElement.exists()).toBe(true)
    expect(notificationElement.text()).toContain('文档索引失败')
    expect(notificationElement.text()).toContain('File format not supported')
  })

  it('should have correct z-index for layering (lower than Agent)', () => {
    const container = wrapper.find('.fixed')
    const classes = container.classes()

    // Should have z-40 for Document notifications (lower than Agent's z-50)
    expect(classes).toContain('z-40')
  })

  it('should have correct position for notifications', () => {
    const container = wrapper.find('.fixed')
    const classes = container.classes()

    // Should be positioned at top-4 right-4
    expect(classes).toContain('top-4')
    expect(classes).toContain('right-4')
  })

  it('should display green indicator for success status', async () => {
    const notification: DocumentNotificationType = {
      id: 'doc-1',
      user_id: 'user-1',
      dataset_id: 'dataset-1',
      document_id: 'document-1',
      document_name: 'test.pdf',
      segment_count: 10,
      index_duration: 5.5,
      created_at: new Date().toISOString(),
      status: 'success',
      error_message: '',
      is_read: false,
    }

    wrapper.vm.addNotification(notification)
    await wrapper.vm.$nextTick()

    const statusIndicator = wrapper.find('[class*="bg-green-500"]')
    expect(statusIndicator.exists()).toBe(true)
  })

  it('should display red indicator for error status', async () => {
    const notification: DocumentNotificationType = {
      id: 'doc-1',
      user_id: 'user-1',
      dataset_id: 'dataset-1',
      document_id: 'document-1',
      document_name: 'test.pdf',
      segment_count: 0,
      index_duration: 2.5,
      created_at: new Date().toISOString(),
      status: 'error',
      error_message: 'Error',
      is_read: false,
    }

    wrapper.vm.addNotification(notification)
    await wrapper.vm.$nextTick()

    const statusIndicator = wrapper.find('[class*="bg-red-500"]')
    expect(statusIndicator.exists()).toBe(true)
  })
})
