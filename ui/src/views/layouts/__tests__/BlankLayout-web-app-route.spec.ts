import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, onMounted, onUnmounted } from 'vue'
import { createMemoryHistory, createRouter, useRoute } from 'vue-router'
import { describe, expect, it } from 'vitest'
import BlankLayout from '@/views/layouts/BlankLayout.vue'

describe('BlankLayout web app route reuse', () => {
  it('remounts the same route component when the web app token changes', async () => {
    const mountedTokens: string[] = []
    const unmountedTokens: string[] = []
    const WebAppView = defineComponent({
      setup() {
        const route = useRoute()
        const token = String(route.params.token)
        onMounted(() => mountedTokens.push(token))
        onUnmounted(() => unmountedTokens.push(token))
        return () => h('div', String(route.params.token))
      },
    })
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/web-apps/:token', name: 'web-apps-index', component: WebAppView }],
    })

    await router.push('/web-apps/app-a')
    const wrapper = mount(BlankLayout, { global: { plugins: [router] } })
    await flushPromises()
    await router.push('/web-apps/app-b')
    await flushPromises()

    expect(mountedTokens).toEqual(['app-a', 'app-b'])
    expect(unmountedTokens).toEqual(['app-a'])
    expect(wrapper.text()).toBe('app-b')
    wrapper.unmount()
  })
})
