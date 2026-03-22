/**
 * Animation Presets System
 * Provides predefined animation configurations for consistent motion design
 */

export type AnimationPreset = 'subtle' | 'smooth' | 'energetic' | 'minimal'

export interface AnimationConfig {
  duration: number
  delay: number
  easing: string
  intensity: number
}

/**
 * Animation presets for different use cases
 */
export const animationPresets: Record<AnimationPreset, AnimationConfig> = {
  // Minimal animations for accessibility
  minimal: {
    duration: 200,
    delay: 0,
    easing: 'ease-in-out',
    intensity: 0.3
  },

  // Subtle, refined animations
  subtle: {
    duration: 400,
    delay: 0,
    easing: 'cubic-bezier(0.4, 0, 0.2, 1)',
    intensity: 0.5
  },

  // Smooth, flowing animations
  smooth: {
    duration: 600,
    delay: 0,
    easing: 'cubic-bezier(0.25, 0.46, 0.45, 0.94)',
    intensity: 0.7
  },

  // Energetic, noticeable animations
  energetic: {
    duration: 800,
    delay: 0,
    easing: 'cubic-bezier(0.34, 1.56, 0.64, 1)',
    intensity: 1
  }
}

/**
 * Get animation config based on preset
 */
export function getAnimationConfig(preset: AnimationPreset): AnimationConfig {
  return animationPresets[preset]
}

/**
 * Canvas animation configurations
 */
export const canvasAnimations = {
  aurora: {
    gradientShift: 0.0003,
    blobSpeed: 0.0001,
    particleSpeed: 0.3,
    gridSpeed: 0.02,
    noiseIntensity: 0.03
  },
  reduced: {
    gradientShift: 0.00015,
    blobSpeed: 0.00005,
    particleSpeed: 0.15,
    gridSpeed: 0.01,
    noiseIntensity: 0.015
  }
}

/**
 * Transition configurations
 */
export const transitions = {
  fast: 'transition-all duration-200 ease-in-out',
  normal: 'transition-all duration-300 ease-in-out',
  slow: 'transition-all duration-500 ease-in-out',
  smooth: 'transition-all duration-700 cubic-bezier(0.25, 0.46, 0.45, 0.94)'
}

/**
 * Keyframe animations
 */
export const keyframes = {
  fadeIn: `
    @keyframes fadeIn {
      from { opacity: 0; }
      to { opacity: 1; }
    }
  `,
  slideUp: `
    @keyframes slideUp {
      from { transform: translateY(20px); opacity: 0; }
      to { transform: translateY(0); opacity: 1; }
    }
  `,
  slideDown: `
    @keyframes slideDown {
      from { transform: translateY(-20px); opacity: 0; }
      to { transform: translateY(0); opacity: 1; }
    }
  `,
  slideLeft: `
    @keyframes slideLeft {
      from { transform: translateX(20px); opacity: 0; }
      to { transform: translateX(0); opacity: 1; }
    }
  `,
  slideRight: `
    @keyframes slideRight {
      from { transform: translateX(-20px); opacity: 0; }
      to { transform: translateX(0); opacity: 1; }
    }
  `,
  scaleIn: `
    @keyframes scaleIn {
      from { transform: scale(0.95); opacity: 0; }
      to { transform: scale(1); opacity: 1; }
    }
  `,
  pulse: `
    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.5; }
    }
  `,
  bounce: `
    @keyframes bounce {
      0%, 100% { transform: translateY(0); }
      50% { transform: translateY(-10px); }
    }
  `,
  float: `
    @keyframes float {
      0%, 100% { transform: translateY(0px); }
      50% { transform: translateY(-20px); }
    }
  `,
  glow: `
    @keyframes glow {
      0%, 100% { box-shadow: 0 0 5px rgba(59, 130, 246, 0.5); }
      50% { box-shadow: 0 0 20px rgba(59, 130, 246, 0.8); }
    }
  `
}

/**
 * Easing functions
 */
export const easings = {
  linear: 'linear',
  easeIn: 'ease-in',
  easeOut: 'ease-out',
  easeInOut: 'ease-in-out',
  easeInQuad: 'cubic-bezier(0.11, 0, 0.5, 0)',
  easeOutQuad: 'cubic-bezier(0.5, 1, 0.89, 1)',
  easeInOutQuad: 'cubic-bezier(0.45, 0, 0.55, 1)',
  easeInCubic: 'cubic-bezier(0.32, 0, 0.67, 0)',
  easeOutCubic: 'cubic-bezier(0.33, 1, 0.68, 1)',
  easeInOutCubic: 'cubic-bezier(0.65, 0, 0.35, 1)',
  easeInQuart: 'cubic-bezier(0.5, 0, 0.75, 0)',
  easeOutQuart: 'cubic-bezier(0.25, 1, 0.5, 1)',
  easeInOutQuart: 'cubic-bezier(0.76, 0, 0.24, 1)',
  easeInQuint: 'cubic-bezier(0.64, 0, 0.78, 0)',
  easeOutQuint: 'cubic-bezier(0.22, 1, 0.36, 1)',
  easeInOutQuint: 'cubic-bezier(0.83, 0, 0.17, 1)',
  easeInExpo: 'cubic-bezier(0.7, 0, 0.84, 0)',
  easeOutExpo: 'cubic-bezier(0.16, 1, 0.3, 1)',
  easeInOutExpo: 'cubic-bezier(0.87, 0, 0.13, 1)',
  easeInCirc: 'cubic-bezier(0.6, 0.04, 0.98, 0.335)',
  easeOutCirc: 'cubic-bezier(0.075, 0.82, 0.165, 1)',
  easeInOutCirc: 'cubic-bezier(0.85, 0, 0.15, 1)',
  easeInBack: 'cubic-bezier(0.36, 0, 0.66, -0.56)',
  easeOutBack: 'cubic-bezier(0.34, 1.56, 0.64, 1)',
  easeInOutBack: 'cubic-bezier(0.68, -0.55, 0.265, 1.55)'
}

/**
 * Duration presets (in milliseconds)
 */
export const durations = {
  instant: 0,
  fast: 150,
  normal: 300,
  slow: 500,
  slower: 700,
  slowest: 1000
}

/**
 * Delay presets (in milliseconds)
 */
export const delays = {
  none: 0,
  tiny: 50,
  small: 100,
  medium: 200,
  large: 300,
  xl: 500
}

/**
 * Stagger animation helper
 */
export function getStaggerDelay(index: number, baseDelay: number = 50): number {
  return index * baseDelay
}

/**
 * Create CSS animation string
 */
export function createAnimation(
  name: string,
  duration: number,
  easing: string,
  delay: number = 0,
  iterationCount: string = '1'
): string {
  return `${name} ${duration}ms ${easing} ${delay}ms ${iterationCount}`
}

/**
 * Get responsive animation config
 */
export function getResponsiveAnimationConfig(
  isMobile: boolean,
  prefersReduced: boolean
): AnimationPreset {
  if (prefersReduced) return 'minimal'
  if (isMobile) return 'subtle'
  return 'smooth'
}
