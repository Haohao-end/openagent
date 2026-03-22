/**
 * Performance Optimization Utilities
 * Provides utilities for optimizing animations and rendering
 */

/**
 * Debounce function to limit function calls
 */
export function debounce<T extends (...args: any[]) => any>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: ReturnType<typeof setTimeout> | null = null

  return function executedFunction(...args: Parameters<T>) {
    const later = () => {
      timeout = null
      func(...args)
    }

    if (timeout) clearTimeout(timeout)
    timeout = setTimeout(later, wait)
  }
}

/**
 * Throttle function to limit function calls
 */
export function throttle<T extends (...args: any[]) => any>(
  func: T,
  limit: number
): (...args: Parameters<T>) => void {
  let inThrottle: boolean = false

  return function executedFunction(...args: Parameters<T>) {
    if (!inThrottle) {
      func(...args)
      inThrottle = true
      setTimeout(() => (inThrottle = false), limit)
    }
  }
}

/**
 * Request animation frame wrapper with fallback
 */
export function requestFrame(callback: FrameRequestCallback): number {
  return typeof window !== 'undefined' && window.requestAnimationFrame
    ? window.requestAnimationFrame(callback)
    : window.setTimeout(callback, 16)
}

/**
 * Cancel animation frame with fallback
 */
export function cancelFrame(id: number): void {
  if (typeof window !== 'undefined') {
    if (window.cancelAnimationFrame) {
      window.cancelAnimationFrame(id)
    } else {
      window.clearTimeout(id)
    }
  }
}

/**
 * Detect if user prefers reduced motion
 */
export function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined') return false
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

/**
 * Lazy load images
 */
export function lazyLoadImage(img: HTMLImageElement): void {
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          const image = entry.target as HTMLImageElement
          image.src = image.dataset.src || ''
          image.classList.remove('lazy')
          observer.unobserve(image)
        }
      })
    })
    observer.observe(img)
  } else {
    img.src = img.dataset.src || ''
  }
}

/**
 * Measure performance
 */
export function measurePerformance(label: string): () => void {
  const start = performance.now()

  return () => {
    const end = performance.now()
    console.log(`${label}: ${(end - start).toFixed(2)}ms`)
  }
}

/**
 * Adaptive animation based on device capabilities
 */
export function getAnimationDuration(baseMs: number): number {
  if (prefersReducedMotion()) {
    return 0
  }

  // Reduce animation duration on mobile devices
  if (typeof window !== 'undefined' && window.innerWidth < 768) {
    return Math.max(baseMs * 0.7, 100)
  }

  return baseMs
}

/**
 * Adaptive particle count based on device
 */
export function getAdaptiveParticleCount(baseCount: number): number {
  if (typeof window === 'undefined') return baseCount

  const width = window.innerWidth
  const height = window.innerHeight

  // Reduce particles on mobile
  if (width < 768) {
    return Math.floor(baseCount * 0.5)
  }

  // Reduce particles on low-end devices
  if ((navigator as any).deviceMemory && (navigator as any).deviceMemory < 4) {
    return Math.floor(baseCount * 0.7)
  }

  return baseCount
}

/**
 * Check if device has high refresh rate
 */
export function hasHighRefreshRate(): boolean {
  if (typeof window === 'undefined') return false
  return (window.screen as any).refreshRate > 60
}

/**
 * Optimize blur effect based on device
 */
export function getOptimalBlurValue(baseBlur: number): number {
  if (prefersReducedMotion()) {
    return 0
  }

  // Reduce blur on low-end devices
  if ((navigator as any).deviceMemory && (navigator as any).deviceMemory < 4) {
    return Math.max(baseBlur * 0.5, 2)
  }

  return baseBlur
}

/**
 * Batch DOM updates
 */
export function batchDOMUpdates(updates: () => void): void {
  if (typeof window !== 'undefined' && window.requestAnimationFrame) {
    window.requestAnimationFrame(updates)
  } else {
    updates()
  }
}

/**
 * Intersection Observer helper
 */
export function observeElement(
  element: Element,
  callback: (isVisible: boolean) => void,
  options?: IntersectionObserverInit
): () => void {
  if (!('IntersectionObserver' in window)) {
    callback(true)
    return () => {}
  }

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        callback(entry.isIntersecting)
      })
    },
    options
  )

  observer.observe(element)

  return () => observer.disconnect()
}

/**
 * Memory-efficient event listener
 */
export function addEventListenerOnce(
  element: Element | Window,
  event: string,
  handler: EventListener,
  options?: AddEventListenerOptions
): () => void {
  element.addEventListener(event, handler, options)

  return () => {
    element.removeEventListener(event, handler, options)
  }
}
