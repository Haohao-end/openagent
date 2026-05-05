<script setup lang="ts">
import { ref } from 'vue'

interface FAQItem {
  id: number
  question: string
  answer: string
}

const faqs: FAQItem[] = [
  {
    id: 1,
    question: 'What is OpenAgent and how does it work?',
    answer:
      'OpenAgent is a comprehensive platform for building, deploying, and managing AI applications. It provides a visual workflow builder, pre-built components, and seamless integration with multiple LLM providers. Simply define your workflow, connect your data sources, and deploy with one click.',
  },
  {
    id: 2,
    question: 'Do I need coding experience to use OpenAgent?',
    answer:
      'No! OpenAgent is designed for both technical and non-technical users. Our visual workflow builder allows you to create complex AI applications without writing any code. However, advanced users can also write custom code when needed.',
  },
  {
    id: 3,
    question: 'What LLM providers are supported?',
    answer:
      'We support all major LLM providers including OpenAI, Google, DeepSeek, Moonshot, and more. You can easily switch between providers or use multiple providers in the same application.',
  },
  {
    id: 4,
    question: 'How much does OpenAgent cost?',
    answer:
      'We offer flexible pricing plans starting from free. The free tier includes basic features and limited API calls. Paid plans offer unlimited apps, advanced features, and priority support.',
  },
  {
    id: 5,
    question: 'Is my data secure on OpenAgent?',
    answer:
      'Yes, security is our top priority. We use enterprise-grade encryption, regular security audits, and comply with GDPR, CCPA, and other data protection regulations. Your data is never used to train our models.',
  },
  {
    id: 6,
    question: 'Can I integrate OpenAgent with my existing tools?',
    answer:
      'Absolutely! OpenAgent provides REST APIs, webhooks, and integrations with popular tools like Slack, Discord, Zapier, and more. You can also deploy your apps as standalone services.',
  },
]

const expandedId = ref<number | null>(null)

const toggleFAQ = (id: number) => {
  expandedId.value = expandedId.value === id ? null : id
}
</script>

<template>
  <div class="w-full max-w-3xl mx-auto">
    <div class="space-y-4">
      <div
        v-for="faq in faqs"
        :key="faq.id"
        class="rounded-lg bg-white/40 backdrop-blur-md border border-white/60 overflow-hidden hover:border-white/80 transition-all duration-300"
      >
        <button
          @click="toggleFAQ(faq.id)"
          class="w-full px-6 py-4 flex items-center justify-between hover:bg-white/20 transition-colors"
        >
          <h3 class="text-lg font-semibold text-gray-900 text-left">{{ faq.question }}</h3>
          <svg
            :class="[
              'w-5 h-5 text-gray-600 transition-transform duration-300',
              expandedId === faq.id ? 'rotate-180' : '',
            ]"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M19 14l-7 7m0 0l-7-7m7 7V3"
            />
          </svg>
        </button>

        <transition
          enter-active-class="transition-all duration-300"
          leave-active-class="transition-all duration-300"
          enter-from-class="max-h-0 opacity-0"
          enter-to-class="max-h-96 opacity-100"
          leave-from-class="max-h-96 opacity-100"
          leave-to-class="max-h-0 opacity-0"
        >
          <div v-if="expandedId === faq.id" class="px-6 py-4 border-t border-white/40 bg-white/20">
            <p class="text-gray-700 leading-relaxed">{{ faq.answer }}</p>
          </div>
        </transition>
      </div>
    </div>
  </div>
</template>

<style scoped>
button {
  outline: none;
}
</style>
