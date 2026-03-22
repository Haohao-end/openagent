<script setup lang="ts">
import { onMounted, onUnmounted, ref, computed } from 'vue'

interface Props {
  modelValue?: string
  placeholder?: string
  type?: string
  disabled?: boolean
  readonly?: boolean
  class?: string
}

const props = withDefaults(defineProps<Props>(), {
  type: 'text',
  disabled: false,
  readonly: false,
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
  focus: []
  blur: []
}>()

const inputRef = ref<HTMLInputElement | null>(null)
const borderRef = ref<HTMLDivElement | null>(null)
const isFocused = ref(false)
let animationFrameId: number | null = null

const updateBorderGradient = () => {
  if (!borderRef.value || !isFocused.value) return

  const time = Date.now() * 0.001
  const hue1 = (time * 60) % 360
  const hue2 = (time * 60 + 120) % 360
  const hue3 = (time * 60 + 240) % 360

  const gradient = `conic-gradient(
    from ${hue1}deg,
    hsl(${hue1}, 100%, 50%),
    hsl(${hue2}, 100%, 50%),
    hsl(${hue3}, 100%, 50%),
    hsl(${hue1}, 100%, 50%)
  )`

  borderRef.value.style.background = gradient
}

const animate = () => {
  updateBorderGradient()
  animationFrameId = requestAnimationFrame(animate)
}

const handleFocus = () => {
  isFocused.value = true
  if (animationFrameId === null) {
    animate()
  }
  emit('focus')
}

const handleBlur = () => {
  isFocused.value = false
  emit('blur')
}

const handleInput = (e: Event) => {
  const target = e.target as HTMLInputElement
  emit('update:modelValue', target.value)
}

onMounted(() => {
  if (isFocused.value) {
    animate()
  }
})

onUnmounted(() => {
  if (animationFrameId !== null) {
    cancelAnimationFrame(animationFrameId)
  }
})

const borderOpacity = computed(() => {
  return isFocused.value ? 'opacity-100' : 'opacity-0'
})
</script>

<template>
  <div class="relative w-full">
    <!-- 动态流动边框 -->
    <div
      v-if="isFocused"
      ref="borderRef"
      class="absolute inset-0 rounded-lg p-0.5 pointer-events-none transition-opacity duration-300"
      :class="borderOpacity"
      style="background: conic-gradient(from 0deg, hsl(0, 100%, 50%), hsl(120, 100%, 50%), hsl(240, 100%, 50%), hsl(0, 100%, 50%))"
    >
      <div class="absolute inset-0 rounded-lg bg-white dark:bg-slate-950" />
    </div>

    <!-- 输入框 -->
    <input
      ref="inputRef"
      :value="modelValue"
      :type="type"
      :placeholder="placeholder"
      :disabled="disabled"
      :readonly="readonly"
      :class="[
        'relative w-full px-4 py-2 rounded-lg',
        'bg-white dark:bg-slate-950',
        'border-2 transition-all duration-300',
        isFocused
          ? 'border-transparent shadow-lg'
          : 'border-gray-200 dark:border-slate-700 hover:border-gray-300 dark:hover:border-slate-600',
        'text-gray-900 dark:text-white',
        'placeholder-gray-400 dark:placeholder-gray-500',
        'focus:outline-none',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        props.class,
      ]"
      @focus="handleFocus"
      @blur="handleBlur"
      @input="handleInput"
    />
  </div>
</template>

<style scoped>
input {
  background-clip: padding-box;
}

/* 确保边框动画流畅 */
div {
  transition: background 0.05s linear;
}
</style>
