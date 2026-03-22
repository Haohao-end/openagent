<script setup lang="ts">
import AiDynamicBackground from '@/components/AiDynamicBackground.vue'
import ScrollNavigator from '@/components/ScrollNavigation/ScrollNavigator.vue'
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'

interface SuggestedAction {
  label: string
  action: string
  icon: string
}

interface IntentResult {
  intent: string
  confidence: number
  suggested_actions: SuggestedAction[]
  is_default: boolean
}

const router = useRouter()
const scrollY = ref(0)
const intentResult = ref<IntentResult | null>(null)
const loading = ref(true)

const handleScroll = () => {
  scrollY.value = window.scrollY
}

const handleGetStarted = () => {
  router.push('/space/apps')
}

const handleExplore = () => {
  const element = document.getElementById('features-section')
  element?.scrollIntoView({ behavior: 'smooth' })
}

const handleAction = (action: string) => {
  const actionMap: Record<string, () => void> = {
    create_app: () => router.push('/space/apps?action=create'),
    view_apps: () => router.push('/space/apps'),
    create_workflow: () => router.push('/space/workflows?action=create'),
    view_workflows: () => router.push('/space/workflows'),
    create_dataset: () => router.push('/space/datasets?action=create'),
    view_datasets: () => router.push('/space/datasets'),
    view_examples: () => router.push('/space/examples'),
    view_capabilities: () => handleExplore(),
    create_weather_agent: () => router.push('/space/apps?action=create&template=weather'),
  }

  const handler = actionMap[action]
  if (handler) {
    handler()
  }
}

const fetchIntent = async () => {
  try {
    loading.value = true
    const response = await fetch('/api/home/intent', {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    })

    if (response.ok) {
      const data = await response.json()
      if (data.code === 0) {
        intentResult.value = data.data
      }
    }
  } catch (error) {
    console.error('Failed to fetch intent:', error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  window.addEventListener('scroll', handleScroll)
  fetchIntent()
})
</script>

<template>
  <scroll-navigator>
    <div class="relative w-full h-full bg-white overflow-y-auto">
      <!-- Dynamic Background -->
      <AiDynamicBackground class="fixed top-0 left-0 z-0 pointer-events-none" />

      <!-- Hero Section -->
      <div id="hero-section" data-scroll-item class="relative z-10 min-h-screen flex flex-col items-center justify-center px-4 sm:px-6 lg:px-8">
      <!-- Animated Background Overlay -->
      <div class="absolute inset-0 pointer-events-none">
        <div
          class="absolute top-1/4 left-1/4 w-96 h-96 bg-gradient-to-br from-blue-200/20 to-cyan-200/10 rounded-full blur-3xl"
          :style="{ transform: `translateY(${scrollY * 0.3}px)` }"
        />
        <div
          class="absolute bottom-1/4 right-1/4 w-96 h-96 bg-gradient-to-tl from-purple-200/15 to-pink-200/10 rounded-full blur-3xl"
          :style="{ transform: `translateY(${scrollY * -0.2}px)` }"
        />
      </div>

      <!-- Content Container -->
      <div class="relative z-20 max-w-4xl mx-auto text-center space-y-8 py-20">
        <!-- Badge -->
        <div class="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/40 backdrop-blur-md border border-white/60 hover:bg-white/50 transition-all duration-300">
          <span class="w-2 h-2 rounded-full bg-gradient-to-r from-blue-400 to-cyan-400 animate-pulse" />
          <span class="text-sm font-medium text-gray-700">AI-Powered Platform</span>
        </div>

        <!-- Main Headline / Intent Result -->
        <div class="space-y-4">
          <div v-if="loading" class="text-lg text-gray-600">
            Loading personalized content...
          </div>
          <div v-else-if="intentResult">
            <h1 class="text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight whitespace-pre-wrap">
              <span class="bg-gradient-to-r from-gray-900 via-blue-800 to-gray-900 bg-clip-text text-transparent">
                {{ intentResult.intent }}
              </span>
            </h1>
            <p v-if="intentResult.confidence > 0" class="text-sm text-gray-500 mt-2">
              Confidence: {{ (intentResult.confidence * 100).toFixed(0) }}%
            </p>
          </div>
          <div v-else>
            <h1 class="text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight">
              <span class="bg-gradient-to-r from-gray-900 via-blue-800 to-gray-900 bg-clip-text text-transparent">
                Build AI Apps
              </span>
              <br />
              <span class="bg-gradient-to-r from-blue-600 to-cyan-600 bg-clip-text text-transparent">
                Effortlessly
              </span>
            </h1>
            <p class="text-lg sm:text-xl text-gray-600 max-w-2xl mx-auto leading-relaxed">
              Create, deploy, and manage AI applications with our intuitive platform. No coding required. Pure innovation.
            </p>
          </div>
        </div>

        <!-- CTA Buttons / Suggested Actions -->
        <div class="flex flex-col sm:flex-row items-center justify-center gap-4 pt-4 flex-wrap">
          <template v-if="intentResult && intentResult.suggested_actions.length > 0">
            <button
              v-for="action in intentResult.suggested_actions"
              :key="action.action"
              @click="handleAction(action.action)"
              class="px-8 py-3 rounded-lg bg-gradient-to-r from-blue-600 to-cyan-600 text-white font-semibold hover:shadow-lg hover:shadow-blue-500/30 transition-all duration-300 transform hover:scale-105"
            >
              {{ action.label }}
            </button>
          </template>
          <template v-else>
            <button
              @click="handleGetStarted"
              class="px-8 py-3 rounded-lg bg-gradient-to-r from-blue-600 to-cyan-600 text-white font-semibold hover:shadow-lg hover:shadow-blue-500/30 transition-all duration-300 transform hover:scale-105"
            >
              Get Started
            </button>
            <button
              @click="handleExplore"
              class="px-8 py-3 rounded-lg bg-white/40 backdrop-blur-md border border-white/60 text-gray-700 font-semibold hover:bg-white/60 transition-all duration-300"
            >
              Explore Features
            </button>
          </template>
        </div>

        <!-- Stats -->
        <div class="grid grid-cols-3 gap-4 pt-12">
          <div class="p-4 rounded-lg bg-white/30 backdrop-blur-md border border-white/40">
            <div class="text-2xl font-bold text-gray-900">10K+</div>
            <div class="text-sm text-gray-600">Active Users</div>
          </div>
          <div class="p-4 rounded-lg bg-white/30 backdrop-blur-md border border-white/40">
            <div class="text-2xl font-bold text-gray-900">50K+</div>
            <div class="text-sm text-gray-600">Apps Created</div>
          </div>
          <div class="p-4 rounded-lg bg-white/30 backdrop-blur-md border border-white/40">
            <div class="text-2xl font-bold text-gray-900">99.9%</div>
            <div class="text-sm text-gray-600">Uptime</div>
          </div>
        </div>
      </div>

      <!-- Scroll Indicator -->
      <div class="absolute bottom-8 left-1/2 transform -translate-x-1/2 animate-bounce">
        <svg class="w-6 h-6 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 14l-7 7m0 0l-7-7m7 7V3" />
        </svg>
      </div>
    </div>

    <!-- Features Section -->
    <div id="features-section" data-scroll-item class="relative z-10 py-20 px-4 sm:px-6 lg:px-8 bg-gradient-to-b from-white/50 to-white">
      <div class="max-w-6xl mx-auto">
        <div class="text-center mb-16">
          <h2 class="text-4xl sm:text-5xl font-bold text-gray-900 mb-4">
            Powerful Features
          </h2>
          <p class="text-lg text-gray-600">
            Everything you need to build, deploy, and scale AI applications
          </p>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-8">
          <!-- Feature 1 -->
          <div class="p-8 rounded-2xl bg-white/60 backdrop-blur-md border border-white/80 hover:border-blue-200/60 transition-all duration-300 hover:shadow-lg hover:shadow-blue-500/10">
            <div class="w-12 h-12 rounded-lg bg-gradient-to-br from-blue-400 to-cyan-400 flex items-center justify-center mb-4">
              <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <h3 class="text-xl font-bold text-gray-900 mb-2">Lightning Fast</h3>
            <p class="text-gray-600">
              Deploy your AI apps in seconds with our optimized infrastructure
            </p>
          </div>

          <!-- Feature 2 -->
          <div class="p-8 rounded-2xl bg-white/60 backdrop-blur-md border border-white/80 hover:border-blue-200/60 transition-all duration-300 hover:shadow-lg hover:shadow-blue-500/10">
            <div class="w-12 h-12 rounded-lg bg-gradient-to-br from-purple-400 to-pink-400 flex items-center justify-center mb-4">
              <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
              </svg>
            </div>
            <h3 class="text-xl font-bold text-gray-900 mb-2">Fully Customizable</h3>
            <p class="text-gray-600">
              Tailor every aspect of your AI application to match your needs
            </p>
          </div>

          <!-- Feature 3 -->
          <div class="p-8 rounded-2xl bg-white/60 backdrop-blur-md border border-white/80 hover:border-blue-200/60 transition-all duration-300 hover:shadow-lg hover:shadow-blue-500/10">
            <div class="w-12 h-12 rounded-lg bg-gradient-to-br from-green-400 to-emerald-400 flex items-center justify-center mb-4">
              <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h3 class="text-xl font-bold text-gray-900 mb-2">Enterprise Ready</h3>
            <p class="text-gray-600">
              Built with security and scalability at its core
            </p>
          </div>
        </div>
      </div>
    </div>

    <!-- CTA Section -->
    <div data-scroll-item class="relative z-10 py-20 px-4 sm:px-6 lg:px-8">
      <div class="max-w-2xl mx-auto text-center">
        <div class="p-12 rounded-2xl bg-gradient-to-r from-blue-600/10 to-cyan-600/10 backdrop-blur-md border border-blue-200/30">
          <h2 class="text-3xl sm:text-4xl font-bold text-gray-900 mb-4">
            Ready to Build?
          </h2>
          <p class="text-lg text-gray-600 mb-8">
            Join thousands of developers creating amazing AI applications
          </p>
          <button
            @click="handleGetStarted"
            class="px-8 py-3 rounded-lg bg-gradient-to-r from-blue-600 to-cyan-600 text-white font-semibold hover:shadow-lg hover:shadow-blue-500/30 transition-all duration-300 transform hover:scale-105"
          >
            Start Building Now
          </button>
        </div>
      </div>
    </div>

    <!-- Footer -->
    <footer data-scroll-item class="relative z-10 border-t border-white/20 py-8 px-4 sm:px-6 lg:px-8 bg-white/30 backdrop-blur-md">
      <div class="max-w-6xl mx-auto text-center text-gray-600 text-sm">
        <p>© 2026 LLMOps Platform. All rights reserved.</p>
      </div>
    </footer>
  </div>
  </scroll-navigator>
</template>

<style scoped>
@keyframes float {
  0%, 100% {
    transform: translateY(0px);
  }
  50% {
    transform: translateY(-20px);
  }
}

.animate-float {
  animation: float 6s ease-in-out infinite;
}
</style>
