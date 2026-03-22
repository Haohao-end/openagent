import { ref, computed, onMounted, onUnmounted } from 'vue'
import { smoothScroll, calculateScrollDuration, getElementScrollPosition } from '@/utils/scrollAnimation'

export interface ScrollNavigationItem {
  id: string
  element: HTMLElement
  label?: string
}

export interface UseScrollNavigationOptions {
  container?: HTMLElement | Window
  bottomThreshold?: number // 距离底部多远时显示回到顶部按钮 (px)
  observerOptions?: IntersectionObserverInit
}

export const useScrollNavigation = (options: UseScrollNavigationOptions = {}) => {
  const {
    container = window,
    bottomThreshold = 500,
    observerOptions = { threshold: 0.5 },
  } = options

  const items = ref<ScrollNavigationItem[]>([])
  const scrollY = ref(0)
  const currentIndex = ref(-1)
  const isNearBottom = ref(false)
  const isScrolling = ref(false)

  let intersectionObserver: IntersectionObserver | null = null
  let scrollTimeout: ReturnType<typeof setTimeout> | null = null

  // 计算是否接近底部
  const updateNearBottom = () => {
    const isWindow = container === window
    const scrollHeight = isWindow
      ? document.documentElement.scrollHeight
      : (container as HTMLElement).scrollHeight
    const clientHeight = isWindow
      ? window.innerHeight
      : (container as HTMLElement).clientHeight
    const currentScroll = isWindow ? window.scrollY : (container as HTMLElement).scrollTop

    const distanceToBottom = scrollHeight - currentScroll - clientHeight
    isNearBottom.value = distanceToBottom < bottomThreshold
  }

  // 处理滚动事件
  const handleScroll = () => {
    const isWindow = container === window
    scrollY.value = isWindow ? window.scrollY : (container as HTMLElement).scrollTop

    updateNearBottom()

    // 防抖更新
    if (scrollTimeout) clearTimeout(scrollTimeout)
    scrollTimeout = setTimeout(() => {
      isScrolling.value = false
    }, 100)
  }

  // 初始化 Intersection Observer
  const initIntersectionObserver = () => {
    if (typeof IntersectionObserver === 'undefined') return

    intersectionObserver = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          const index = items.value.findIndex((item) => item.element === entry.target)
          if (index !== -1) {
            currentIndex.value = index
          }
        }
      })
    }, observerOptions)

    items.value.forEach((item) => {
      intersectionObserver?.observe(item.element)
    })
  }

  // 收集导航项
  const collectItems = (elements: HTMLElement[], labels?: string[]) => {
    items.value = elements.map((element, index) => ({
      id: `item-${index}`,
      element,
      label: labels?.[index] || String(index + 1),
    }))

    // 重新初始化观察器
    intersectionObserver?.disconnect()
    initIntersectionObserver()
  }

  // 滚动到顶部
  const scrollToTop = () => {
    if (isScrolling.value) return
    isScrolling.value = true

    const duration = calculateScrollDuration(scrollY.value)
    smoothScroll(container, 0, duration, () => {
      isScrolling.value = false
    })
  }

  // 滚动到指定项
  const scrollToItem = (index: number) => {
    if (index < 0 || index >= items.value.length || isScrolling.value) return

    isScrolling.value = true
    const targetPosition = getElementScrollPosition(items.value[index].element, container)
    const distance = Math.abs(targetPosition - scrollY.value)
    const duration = calculateScrollDuration(distance)

    smoothScroll(container, targetPosition, duration, () => {
      isScrolling.value = false
      currentIndex.value = index
    })
  }

  // 挂载
  onMounted(() => {
    const scrollElement = container === window ? window : (container as HTMLElement)
    scrollElement.addEventListener('scroll', handleScroll)
    updateNearBottom()
  })

  // 卸载
  onUnmounted(() => {
    const scrollElement = container === window ? window : (container as HTMLElement)
    scrollElement.removeEventListener('scroll', handleScroll)
    intersectionObserver?.disconnect()
    if (scrollTimeout) clearTimeout(scrollTimeout)
  })

  return {
    items: computed(() => items.value),
    scrollY: computed(() => scrollY.value),
    currentIndex: computed(() => currentIndex.value),
    isNearBottom: computed(() => isNearBottom.value),
    isScrolling: computed(() => isScrolling.value),
    collectItems,
    scrollToTop,
    scrollToItem,
  }
}
