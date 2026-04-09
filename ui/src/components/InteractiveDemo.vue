<script setup lang="ts">
import { ref, nextTick, computed } from 'vue'

interface Message {
  id: string
  type: 'user' | 'ai'
  content: string
  timestamp: Date
}

const messages = ref<Message[]>([
  {
    id: '1',
    type: 'ai',
    content: "Hello! I'm your AI assistant. How can I help you today?",
    timestamp: new Date(),
  },
])

const inputValue = ref('')
const isLoading = ref(false)
const messagesContainer = ref<HTMLElement | null>(null)

const demoResponses = [
  "That's a great question! Let me help you with that.",
  "I can definitely assist you with that. Here's what I recommend...",
  'Interesting! Based on your input, I suggest considering these options.',
  'I understand. Let me provide you with some insights on this topic.',
  "That's a common question. Here's what works best in most cases.",
]

const scrollToBottom = async () => {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

const handleSendMessage = async () => {
  if (!inputValue.value.trim()) return

  // Add user message
  const userMessage: Message = {
    id: Date.now().toString(),
    type: 'user',
    content: inputValue.value,
    timestamp: new Date(),
  }

  messages.value.push(userMessage)
  inputValue.value = ''
  await scrollToBottom()

  // Simulate AI response
  isLoading.value = true
  await new Promise((resolve) => setTimeout(resolve, 1000))

  const aiMessage: Message = {
    id: (Date.now() + 1).toString(),
    type: 'ai',
    content: demoResponses[Math.floor(Math.random() * demoResponses.length)],
    timestamp: new Date(),
  }

  messages.value.push(aiMessage)
  isLoading.value = false
  await scrollToBottom()
}

const handleKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSendMessage()
  }
}

const messageCount = computed(() => messages.value.length)
</script>

<template>
  <div class="w-full max-w-2xl mx-auto">
    <div
      class="rounded-2xl bg-white/40 backdrop-blur-md border border-white/60 overflow-hidden flex flex-col h-96"
    >
      <!-- Header -->
      <div class="px-6 py-4 border-b border-white/40 bg-white/20">
        <h3 class="text-lg font-bold text-gray-900">Try Our AI Assistant</h3>
        <p class="text-sm text-gray-600">Experience the power of OpenAgent in action</p>
      </div>

      <!-- Messages -->
      <div
        ref="messagesContainer"
        class="flex-1 overflow-y-auto px-6 py-4 space-y-4 scrollbar-w-none"
      >
        <div
          v-for="message in messages"
          :key="message.id"
          :class="[
            'flex gap-3 animate-fade-in',
            message.type === 'user' ? 'justify-end' : 'justify-start',
          ]"
        >
          <!-- AI Avatar -->
          <div v-if="message.type === 'ai'" class="flex-shrink-0">
            <div
              class="w-8 h-8 rounded-full bg-gradient-to-br from-blue-400 to-cyan-400 flex items-center justify-center text-white text-sm font-bold"
            >
              AI
            </div>
          </div>

          <!-- Message Bubble -->
          <div
            :class="[
              'max-w-xs px-4 py-2 rounded-lg',
              message.type === 'user'
                ? 'bg-gradient-to-r from-blue-600 to-cyan-600 text-white rounded-br-none'
                : 'bg-white/60 text-gray-900 rounded-bl-none',
            ]"
          >
            <p class="text-sm leading-relaxed">{{ message.content }}</p>
          </div>

          <!-- User Avatar -->
          <div v-if="message.type === 'user'" class="flex-shrink-0">
            <div
              class="w-8 h-8 rounded-full bg-gray-300 flex items-center justify-center text-gray-700 text-sm font-bold"
            >
              U
            </div>
          </div>
        </div>

        <!-- Loading Indicator -->
        <div v-if="isLoading" class="flex gap-3">
          <div
            class="w-8 h-8 rounded-full bg-gradient-to-br from-blue-400 to-cyan-400 flex items-center justify-center"
          >
            <div class="w-2 h-2 rounded-full bg-white animate-pulse" />
          </div>
          <div class="flex gap-1 items-center">
            <div
              class="w-2 h-2 rounded-full bg-gray-400 animate-bounce"
              style="animation-delay: 0s"
            />
            <div
              class="w-2 h-2 rounded-full bg-gray-400 animate-bounce"
              style="animation-delay: 0.1s"
            />
            <div
              class="w-2 h-2 rounded-full bg-gray-400 animate-bounce"
              style="animation-delay: 0.2s"
            />
          </div>
        </div>
      </div>

      <!-- Input -->
      <div class="px-6 py-4 border-t border-white/40 bg-white/20">
        <div class="flex gap-2">
          <input
            v-model="inputValue"
            type="text"
            placeholder="Type your message..."
            @keydown="handleKeydown"
            :disabled="isLoading"
            class="flex-1 px-4 py-2 rounded-lg bg-white/50 border border-white/60 text-gray-900 placeholder-gray-500 focus:outline-none focus:border-blue-300 focus:ring-2 focus:ring-blue-200/50 transition-all disabled:opacity-50"
          />
          <button
            @click="handleSendMessage"
            :disabled="isLoading || !inputValue.trim()"
            class="px-4 py-2 rounded-lg bg-gradient-to-r from-blue-600 to-cyan-600 text-white font-semibold hover:shadow-lg hover:shadow-blue-500/30 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
              />
            </svg>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
@keyframes fade-in {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.animate-fade-in {
  animation: fade-in 0.3s ease-out;
}

.scrollbar-w-none {
  scrollbar-width: none;
  -ms-overflow-style: none;
}

.scrollbar-w-none::-webkit-scrollbar {
  display: none;
}
</style>
