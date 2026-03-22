<script setup lang="ts">
import { ref } from 'vue'

interface Props {
  modelValue?: boolean
}

defineProps<Props>()
defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const email = ref('')
const isLoading = ref(false)
const message = ref('')
const messageType = ref<'success' | 'error' | ''>('')

const handleSubscribe = async () => {
  if (!email.value || !email.value.includes('@')) {
    message.value = 'Please enter a valid email'
    messageType.value = 'error'
    return
  }

  isLoading.value = true
  try {
    // Simulate API call
    await new Promise(resolve => setTimeout(resolve, 1000))
    message.value = 'Successfully subscribed! Check your email.'
    messageType.value = 'success'
    email.value = ''
    setTimeout(() => {
      message.value = ''
    }, 3000)
  } catch (error) {
    message.value = 'Failed to subscribe. Please try again.'
    messageType.value = 'error'
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div class="w-full max-w-md mx-auto">
    <div class="p-8 rounded-2xl bg-white/40 backdrop-blur-md border border-white/60">
      <h3 class="text-2xl font-bold text-gray-900 mb-2">Stay Updated</h3>
      <p class="text-gray-600 mb-6">Get the latest news and updates delivered to your inbox</p>

      <form @submit.prevent="handleSubscribe" class="space-y-4">
        <div class="relative">
          <input
            v-model="email"
            type="email"
            placeholder="Enter your email"
            class="w-full px-4 py-3 rounded-lg bg-white/50 border border-white/60 text-gray-900 placeholder-gray-500 focus:outline-none focus:border-blue-300 focus:ring-2 focus:ring-blue-200/50 transition-all"
          />
        </div>

        <button
          type="submit"
          :disabled="isLoading"
          class="w-full px-4 py-3 rounded-lg bg-gradient-to-r from-blue-600 to-cyan-600 text-white font-semibold hover:shadow-lg hover:shadow-blue-500/30 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {{ isLoading ? 'Subscribing...' : 'Subscribe' }}
        </button>
      </form>

      <transition name="fade">
        <div
          v-if="message"
          :class="[
            'mt-4 p-3 rounded-lg text-sm font-medium',
            messageType === 'success'
              ? 'bg-green-100/50 text-green-700'
              : 'bg-red-100/50 text-red-700'
          ]"
        >
          {{ message }}
        </div>
      </transition>
    </div>
  </div>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
