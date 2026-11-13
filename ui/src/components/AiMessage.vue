<script setup lang="ts">
import { computed, type PropType } from 'vue'
import { Message } from '@arco-design/web-vue'
import { useI18n } from 'vue-i18n'
import DotFlashing from '@/components/DotFlashing.vue'
import { useAudioPlayer } from '@/hooks/use-audio'
import { useMarkdownRenderer } from '@/hooks/use-markdown-renderer'
import { copyTextToClipboard } from '@/utils/clipboard'
import {
  mergeChatArtifacts,
  normalizeChatOutputParts,
  type ChatArtifact,
  type ChatOutputPart,
} from '@/views/shared/chat-output'
import AgentThought from './AgentThought.vue'
import ChatImageGallery from './ChatImageGallery.vue'
import DeepAgentTimeline from './DeepAgentTimeline.vue'
import DeepThinkingPanel from './DeepThinkingPanel.vue'
import CallableTraceTimeline from './chat/CallableTraceTimeline.vue'
import { QueueEvent } from '@/config'
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
  answer_parts: {
    type: Array as PropType<Array<Record<string, unknown>>>,
    default: () => [],
    required: false,
  },
  artifacts: {
    type: Array as PropType<Array<Record<string, unknown>>>,
    default: () => [],
    required: false,
  },
  loading: { type: Boolean, default: false, required: false },
  latency: { type: Number, default: 0, required: false },
  total_token_count: { type: Number, default: 0, required: false },
  agent_thoughts: {
    type: Array as PropType<Array<Record<string, unknown>>>,
    default: () => [],
    required: true,
  },
  callable_trace_events: {
    type: Array as PropType<unknown[]>,
    default: () => [],
    required: false,
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
const { t } = useI18n()
const { renderMarkdown, handleMarkdownCopyClick } = useMarkdownRenderer()
const normalizedArtifacts = computed(() => {
  return mergeChatArtifacts([], props.artifacts) as ChatArtifact[]
})
const resolvedAnswerParts = computed(() => {
  return normalizeChatOutputParts(props.answer_parts, props.answer, normalizedArtifacts.value) as ChatOutputPart[]
})
const renderedTextParts = computed(() => {
  return resolvedAnswerParts.value
    .filter((part): part is Extract<ChatOutputPart, { type: 'text' }> => part.type === 'text')
    .map((part, index) => ({
      key: `text-${index}`,
      html: renderMarkdown(part.text),
    }))
})
const galleryImages = computed(() => {
  const images: Array<{ name: string, url: string, mime_type?: string, extension?: string }> = []
  const seenUrls = new Set<string>()

  for (const part of resolvedAnswerParts.value) {
    if (part.type !== 'image')
      continue
    const url = String(part.url || '').trim()
    if (!url || seenUrls.has(url))
      continue
    seenUrls.add(url)
    images.push({
      name: part.name || '',
      url,
      mime_type: part.mime_type,
      extension: part.extension,
    })
  }

  return images
})
const renderedArtifactParts = computed(() => {
  return resolvedAnswerParts.value
    .filter((part): part is Extract<ChatOutputPart, { type: 'artifact' }> => part.type === 'artifact')
    .map((part, index) => ({
      key: `artifact-${index}`,
      name: part.name,
      url: part.url,
      mime_type: part.mime_type,
      extension: part.extension,
      size: part.size,
    }))
})
const hasRenderableAnswer = computed(() => {
  return renderedTextParts.value.length > 0 || galleryImages.value.length > 0 || renderedArtifactParts.value.length > 0
})
const avatarText = computed(() => {
  return String(props.app?.avatar_text || '').trim()
})

const deepTimelineThoughts = computed(() => {
  return props.agent_thoughts.filter((t: Record<string, unknown>) =>
    [
      QueueEvent.deepStep,
      QueueEvent.deepComplete,
      QueueEvent.deepArtifactCreated,
    ].includes(String(t.event ?? '')),
  ) as Record<string, unknown>[]
})

/** 兼容旧版 deep_thinking 文本事件 */
const legacyDeepThinkingThought = computed(() => {
  return props.agent_thoughts.find(
    (t: Record<string, unknown>) => t.event === QueueEvent.deepThinking,
  ) as Record<string, unknown> | undefined
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
  Message.success(t('chat.messages.aiCopied'))
}

const handleMarkdownClick = async (event: MouseEvent) => {
  await handleMarkdownCopyClick(event, { successMessage: t('chat.messages.codeCopied') })
}
</script>

<template>
  <div class="flex max-w-full min-w-0 gap-2 group">
    <!-- 左侧图标 -->
    <a-avatar
      v-if="avatarText"
      :size="36"
      class="flex-shrink-0 text-sm bg-blue-700"
    >
      {{ avatarText }}
    </a-avatar>
    <a-avatar v-else-if="props.app?.icon" :size="36" shape="circle" class="flex-shrink-0" :image-url="props.app?.icon" />
    <a-avatar v-else :size="36" shape="circle" class="flex-shrink-0 bg-blue-700">
      <icon-apps />
    </a-avatar>
    <!-- 右侧名称与消息 -->
    <div class="flex-1 min-w-0 max-w-full flex flex-col items-start gap-2">
      <!-- 应用名称 -->
      <div class="text-gray-700 font-bold text-sm">{{ props.app?.name }}</div>
      <!-- 深度思考面板（在推理步骤之前单独展示） -->
      <deep-agent-timeline
        v-if="deepTimelineThoughts.length > 0"
        :thoughts="deepTimelineThoughts"
        :loading="props.loading"
      />
      <deep-thinking-panel
        v-else-if="legacyDeepThinkingThought"
        :thought="String(legacyDeepThinkingThought.thought ?? '')"
        :latency="Number(legacyDeepThinkingThought.latency ?? 0)"
        :loading="props.loading"
      />
      <CallableTraceTimeline
        v-if="props.callable_trace_events.length > 0"
        :events="props.callable_trace_events"
      />
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
      <div class="w-full max-w-full min-w-0 flex flex-col gap-1">
        <!-- AI消息 -->
        <div
          v-if="props.loading && !hasRenderableAnswer"
          class="message-bubble-content glass-message-bubble px-4 py-3 rounded-2xl break-all transition-all duration-300"
        >
          <dot-flashing />
        </div>
        <template v-else>
          <template v-for="part in renderedTextParts" :key="part.key">
            <div
              :class="[
                'message-bubble-content glass-message-bubble markdown-body px-4 py-3 rounded-2xl break-all transition-all duration-300',
                isCurrentPlaying ? 'ai-message-playing' : '',
              ]"
              v-html="part.html"
              @click="handleMarkdownClick"
            ></div>
          </template>
          <chat-image-gallery
            v-if="galleryImages.length > 0"
            :images="galleryImages"
            :title="t('chat.gallery.generatedImages')"
            class="message-gallery-card"
          />
          <template v-for="part in renderedArtifactParts" :key="part.key">
            <div class="message-artifact-card">
              <div class="message-artifact-card__name">{{ part.name }}</div>
              <div class="message-artifact-card__meta">
                <span v-if="part.extension">{{ part.extension }}</span>
                <span v-if="typeof part.size === 'number'">{{ part.size }} bytes</span>
                <span v-else-if="part.mime_type">{{ part.mime_type }}</span>
              </div>
              <a
                class="message-artifact-card__link"
                :href="part.url"
                target="_blank"
                rel="noreferrer"
              >
                {{ t('chat.deepTimeline.downloadAttachment') }}
              </a>
            </div>
          </template>
        </template>
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
      <div v-if="props.suggested_questions.length > 0" class="max-w-full min-w-0 flex flex-col gap-2">
        <div v-for="(suggested_question, idx) in props.suggested_questions" :key="idx"
          class="glass-suggestion-bubble max-w-full px-4 py-2 border rounded-lg text-gray-700 cursor-pointer break-words transition-all duration-300"
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

.message-bubble-content {
  width: fit-content;
  max-width: min(600px, 100%);
  min-width: 0;
}

.message-artifact-card {
  width: min(420px, 100%);
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 14px 16px;
  border-radius: 18px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(248, 250, 252, 0.94));
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.08);
}

.message-artifact-card__name {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
  word-break: break-all;
}

.message-artifact-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 12px;
  color: #64748b;
}

.message-artifact-card__link {
  font-size: 13px;
  color: #1d4ed8;
  text-decoration: none;
}

.message-artifact-card__link:hover {
  text-decoration: underline;
}

.message-gallery-card {
  width: min(560px, 100%);
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

:deep(.markdown-body p),
:deep(.markdown-body li),
:deep(.markdown-body blockquote) {
  overflow-wrap: anywhere;
}

:deep(.markdown-body .md-code-block) {
  max-width: 100%;
  min-width: 0;
  margin: 0 0 12px 0;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  overflow-x: auto;
}

:deep(.markdown-body .md-code-header) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-width: 0;
  padding: 6px 10px;
  background: #f9fafb;
  border-bottom: 1px solid #e5e7eb;
}

:deep(.markdown-body .md-code-lang) {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #6b7280;
  font-size: 12px;
  line-height: 16px;
}

:deep(.markdown-body .md-code-copy-btn) {
  flex-shrink: 0;
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
  max-width: 100%;
  margin: 0;
  border: 0;
  border-radius: 0;
  overflow-x: auto;
}

:deep(.markdown-body table) {
  max-width: 100%;
  overflow-x: auto;
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
