<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  count: number
  currentIndex: number
}

const props = withDefaults(defineProps<Props>(), {
  count: 0,
  currentIndex: -1,
})

const emit = defineEmits<{
  'item-click': [index: number]
}>()

const items = computed(() => {
  return Array.from({ length: props.count }, (_, i) => i)
})

const handleItemClick = (index: number) => {
  emit('item-click', index)
}

const handleEnter = (el: Element) => {
  const element = el as HTMLElement
  element.style.opacity = '0'
}

const handleAfterEnter = (el: Element) => {
  const element = el as HTMLElement
  element.style.opacity = '1'
}
</script>

<template>
  <transition name="index-navigator" @enter="handleEnter" @after-enter="handleAfterEnter">
    <div
      v-if="count > 0"
      class="fixed right-8 top-1/2 transform -translate-y-1/2 z-40 flex flex-col gap-2"
    >
      <button
        v-for="(_, index) in items"
        :key="index"
        @click="handleItemClick(index)"
        :class="[
          'w-10 h-10 rounded-full font-semibold text-sm transition-all duration-300 flex items-center justify-center',
          currentIndex === index
            ? 'bg-gradient-to-r from-blue-600 to-cyan-600 text-white shadow-lg shadow-blue-500/30'
            : 'bg-white/40 backdrop-blur-md border border-white/60 text-gray-700 hover:bg-white/50 hover:border-white/80 hover:shadow-lg hover:shadow-blue-500/10',
        ]"
        :aria-label="`跳转到第 ${index + 1} 项`"
      >
        {{ index + 1 }}
      </button>
    </div>
  </transition>
</template>

<style scoped>
.index-navigator-enter-active,
.index-navigator-leave-active {
  transition: all 300ms ease;
}

.index-navigator-enter-from,
.index-navigator-leave-to {
  opacity: 0;
  transform: translateY(-20px) translateX(20px);
}

.index-navigator-enter-to,
.index-navigator-leave-from {
  opacity: 1;
  transform: translateY(0) translateX(0);
}
</style>
