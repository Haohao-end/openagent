/**
 * 缓动函数 - easeInOutQuad (先加速后减速)
 * @param t 当前时间 (0-1)
 * @returns 缓动后的值 (0-1)
 */
export const easeInOutQuad = (t: number): number => {
  return t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t
}

/**
 * 计算滚动动画时长
 * @param distance 滚动距离
 * @param baseSpeed 基础速度 (px/ms)
 * @returns 动画时长 (ms)
 */
export const calculateScrollDuration = (distance: number, baseSpeed: number = 1): number => {
  const duration = Math.abs(distance) / baseSpeed
  // 限制在 300-500ms 之间
  return Math.max(300, Math.min(500, duration))
}

/**
 * 平滑滚动到指定位置
 * @param element 滚动容器
 * @param targetScrollY 目标滚动位置
 * @param duration 动画时长 (ms)
 * @param onComplete 完成回调
 */
export const smoothScroll = (
  element: HTMLElement | Window,
  targetScrollY: number,
  duration: number = 400,
  onComplete?: () => void,
): void => {
  const isWindow = element === window
  const startScrollY = isWindow ? window.scrollY : (element as HTMLElement).scrollTop
  const distance = targetScrollY - startScrollY

  if (Math.abs(distance) < 1) {
    onComplete?.()
    return
  }

  let startTime: number | null = null

  const animate = (currentTime: number) => {
    if (startTime === null) {
      startTime = currentTime
    }

    const elapsed = currentTime - startTime
    const progress = Math.min(elapsed / duration, 1)
    const easeProgress = easeInOutQuad(progress)
    const currentScrollY = startScrollY + distance * easeProgress

    if (isWindow) {
      window.scrollTo(0, currentScrollY)
    } else {
      (element as HTMLElement).scrollTop = currentScrollY
    }

    if (progress < 1) {
      requestAnimationFrame(animate)
    } else {
      onComplete?.()
    }
  }

  requestAnimationFrame(animate)
}

/**
 * 获取元素距离容器顶部的距离
 * @param element 目标元素
 * @param container 容器元素 (默认为 window)
 * @returns 距离 (px)
 */
export const getElementScrollPosition = (
  element: HTMLElement,
  container: HTMLElement | Window = window,
): number => {
  const rect = element.getBoundingClientRect()
  const isWindow = container === window
  const containerTop = isWindow ? 0 : (container as HTMLElement).getBoundingClientRect().top
  return rect.top - containerTop + (isWindow ? window.scrollY : (container as HTMLElement).scrollTop)
}
