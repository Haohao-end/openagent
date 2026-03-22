<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'

type Theme = 'light' | 'dark' | 'system'

const theme = ref<Theme>('light')
const systemPrefersDark = ref(false)

const isDark = computed(() => {
  if (theme.value === 'system') {
    return systemPrefersDark.value
  }
  return theme.value === 'dark'
})

const toggleTheme = () => {
  if (theme.value === 'light') {
    theme.value = 'dark'
  } else if (theme.value === 'dark') {
    theme.value = 'system'
  } else {
    theme.value = 'light'
  }
}

const setTheme = (newTheme: Theme) => {
  theme.value = newTheme
}

const applyTheme = () => {
  const html = document.documentElement

  if (isDark.value) {
    html.classList.add('dark')
  } else {
    html.classList.remove('dark')
  }

  // Save preference
  localStorage.setItem('theme-preference', theme.value)
}

const detectSystemPreference = () => {
  if (typeof window === 'undefined') return

  const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
  systemPrefersDark.value = mediaQuery.matches

  mediaQuery.addEventListener('change', (e) => {
    systemPrefersDark.value = e.matches
  })
}

const loadSavedTheme = () => {
  if (typeof window === 'undefined') return

  const saved = localStorage.getItem('theme-preference') as Theme | null
  if (saved) {
    theme.value = saved
  }
}

watch(isDark, () => {
  applyTheme()
})

onMounted(() => {
  detectSystemPreference()
  loadSavedTheme()
  applyTheme()
})

defineExpose({
  theme,
  isDark,
  toggleTheme,
  setTheme
})
</script>

<template>
  <div class="flex items-center gap-2">
    <button
      @click="setTheme('light')"
      :class="[
        'p-2 rounded-lg transition-all',
        theme === 'light'
          ? 'bg-blue-600 text-white'
          : 'bg-white/40 backdrop-blur-md border border-white/60 text-gray-700 hover:bg-white/60'
      ]"
      title="Light mode"
    >
      <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
        <path fill-rule="evenodd" d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.707.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.464 5.05l-.707-.707a1 1 0 00-1.414 1.414l.707.707zm5.657-9.193a1 1 0 00-1.414 0l-.707.707A1 1 0 005.05 6.464l.707-.707a1 1 0 011.414 0zM5 6a1 1 0 100-2H4a1 1 0 000 2h1z" clip-rule="evenodd" />
      </svg>
    </button>

    <button
      @click="setTheme('system')"
      :class="[
        'p-2 rounded-lg transition-all',
        theme === 'system'
          ? 'bg-blue-600 text-white'
          : 'bg-white/40 backdrop-blur-md border border-white/60 text-gray-700 hover:bg-white/60'
      ]"
      title="System preference"
    >
      <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
        <path d="M4 3a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2V5a2 2 0 00-2-2H4zm12 12H4l4-8 3 6 2-4 3 6z" />
      </svg>
    </button>

    <button
      @click="setTheme('dark')"
      :class="[
        'p-2 rounded-lg transition-all',
        theme === 'dark'
          ? 'bg-blue-600 text-white'
          : 'bg-white/40 backdrop-blur-md border border-white/60 text-gray-700 hover:bg-white/60'
      ]"
      title="Dark mode"
    >
      <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
        <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z" />
      </svg>
    </button>
  </div>
</template>

<style scoped>
button {
  outline: none;
}
</style>
