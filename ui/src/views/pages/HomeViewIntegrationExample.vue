<!--
  集成示例：如何在现有 HomeView 中使用 AI 动态背景和玻璃卡片

  这个文件展示了如何将新的背景组件和玻璃卡片集成到现有的聊天界面中。
  可以根据需要选择性地应用这些组件。
-->

<script setup lang="ts">
import { ref } from 'vue'
import AiDynamicBackground from '@/components/AiDynamicBackground.vue'
import GlassCard from '@/components/GlassCard.vue'
import HeroSection from '@/components/HeroSection.vue'

// 示例 1: 在首屏显示 Hero 区域
const showHero = ref(true)

// 示例 2: 在对话框中使用玻璃卡片
const messages = ref([
  {
    id: 1,
    type: 'ai',
    content: '你好！我是你的 AI 助手。我可以帮你创建应用、回答问题等。',
  },
  {
    id: 2,
    type: 'user',
    content: '帮我创建一个天气应用',
  },
  {
    id: 3,
    type: 'ai',
    content: '好的！我可以帮你创建一个天气应用。首先，我需要了解一些需求...',
  },
])
</script>

<template>
  <div class="relative w-full min-h-screen bg-white overflow-x-hidden">
    <!-- 方案 A: 完整的 Hero 首页 -->
    <div v-if="showHero" class="relative w-full min-h-screen">
      <HeroSection
        title="Hi，朋友"
        subtitle="你的专属 AI 原生应用开发平台"
        description="说出你的创意，我可以快速帮你创建专属应用，一键轻松分享给朋友。"
      />
    </div>

    <!-- 方案 B: 在聊天界面中使用动态背景 -->
    <div class="relative w-full min-h-screen">
      <!-- 动态背景层 -->
      <AiDynamicBackground
        className="z-0"
        intensity="low"
        :showParticles="true"
        :showGrid="false"
      />

      <!-- 聊天内容 -->
      <div class="relative z-10 max-w-2xl mx-auto p-6 space-y-4">
        <!-- 消息列表 -->
        <div v-for="message in messages" :key="message.id" class="flex" :class="message.type === 'user' ? 'justify-end' : 'justify-start'">
          <!-- AI 消息 -->
          <GlassCard
            v-if="message.type === 'ai'"
            variant="message"
            className="max-w-xs p-4"
          >
            <div class="text-gray-800">
              <p class="text-sm font-semibold text-blue-600 mb-2">AI 助手</p>
              <p class="text-sm leading-relaxed">{{ message.content }}</p>
            </div>
          </GlassCard>

          <!-- 用户消息 -->
          <GlassCard
            v-else
            variant="message"
            className="max-w-xs p-4 bg-blue-500/40 border-blue-400/60"
          >
            <div class="text-gray-800">
              <p class="text-sm leading-relaxed">{{ message.content }}</p>
            </div>
          </GlassCard>
        </div>

        <!-- 输入框 -->
        <div class="mt-8">
          <GlassCard variant="input" className="p-4 flex items-center gap-2">
            <input
              type="text"
              placeholder="输入你的问题..."
              class="flex-1 bg-transparent outline-none text-gray-800 placeholder-gray-500"
            />
            <button class="p-2 hover:bg-white/20 rounded-lg transition">
              <svg class="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </button>
          </GlassCard>
        </div>
      </div>
    </div>

    <!-- 方案 C: 功能特性展示 -->
    <section class="relative w-full py-20 px-4">
      <AiDynamicBackground
        className="z-0 opacity-40"
        intensity="low"
        :showParticles="false"
        :showGrid="false"
      />

      <div class="relative z-10 max-w-6xl mx-auto">
        <h2 class="text-4xl font-bold text-center text-gray-900 mb-12">
          强大的功能特性
        </h2>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
          <GlassCard className="p-8 hover:shadow-xl transition-all">
            <div class="w-12 h-12 rounded-lg bg-gradient-to-br from-blue-400 to-cyan-400 flex items-center justify-center mb-4">
              <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <h3 class="text-xl font-bold text-gray-900 mb-2">快速创建</h3>
            <p class="text-gray-600">通过直观的可视化编辑器快速创建 AI 应用</p>
          </GlassCard>

          <GlassCard className="p-8 hover:shadow-xl transition-all">
            <div class="w-12 h-12 rounded-lg bg-gradient-to-br from-purple-400 to-pink-400 flex items-center justify-center mb-4">
              <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h3 class="text-xl font-bold text-gray-900 mb-2">智能优化</h3>
            <p class="text-gray-600">内置 AI 优化引擎，自动调整应用参数</p>
          </GlassCard>

          <GlassCard className="p-8 hover:shadow-xl transition-all">
            <div class="w-12 h-12 rounded-lg bg-gradient-to-br from-green-400 to-emerald-400 flex items-center justify-center mb-4">
              <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
              </svg>
            </div>
            <h3 class="text-xl font-bold text-gray-900 mb-2">灵活配置</h3>
            <p class="text-gray-600">支持多种 LLM 模型和工具集成</p>
          </GlassCard>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
/* 自定义样式 */
</style>
