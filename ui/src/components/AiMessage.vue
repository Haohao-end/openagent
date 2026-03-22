<script setup lang="ts">
import { computed, type PropType } from 'vue'
import { Message } from '@arco-design/web-vue'
import DotFlashing from '@/components/DotFlashing.vue'
import { useAudioPlayer } from '@/hooks/use-audio'
import { useMarkdownRenderer } from '@/hooks/use-markdown-renderer'
import { copyTextToClipboard } from '@/utils/clipboard'
import AgentThought from './AgentThought.vue'
import 'github-markdown-css'
import 'highlight.js/styles/github.css'

const {
  messageAudioLoading,
  thoughtAudioLoading,
  isPlaying,
  activeMessageId,
  activeThoughtId,
  activeStreamType,
  startAudioStream,
  startTextAudioStream,
  stopAudioStream,
} = useAudioPlayer()


// 1.定义自定义组件所需数据
const props = defineProps({
  app: {
    type: Object,
    default: () => {
      return {}
    },
    required: true,
  },
  enable_text_to_speech: { type: Boolean, default: false, required: false },
  message_id: { type: String, default: '', required: false },
  answer: { type: String, default: '', required: true },
  loading: { type: Boolean, default: false, required: false },
  latency: { type: Number, default: 0, required: false },
  total_token_count: { type: Number, default: 0, required: false },
  agent_thoughts: {
    type: Array as PropType<Array<Record<string, unknown>>>,
    default: () => [],
    required: true,
  },
  suggested_questions: { type: Array as PropType<string[]>, default: () => [], required: false },
  message_class: { type: String, default: '!bg-gray-100', required: false },
  agent_thought_variant: { type: String as PropType<'sidebar' | 'inline'>, default: 'sidebar', required: false },
  show_agent_thought: { type: Boolean, default: true, required: false },
  agent_thought_default_visible: { type: Boolean, default: false, required: false },
  agent_thought_follow_latest: { type: Boolean, default: false, required: false },
  always_show_actions: { type: Boolean, default: false, required: false },
  audio_stream_id: { type: String, default: '', required: false },
})
const emits = defineEmits(['selectSuggestedQuestion'])
const { renderMarkdown, handleMarkdownCopyClick } = useMarkdownRenderer()
const compiledMarkdown = computed(() => {
  return renderMarkdown(props.answer)
})

const fallbackAudioId = computed(() => {
  return `answer-audio:${props.app?.name || 'assistant'}`
})
const currentAudioStreamId = computed(() => {
  return props.audio_stream_id || fallbackAudioId.value
})

const actionIconClass = computed(() => {
  if (props.always_show_actions) {
    return 'text-gray-400 cursor-pointer hover:text-gray-700'
  }
  return 'text-gray-400 cursor-pointer hover:text-gray-700 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none group-hover:pointer-events-auto'
})

const isCurrentPlaying = computed(() => {
  if (props.message_id) {
    return (
      isPlaying.value &&
      activeStreamType.value === 'message' &&
      activeMessageId.value === props.message_id
    )
  }
  return (
    isPlaying.value &&
    activeStreamType.value === 'thought' &&
    activeThoughtId.value === currentAudioStreamId.value
  )
})

const isCurrentLoading = computed(() => {
  if (props.message_id) {
    return (
      messageAudioLoading.value &&
      activeStreamType.value === 'message' &&
      activeMessageId.value === props.message_id
    )
  }
  return (
    thoughtAudioLoading.value &&
    activeStreamType.value === 'thought' &&
    activeThoughtId.value === currentAudioStreamId.value
  )
})

const canShowAudioPlay = computed(() => {
  if (!props.enable_text_to_speech) return false
  if (props.loading) return false
  return props.answer.trim() !== ''
})

const shouldRenderAudioAction = computed(() => {
  if (!props.enable_text_to_speech) return false
  return isCurrentLoading.value || isCurrentPlaying.value || canShowAudioPlay.value
})

const safeLatency = computed(() => {
  const value = Number(props.latency)
  return Number.isFinite(value) && value >= 0 ? value : 0
})

const safeTotalTokenCount = computed(() => {
  const value = Number(props.total_token_count)
  return Number.isFinite(value) && value >= 0 ? Math.floor(value) : 0
})

const handlePlayAudio = async () => {
  if (props.message_id) {
    await startAudioStream(props.message_id)
    return
  }

  const answer = props.answer.trim()
  if (!answer) return
  await startTextAudioStream(answer, '', currentAudioStreamId.value)
}

const handleStopAudio = () => {
  stopAudioStream()
}

const handleCopyAnswer = async () => {
  if (!props.answer) return
  await copyTextToClipboard(props.answer)
  Message.success('AI消息已复制')
}

const handleMarkdownClick = async (event: MouseEvent) => {
  await handleMarkdownCopyClick(event, { successMessage: '代码已复制' })
}
</script>

<template>
  <div class="flex gap-2 group">
    <!-- 左侧图标 -->
    <a-avatar v-if="props.app?.icon" :size="36" shape="circle" class="flex-shrink-0" :image-url="props.app?.icon" />
    <a-avatar v-else :size="36" shape="circle" class="flex-shrink-0 bg-blue-700">
      <icon-apps />
    </a-avatar>
    <!-- 右侧名称与消息 -->
    <div class="flex-1 flex flex-col items-start gap-2">
      <!-- 应用名称 -->
      <div class="text-gray-700 font-bold text-sm">{{ props.app?.name }}</div>
      <!-- 推理步骤 -->
      <agent-thought
        v-if="props.show_agent_thought"
        :agent_thoughts="props.agent_thoughts"
        :loading="props.loading"
        :message_id="props.message_id"
        :variant="props.agent_thought_variant"
        :default_visible="props.agent_thought_default_visible"
        :follow_latest_thought="props.agent_thought_follow_latest"
      />
      <div class="flex flex-col gap-1">
        <!-- AI消息 -->
        <div
          v-if="props.loading && props.answer.trim() === ''"
          class="glass-message-bubble px-4 py-3 rounded-2xl break-all max-w-[600px] transition-all duration-300"
        >
          <dot-flashing />
        </div>
        <div
          v-else
          :class="[
            'glass-message-bubble markdown-body px-4 py-3 rounded-2xl break-all max-w-[600px] transition-all duration-300',
            isCurrentPlaying ? 'ai-message-playing' : '',
          ]"
          v-html="compiledMarkdown"
          @click="handleMarkdownClick"
        ></div>
        <!-- 消息展示与操作 -->
        <div class="flex items-center justify-between gap-3">
          <!-- 消息数据额外展示 -->
          <a-space class="text-xs">
            <template #split>
              <a-divider direction="vertical" class="m-0" />
            </template>
            <div class="flex items-center gap-1 text-gray-500">
              <icon-check />
              {{ safeLatency.toFixed(2) }}s
            </div>
            <div class="text-gray-500">{{ safeTotalTokenCount }} Tokens</div>
          </a-space>
          <!-- 播放音频&暂停播放 -->
          <div class="flex items-center gap-2">
            <icon-copy
              :class="actionIconClass"
              @click="handleCopyAnswer"
            />
            <template v-if="shouldRenderAudioAction">
              <template v-if="isCurrentLoading">
                <icon-loading class="text-blue-700" />
              </template>
              <template v-else-if="isCurrentPlaying">
                <icon-pause
                  class="text-blue-700 cursor-pointer hover:text-blue-700"
                  @click="handleStopAudio"
                />
              </template>
              <template v-else-if="canShowAudioPlay">
                <icon-play-circle
                  :class="actionIconClass"
                  @click="handlePlayAudio"
                />
              </template>
            </template>
          </div>
        </div>
      </div>
      <!-- 建议问题列表 -->
      <div v-if="props.suggested_questions.length > 0" class="flex flex-col gap-2">
        <div v-for="(suggested_question, idx) in props.suggested_questions" :key="idx"
          class="glass-suggestion-bubble px-4 py-2 border rounded-lg text-gray-700 cursor-pointer transition-all duration-300"
          @click="() => emits('selectSuggestedQuestion', suggested_question)">
          {{ suggested_question }}
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.glass-message-bubble {
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.45) 0%, rgba(240, 248, 255, 0.35) 100%);
  backdrop-filter: blur(30px);
  -webkit-backdrop-filter: blur(30px);
  border: 1.5px solid rgba(255, 255, 255, 0.7);
  box-shadow:
    0 8px 32px rgba(186, 230, 253, 0.2),
    inset 0 1px 0 rgba(255, 255, 255, 0.9),
    inset 0 -1px 0 rgba(0, 0, 0, 0.06);
  color: #1f2937;
  position: relative;
  overflow: hidden;
}

.glass-message-bubble::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.5) 0%, rgba(255, 255, 255, 0) 100%);
  pointer-events: none;
}

.glass-message-bubble:hover {
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.55) 0%, rgba(240, 248, 255, 0.45) 100%);
  border-color: rgba(255, 255, 255, 0.85);
  box-shadow:
    0 12px 40px rgba(186, 230, 253, 0.3),
    inset 0 1px 0 rgba(255, 255, 255, 1),
    inset 0 -1px 0 rgba(0, 0, 0, 0.08);
}

.glass-suggestion-bubble {
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.5) 0%, rgba(240, 248, 255, 0.4) 100%);
  backdrop-filter: blur(25px);
  -webkit-backdrop-filter: blur(25px);
  border: 1.2px solid rgba(255, 255, 255, 0.65);
  box-shadow:
    0 6px 24px rgba(186, 230, 253, 0.15),
    inset 0 1px 0 rgba(255, 255, 255, 0.8),
    inset 0 -1px 0 rgba(0, 0, 0, 0.04);
  position: relative;
  overflow: hidden;
}

.glass-suggestion-bubble::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.4) 0%, rgba(255, 255, 255, 0) 100%);
  pointer-events: none;
}

.glass-suggestion-bubble:hover {
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.6) 0%, rgba(240, 248, 255, 0.5) 100%);
  border-color: rgba(255, 255, 255, 0.8);
  box-shadow:
    0 8px 32px rgba(186, 230, 253, 0.25),
    inset 0 1px 0 rgba(255, 255, 255, 0.9),
    inset 0 -1px 0 rgba(0, 0, 0, 0.06);
}

:deep(.markdown-body) {
  background: transparent;
}

:deep(.markdown-body .md-code-block) {
  margin: 0 0 12px 0;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  overflow: hidden;
}

:deep(.markdown-body .md-code-header) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 6px 10px;
  background: #f9fafb;
  border-bottom: 1px solid #e5e7eb;
}

:deep(.markdown-body .md-code-lang) {
  color: #6b7280;
  font-size: 12px;
  line-height: 16px;
}

:deep(.markdown-body .md-code-copy-btn) {
  border: none;
  background: transparent;
  color: #374151;
  font-size: 12px;
  line-height: 16px;
  cursor: pointer;
}

:deep(.markdown-body .md-code-copy-btn:hover) {
  color: #111827;
}

:deep(.markdown-body .md-code-copy-btn:disabled) {
  color: #9ca3af;
  cursor: default;
}

:deep(.markdown-body pre.hljs) {
  margin: 0;
  border: 0;
  border-radius: 0;
}

.ai-message-playing {
  border-color: rgba(186, 230, 253, 0.9) !important;
  animation: ai-message-breathing 1.2s ease-in-out infinite;
}

@keyframes ai-message-breathing {
  0%,
  100% {
    box-shadow:
      0 8px 32px rgba(186, 230, 253, 0.2),
      inset 0 1px 0 rgba(255, 255, 255, 0.9),
      inset 0 -1px 0 rgba(0, 0, 0, 0.06),
      0 0 0 0 rgba(186, 230, 253, 0.4);
    background: linear-gradient(135deg, rgba(255, 255, 255, 0.45) 0%, rgba(240, 248, 255, 0.35) 100%);
  }
  50% {
    box-shadow:
      0 12px 40px rgba(186, 230, 253, 0.35),
      inset 0 1px 0 rgba(255, 255, 255, 0.9),
      inset 0 -1px 0 rgba(0, 0, 0, 0.08),
      0 0 0 12px rgba(186, 230, 253, 0.15);
    background: linear-gradient(135deg, rgba(255, 255, 255, 0.6) 0%, rgba(240, 248, 255, 0.5) 100%);
  }
}
</style>
