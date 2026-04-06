<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'

interface SocialProof {
  id: number
  name: string
  role: string
  company: string
  text: string
  avatar: string
  rating: number
}

const proofs: SocialProof[] = [
  {
    id: 1,
    name: 'Sarah Chen',
    role: 'AI Product Manager',
    company: 'TechCorp',
    text: 'LLMOps transformed how we build AI applications. What used to take weeks now takes days. The platform is incredibly intuitive and powerful.',
    avatar: '👩‍💼',
    rating: 5
  },
  {
    id: 2,
    name: 'Marcus Johnson',
    role: 'CTO',
    company: 'StartupXYZ',
    text: 'The platform is incredibly intuitive. Our team was productive from day one. Best investment we made for our AI infrastructure.',
    avatar: '👨‍💻',
    rating: 5
  },
  {
    id: 3,
    name: 'Elena Rodriguez',
    role: 'AI Engineer',
    company: 'DataFlow Inc',
    text: 'Best investment we made for our AI infrastructure. Highly recommended! The support team is also amazing.',
    avatar: '👩‍🔬',
    rating: 5
  },
  {
    id: 4,
    name: 'David Park',
    role: 'Founder',
    company: 'AI Ventures',
    text: 'LLMOps made it possible for us to launch our AI product in record time. The workflow builder is genius.',
    avatar: '👨‍🔬',
    rating: 5
  },
  {
    id: 5,
    name: 'Lisa Wang',
    role: 'Tech Lead',
    company: 'CloudScale',
    text: 'The integration capabilities are outstanding. We connected our entire stack in hours, not days.',
    avatar: '👩‍💻',
    rating: 5
  }
]

const currentIndex = ref(0)
let autoplayInterval: number | null = null

const visibleProofs = computed(() => {
  const items = []
  for (let i = 0; i < 3; i++) {
    items.push(proofs[(currentIndex.value + i) % proofs.length])
  }
  return items
})

const nextSlide = () => {
  currentIndex.value = (currentIndex.value + 1) % proofs.length
}

const prevSlide = () => {
  currentIndex.value = (currentIndex.value - 1 + proofs.length) % proofs.length
}

const startAutoplay = () => {
  autoplayInterval = window.setInterval(nextSlide, 5000)
}

const stopAutoplay = () => {
  if (autoplayInterval) {
    clearInterval(autoplayInterval)
    autoplayInterval = null
  }
}

onMounted(() => {
  startAutoplay()
})

onUnmounted(() => {
  stopAutoplay()
})
</script>

<template>
  <div class="w-full max-w-6xl mx-auto">
    <!-- Carousel Container -->
    <div
      class="relative"
      @mouseenter="stopAutoplay"
      @mouseleave="startAutoplay"
    >
      <!-- Slides -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <transition-group name="carousel" tag="div" class="contents">
          <div
            v-for="proof in visibleProofs"
            :key="proof.id"
            class="rounded-2xl p-8 bg-white/40 backdrop-blur-md border border-white/60 hover:border-white/80 transition-all duration-300"
          >
            <!-- Rating -->
            <div class="flex gap-1 mb-4">
              <svg
                v-for="i in proof.rating"
                :key="i"
                class="w-5 h-5 text-yellow-400"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
              </svg>
            </div>

            <!-- Quote -->
            <p class="text-gray-700 mb-6 italic leading-relaxed">
              "{{ proof.text }}"
            </p>

            <!-- Author -->
            <div class="flex items-center gap-4">
              <div class="text-4xl">{{ proof.avatar }}</div>
              <div>
                <div class="font-bold text-gray-900">{{ proof.name }}</div>
                <div class="text-sm text-gray-600">{{ proof.role }} at {{ proof.company }}</div>
              </div>
            </div>
          </div>
        </transition-group>
      </div>

      <!-- Navigation Buttons -->
      <div class="flex items-center justify-center gap-4">
        <button
          @click="prevSlide"
          class="p-2 rounded-lg bg-white/40 backdrop-blur-md border border-white/60 hover:bg-white/60 transition-all"
          aria-label="Previous slide"
        >
          <svg class="w-6 h-6 text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
          </svg>
        </button>

        <!-- Dots -->
        <div class="flex gap-2">
          <button
            v-for="(_, idx) in proofs"
            :key="idx"
            @click="currentIndex = idx"
            :class="[
              'w-2 h-2 rounded-full transition-all',
              idx === currentIndex
                ? 'bg-blue-600 w-8'
                : 'bg-white/40 hover:bg-white/60'
            ]"
            :aria-label="`Go to slide ${idx + 1}`"
          />
        </div>

        <button
          @click="nextSlide"
          class="p-2 rounded-lg bg-white/40 backdrop-blur-md border border-white/60 hover:bg-white/60 transition-all"
          aria-label="Next slide"
        >
          <svg class="w-6 h-6 text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
          </svg>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.carousel-enter-active,
.carousel-leave-active {
  transition: all 0.5s ease;
}

.carousel-enter-from {
  opacity: 0;
  transform: translateX(30px);
}

.carousel-leave-to {
  opacity: 0;
  transform: translateX(-30px);
}
</style>
