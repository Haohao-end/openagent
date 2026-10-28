import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, nextTick } from 'vue'

import AgentBindingsMarketplacePickerModal from '../AgentBindingsMarketplacePickerModal.vue'
import type { AgentBinding } from '@/models/app'

const mocks = vi.hoisted(() => ({
  getAppsWithPage: vi.fn(),
  getPublicApps: vi.fn(),
}))

vi.mock('@/services/app', () => ({
  getAppsWithPage: (...args: unknown[]) => mocks.getAppsWithPage(...args),
}))

vi.mock('@/services/public-app', () => ({
  getPublicApps: (...args: unknown[]) => mocks.getPublicApps(...args),
}))

vi.mock('@/hooks/use-app', () => ({}))

vi.mock('@arco-design/web-vue', () => ({
  Message: {
    warning: vi.fn(),
    success: vi.fn(),
    error: vi.fn(),
  },
}))

const makePaginator = (current_page: number, total_page: number, total_record: number) => ({
  current_page,
  total_page,
  total_record,
  page_size: 50,
})

const makeOwnApp = (id: string, name: string, overrides: Record<string, unknown> = {}) => ({
  id,
  name,
  icon: '',
  description: `${name} 描述`,
  status: 'published',
  is_public: false,
  ...overrides,
})

const makePublicApp = (id: string, name: string, overrides: Record<string, unknown> = {}) => ({
  id,
  name,
  icon: '',
  description: `${name} 描述`,
  status: 'published',
  is_public: true,
  ...overrides,
})

const deferred = <T,>() => {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise
  })
  return { promise, resolve }
}

const ownAppsResponse = (id: string, name: string) => ({
  data: { list: [makeOwnApp(id, name)], paginator: makePaginator(1, 1, 1) },
})

const publicAppsResponse = (id: string, name: string) => ({
  data: { list: [makePublicApp(id, name)], paginator: makePaginator(1, 1, 1) },
})

const makeSelectedBinding = (appId: string): AgentBinding => ({
  app_id: appId,
  invoke_mode: 'tool',
  name: '',
  icon: '',
  description: '',
  source_scope: 'own',
})

const setScrollMetrics = (
  element: HTMLElement,
  metrics: { scrollTop: number; clientHeight: number; scrollHeight: number },
) => {
  Object.defineProperty(element, 'scrollTop', {
    configurable: true,
    value: metrics.scrollTop,
  })
  Object.defineProperty(element, 'clientHeight', {
    configurable: true,
    value: metrics.clientHeight,
  })
  Object.defineProperty(element, 'scrollHeight', {
    configurable: true,
    value: metrics.scrollHeight,
  })
}

const buttonStub = defineComponent({
  props: {
    disabled: { type: Boolean, default: false },
  },
  emits: ['click'],
  template: '<button :disabled="disabled" @click="$emit(\'click\', $event)"><slot /></button>',
})

const inputSearchStub = defineComponent({
  props: {
    modelValue: { type: String, default: '' },
  },
  emits: ['update:modelValue', 'search'],
  template:
    '<div><input data-testid="search-input" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" /><button data-testid="search-button" @click="$emit(\'search\')">search</button></div>',
})

const modalStub = {
  template: '<div><slot /></div>',
}

const spinStub = {
  template: '<div><slot /></div>',
}

const avatarStub = {
  template: '<div><slot /></div>',
}

const tagStub = {
  template: '<span><slot /></span>',
}

const spaceStub = {
  template: '<div><slot /></div>',
}

const emptyStub = {
  template: '<div><slot /></div>',
}

const globalStubs = {
  'a-modal': modalStub,
  'a-button': buttonStub,
  'a-input-search': inputSearchStub,
  'a-spin': spinStub,
  'a-avatar': avatarStub,
  'a-tag': tagStub,
  'a-space': spaceStub,
  'a-empty': emptyStub,
  'icon-close': true,
  'icon-apps': true,
}

describe('AgentBindingsMarketplacePickerModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loads my published apps and loads the next page when the list scrolls', async () => {
    mocks.getAppsWithPage.mockImplementation(async (params: Record<string, unknown>) => {
      if (Number(params.current_page) === 1) {
        return {
          data: {
            list: [makeOwnApp('own-1', '北京旅行助手'), makeOwnApp('own-2', '周末规划师')],
            paginator: makePaginator(1, 2, 3),
          },
        }
      }

      if (Number(params.current_page) === 2) {
        return {
          data: {
            list: [makeOwnApp('own-3', '城市路线师')],
            paginator: makePaginator(2, 2, 3),
          },
        }
      }

      throw new Error(`unexpected own page: ${String(params.current_page)}`)
    })

    const wrapper = mount(AgentBindingsMarketplacePickerModal, {
      props: {
        visible: true,
        selected_bindings: [makeSelectedBinding('own-1')],
        current_app_id: 'current-app',
      },
      global: {
        stubs: globalStubs,
      },
    })

    await flushPromises()
    await nextTick()

    expect(mocks.getAppsWithPage).toHaveBeenCalledWith(
      expect.objectContaining({
        current_page: 1,
        page_size: 50,
        search_word: '',
        published_only: true,
      }),
    )
    expect(wrapper.text()).toContain('北京旅行助手')
    expect(wrapper.text()).toContain('周末规划师')
    expect(wrapper.text()).toContain('已添加')

    const ownList = wrapper.get('[data-testid="agent-binding-list"]').element as HTMLElement
    setScrollMetrics(ownList, {
      scrollTop: 1000,
      clientHeight: 400,
      scrollHeight: 1300,
    })
    await wrapper.get('[data-testid="agent-binding-list"]').trigger('scroll')
    await flushPromises()
    await nextTick()

    expect(mocks.getAppsWithPage).toHaveBeenCalledWith(
      expect.objectContaining({
        current_page: 2,
        page_size: 50,
        search_word: '',
        published_only: true,
      }),
    )
    expect(wrapper.text()).toContain('城市路线师')
  })

  it('switches to the public marketplace and keeps loading more pages', async () => {
    mocks.getAppsWithPage.mockResolvedValue({
      data: {
        list: [makeOwnApp('own-1', '北京旅行助手')],
        paginator: makePaginator(1, 1, 1),
      },
    })

    mocks.getPublicApps.mockImplementation(async (params: Record<string, unknown>) => {
      if (Number(params.current_page) === 1) {
        return {
          data: {
            list: [makePublicApp('public-1', '应用广场一号')],
            paginator: makePaginator(1, 2, 2),
          },
        }
      }

      if (Number(params.current_page) === 2) {
        return {
          data: {
            list: [makePublicApp('public-2', '应用广场二号')],
            paginator: makePaginator(2, 2, 2),
          },
        }
      }

      throw new Error(`unexpected public page: ${String(params.current_page)}`)
    })

    const wrapper = mount(AgentBindingsMarketplacePickerModal, {
      props: {
        visible: true,
        selected_bindings: [],
        current_app_id: 'current-app',
      },
      global: {
        stubs: globalStubs,
      },
    })

    await flushPromises()
    await nextTick()

    await wrapper.get('[data-testid="agent-source-public"]').trigger('click')
    await flushPromises()
    await nextTick()

    expect(mocks.getPublicApps).toHaveBeenCalledWith(
      expect.objectContaining({
        current_page: 1,
        page_size: 50,
        search_word: '',
      }),
    )
    expect(wrapper.text()).toContain('应用广场一号')
    expect(wrapper.text()).toContain('A2A')

    const publicList = wrapper.get('[data-testid="agent-binding-list"]').element as HTMLElement
    setScrollMetrics(publicList, {
      scrollTop: 1000,
      clientHeight: 400,
      scrollHeight: 1300,
    })
    await wrapper.get('[data-testid="agent-binding-list"]').trigger('scroll')
    await flushPromises()
    await nextTick()

    expect(mocks.getPublicApps).toHaveBeenCalledWith(
      expect.objectContaining({
        current_page: 2,
        page_size: 50,
        search_word: '',
      }),
    )
    expect(wrapper.text()).toContain('应用广场二号')
  })

  it('refreshes my-app search while the previous request is pending', async () => {
    const oldRequest = deferred<ReturnType<typeof ownAppsResponse>>()
    const newRequest = deferred<ReturnType<typeof ownAppsResponse>>()
    mocks.getAppsWithPage.mockReturnValueOnce(oldRequest.promise).mockReturnValueOnce(newRequest.promise)

    const wrapper = mount(AgentBindingsMarketplacePickerModal, {
      props: { visible: true, selected_bindings: [], current_app_id: 'current-app' },
      global: { stubs: globalStubs },
    })
    await nextTick()
    await wrapper.get('[data-testid="search-input"]').setValue('new query')
    await wrapper.get('[data-testid="search-button"]').trigger('click')
    await nextTick()
    const callsAfterSearch = mocks.getAppsWithPage.mock.calls.length

    newRequest.resolve(ownAppsResponse('new-app', 'New Own App'))
    await flushPromises()
    oldRequest.resolve(ownAppsResponse('old-app', 'Old Own App'))
    await flushPromises()

    expect(callsAfterSearch).toBe(2)
    expect(mocks.getAppsWithPage.mock.calls[1][0].search_word).toBe('new query')
    expect(wrapper.text()).toContain('New Own App')
    expect(wrapper.text()).not.toContain('Old Own App')
    wrapper.unmount()
  })

  it('refreshes public-app search while the previous request is pending', async () => {
    mocks.getAppsWithPage.mockResolvedValue(ownAppsResponse('own-app', 'Own App'))
    const oldRequest = deferred<ReturnType<typeof publicAppsResponse>>()
    const newRequest = deferred<ReturnType<typeof publicAppsResponse>>()
    mocks.getPublicApps.mockReturnValueOnce(oldRequest.promise).mockReturnValueOnce(newRequest.promise)

    const wrapper = mount(AgentBindingsMarketplacePickerModal, {
      props: { visible: true, selected_bindings: [], current_app_id: 'current-app' },
      global: { stubs: globalStubs },
    })
    await flushPromises()
    await wrapper.get('[data-testid="agent-source-public"]').trigger('click')
    await nextTick()
    await wrapper.get('[data-testid="search-input"]').setValue('new query')
    await wrapper.get('[data-testid="search-button"]').trigger('click')
    await nextTick()
    const callsAfterSearch = mocks.getPublicApps.mock.calls.length

    newRequest.resolve(publicAppsResponse('new-app', 'New Public App'))
    await flushPromises()
    oldRequest.resolve(publicAppsResponse('old-app', 'Old Public App'))
    await flushPromises()

    expect(callsAfterSearch).toBe(2)
    expect(mocks.getPublicApps.mock.calls[1][0].search_word).toBe('new query')
    expect(wrapper.text()).toContain('New Public App')
    expect(wrapper.text()).not.toContain('Old Public App')
    wrapper.unmount()
  })
})
