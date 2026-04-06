<script setup lang="ts">
import { ref } from 'vue'

interface PricingPlan {
  id: number
  name: string
  price: number | string
  description: string
  features: string[]
  highlighted?: boolean
  cta: string
}

const plans: PricingPlan[] = [
  {
    id: 1,
    name: 'Starter',
    price: 'Free',
    description: 'Perfect for getting started',
    features: [
      'Up to 3 AI apps',
      '1,000 API calls/month',
      'Basic analytics',
      'Community support',
      'Standard templates'
    ],
    cta: 'Get Started'
  },
  {
    id: 2,
    name: 'Professional',
    price: '$99',
    description: 'For growing teams',
    features: [
      'Unlimited AI apps',
      '100,000 API calls/month',
      'Advanced analytics',
      'Priority email support',
      'Custom integrations',
      'Team collaboration',
      'API access'
    ],
    highlighted: true,
    cta: 'Start Free Trial'
  },
  {
    id: 3,
    name: 'Enterprise',
    price: 'Custom',
    description: 'For large organizations',
    features: [
      'Everything in Professional',
      'Unlimited API calls',
      'Dedicated support',
      'Custom SLA',
      'On-premise deployment',
      'Advanced security',
      'Custom training'
    ],
    cta: 'Contact Sales'
  }
]

const billingCycle = ref<'monthly' | 'yearly'>('monthly')
</script>

<template>
  <div class="w-full">
    <!-- Billing Toggle -->
    <div class="flex items-center justify-center gap-4 mb-12">
      <span :class="['text-sm font-medium', billingCycle === 'monthly' ? 'text-gray-900' : 'text-gray-600']">
        Monthly
      </span>
      <button
        @click="billingCycle = billingCycle === 'monthly' ? 'yearly' : 'monthly'"
        class="relative inline-flex h-8 w-14 items-center rounded-full bg-white/40 backdrop-blur-md border border-white/60 transition-colors"
      >
        <span
          :class="[
            'inline-block h-6 w-6 transform rounded-full bg-gradient-to-r from-blue-600 to-cyan-600 transition-transform',
            billingCycle === 'yearly' ? 'translate-x-7' : 'translate-x-1'
          ]"
        />
      </button>
      <span :class="['text-sm font-medium', billingCycle === 'yearly' ? 'text-gray-900' : 'text-gray-600']">
        Yearly
        <span class="ml-2 inline-block px-2 py-1 rounded-full bg-green-100/50 text-green-700 text-xs font-semibold">
          Save 20%
        </span>
      </span>
    </div>

    <!-- Pricing Cards -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-6xl mx-auto">
      <div
        v-for="plan in plans"
        :key="plan.id"
        :class="[
          'rounded-2xl p-8 transition-all duration-300',
          plan.highlighted
            ? 'bg-gradient-to-br from-blue-600/10 to-cyan-600/10 border-2 border-blue-200/50 shadow-lg shadow-blue-500/10 scale-105'
            : 'bg-white/40 backdrop-blur-md border border-white/60 hover:border-white/80'
        ]"
      >
        <!-- Badge for highlighted plan -->
        <div v-if="plan.highlighted" class="mb-4">
          <span class="inline-block px-3 py-1 rounded-full bg-gradient-to-r from-blue-600 to-cyan-600 text-white text-xs font-semibold">
            Most Popular
          </span>
        </div>

        <!-- Plan Name -->
        <h3 class="text-2xl font-bold text-gray-900 mb-2">{{ plan.name }}</h3>
        <p class="text-gray-600 text-sm mb-6">{{ plan.description }}</p>

        <!-- Price -->
        <div class="mb-6">
          <span class="text-4xl font-bold text-gray-900">{{ plan.price }}</span>
          <span v-if="plan.price !== 'Free' && plan.price !== 'Custom'" class="text-gray-600 ml-2">
            /{{ billingCycle === 'monthly' ? 'month' : 'year' }}
          </span>
        </div>

        <!-- CTA Button -->
        <button
          :class="[
            'w-full px-6 py-3 rounded-lg font-semibold transition-all duration-300 mb-8',
            plan.highlighted
              ? 'bg-gradient-to-r from-blue-600 to-cyan-600 text-white hover:shadow-lg hover:shadow-blue-500/30'
              : 'bg-white/40 backdrop-blur-md border border-white/60 text-gray-700 hover:bg-white/60'
          ]"
        >
          {{ plan.cta }}
        </button>

        <!-- Features List -->
        <div class="space-y-4">
          <div v-for="(feature, idx) in plan.features" :key="idx" class="flex items-start gap-3">
            <svg class="w-5 h-5 text-green-500 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
            </svg>
            <span class="text-gray-700 text-sm">{{ feature }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Smooth transitions */
button {
  outline: none;
}
</style>
