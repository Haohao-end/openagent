import { defineComponent } from 'vue'
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import CardGridSkeleton from '../CardGridSkeleton.vue'

const SlotStub = { template: '<div><slot /></div>' }
const ColStub = defineComponent({
  props: { span: Number, xs: Number, sm: Number, md: Number, lg: Number },
  template: '<div><slot /></div>',
})

describe('CardGridSkeleton', () => {
  it('uses responsive columns for loading cards', () => {
    const wrapper = mount(CardGridSkeleton, {
      props: { count: 4 },
      global: { stubs: { 'a-row': SlotStub, 'a-col': ColStub } },
    })

    expect(wrapper.findAllComponents(ColStub)).toHaveLength(4)
    expect(wrapper.findAllComponents(ColStub)[0].props()).toMatchObject({ xs: 24, sm: 12, md: 8, lg: 6 })
  })
})
