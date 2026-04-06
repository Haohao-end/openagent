import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import TagList from '@/components/TagList.vue'

describe('TagList', () => {
  it('renders tags by business priority and respects maxDisplay', () => {
    const wrapper = mount(TagList, {
      props: {
        tags: {
          tech: ['Agent', 'Vue'],
          scene: ['客户服务', '效率工具'],
          ability: ['自动回复'],
          industry: ['零售'],
        },
        maxDisplay: 3,
      },
    })

    expect(wrapper.findAll('.tag-item').map((item) => item.text())).toEqual([
      '客户服务',
      '效率工具',
      '自动回复',
    ])
  })

  it('deduplicates repeated tags and falls back to default style for unknown dimensions', () => {
    const wrapper = mount(TagList, {
      props: {
        tags: {
          scene: ['数据分析'],
          custom: ['数据分析', '企业内部'],
        },
        maxDisplay: 3,
      },
    })

    const items = wrapper.findAll('.tag-item')

    expect(items.map((item) => item.text())).toEqual(['数据分析', '企业内部'])
    expect(items[1]?.classes()).toContain('tag-item--default')
  })

  it('renders nothing when there are no visible tags', () => {
    const wrapper = mount(TagList, {
      props: {
        tags: {},
        maxDisplay: 2,
      },
    })

    expect(wrapper.find('.tag-list').exists()).toBe(false)
  })
})
