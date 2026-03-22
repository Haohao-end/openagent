<script setup lang="ts">
interface Props {
  visible: boolean
  onClick?: () => void
}

withDefaults(defineProps<Props>(), {
  visible: false,
})

const emit = defineEmits<{
  click: []
}>()

const handleClick = () => {
  emit('click')
}
</script>

<template>
  <transition
    name="scroll-to-top"
    @enter="(el) => el.style.opacity = '0'"
    @after-enter="(el) => el.style.opacity = '1'"
  >
    <button
      v-if="visible"
      @click="handleClick"
      class="fixed bottom-8 right-8 z-40 w-12 h-12 rounded-full bg-white/40 backdrop-blur-md border border-white/60 hover:bg-white/50 hover:border-white/80 transition-all duration-300 flex items-center justify-center shadow-lg shadow-blue-500/10 hover:shadow-lg hover:shadow-blue-500/20 group"
      aria-label="回到顶部"
    >
      <svg
        class="w-5 h-5 text-gray-700 group-hover:text-blue-600 transition-colors"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M7 16l-4-4m0 0l4-4m-4 4h18"
        />
      </svg>
    </button>
  </transition>
</template>

<style scoped>
.scroll-to-top-enter-active,
.scroll-to-top-leave-active {
  transition: all 300ms ease;
}

.scroll-to-top-enter-from,
.scroll-to-top-leave-to {
  opacity: 0;
  transform: translateY(20px) scale(0.8);
}

.scroll-to-top-enter-to,
.scroll-to-top-leave-from {
  opacity: 1;
  transform: translateY(0) scale(1);
}
</style>
