<script setup lang="ts">
import { onMounted, ref } from 'vue'
import ScrollToTopButton from './ScrollToTopButton.vue'
import IndexNavigator from './IndexNavigator.vue'
import { useScrollNavigation } from '@/composables/useScrollNavigation'

interface Props {
  container?: HTMLElement | Window
  bottomThreshold?: number
  itemSelector?: string // CSS 选择器，用于自动收集导航项
  labels?: string[] // 可选的标签
}

withDefaults(defineProps<Props>(), {
  container: undefined,
  bottomThreshold: 500,
  itemSelector: '[data-scroll-item]',
})

const emit = defineEmits<{
  'item-click': [index: number]
}>()

const containerRef = ref<HTMLElement | null>(null)

const {
  items,
  currentIndex,
  isNearBottom,
  collectItems,
  scrollToTop,
  scrollToItem,
} = useScrollNavigation({
  container: undefined, // 将在 onMounted 中设置
  bottomThreshold: 500,
})

onMounted(() => {
  // 自动收集导航项
  const container = containerRef.value || document.documentElement
  const elements = Array.from(container.querySelectorAll(itemSelector)) as HTMLElement[]

  if (elements.length > 0) {
    collectItems(elements)
  }
})

const handleScrollToTop = () => {
  scrollToTop()
}

const handleItemClick = (index: number) => {
  scrollToItem(index)
  emit('item-click', index)
}
</script>

<template>
  <div ref="containerRef" class="relative">
    <slot />

    <!-- 回到顶部按钮 -->
    <scroll-to-top-button
      :visible="isNearBottom"
      @click="handleScrollToTop"
    />

    <!-- 右侧索引导航 -->
    <index-navigator
      :count="items.length"
      :current-index="currentIndex"
      @item-click="handleItemClick"
    />
  </div>
</template>
