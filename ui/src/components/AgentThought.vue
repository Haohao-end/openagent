<script setup lang="ts">
import { QueueEvent } from '@/config'
import { useAudioPlayer } from '@/hooks/use-audio'
import { copyTextToClipboard } from '@/utils/clipboard'
import { Message } from '@arco-design/web-vue'
import { computed, nextTick, onBeforeUnmount, ref, watch, type PropType } from 'vue'

// 1.定义自定义组件所需数据
const props = defineProps({
  loading: { type: Boolean, default: false, required: true },
  message_id: { type: String, default: '', required: false },
  variant: { type: String as PropType<'sidebar' | 'inline'>, default: 'sidebar', required: false },
  default_visible: { type: Boolean, default: false, required: false },
  follow_latest_thought: { type: Boolean, default: false, required: false },
  agent_thoughts: {
    type: Array as PropType<Record<string, any>[]>,
    default: () => [],
    required: true,
  },
})

const visible = ref(props.default_visible)
const containerRef = ref<HTMLElement | null>(null)
const activeThoughtKeys = ref<(string | number)[]>([])
const {
  activeMessageId,
  activeThoughtId,
  activeStreamType,
  thoughtAudioLoading,
  startThoughtAudioStream,
  stopAudioStream,
} = useAudioPlayer()

const thoughtItems = computed(() =>
  props.agent_thoughts.filter((item: any) =>
    [
      QueueEvent.longTermMemoryRecall,
      QueueEvent.agentThought,
      QueueEvent.datasetRetrieval,
      QueueEvent.agentAction,
      QueueEvent.agentMessage,
    ].includes(item.event),
  ),
)

const getThoughtKey = (agentThought: Record<string, any>) => {
  if (typeof agentThought?.id === 'number') return agentThought.id
  return String(agentThought?.id ?? '')
}

const latestThoughtKey = computed(() => {
  if (thoughtItems.value.length === 0) return ''
  return String(getThoughtKey(thoughtItems.value[thoughtItems.value.length - 1]))
})
const isInlineVariant = computed(() => props.variant === 'inline')

const isLatestThought = (agentThought: Record<string, any>) => {
  return String(getThoughtKey(agentThought)) === latestThoughtKey.value
}

const containerClass = computed(() => {
  const baseClass = 'flex flex-col rounded-2xl border border-gray-200 bg-white overflow-hidden'
  if (isInlineVariant.value) {
    return `${baseClass} max-w-full flex-shrink-0 ${visible.value ? 'w-[320px]' : 'w-[180px]'}`
  }
  return `${baseClass} max-w-full ${visible.value ? 'w-[320px]' : 'w-[180px]'}`
})

const toggleTitle = computed(() => {
  return visible.value ? '隐藏运行流程' : '显示运行流程'
})

const toggleLabel = computed(() => {
  return visible.value ? '隐藏运行流程' : '显示运行流程'
})

const headerClass = computed(() => {
  return `relative flex items-center h-10 px-4 cursor-pointer text-gray-700 whitespace-nowrap select-none bg-gray-100 transition-colors hover:bg-gray-200 ${
    visible.value ? 'rounded-t-2xl border-b border-gray-200' : 'rounded-2xl'
  }`
})

const getThoughtContent = (agentThought: Record<string, any>) => {
  const fromThought =
    agentThought?.event === QueueEvent.agentThought || agentThought?.event === QueueEvent.agentMessage
  return ((fromThought ? agentThought?.thought : agentThought?.observation) || '').trim()
}

const getThoughtTitle = (event: string) => {
  if (event === QueueEvent.longTermMemoryRecall) return '长期记忆召回'
  if (event === QueueEvent.agentThought) return '智能体推理'
  if (event === QueueEvent.datasetRetrieval) return '搜索知识库'
  if (event === QueueEvent.agentAction) return '调用工具'
  if (event === QueueEvent.agentMessage) return '智能体消息'
  return '运行步骤'
}

const getThoughtTitleTooltip = (event: string) => {
  if (event === QueueEvent.longTermMemoryRecall) return '长期记忆召回'
  if (event === QueueEvent.agentThought) return '智能体推理'
  if (event === QueueEvent.datasetRetrieval) return '搜索知识库'
  if (event === QueueEvent.agentAction) return '调用工具'
  if (event === QueueEvent.agentMessage) return '智能体消息'
  return '运行步骤'
}

const scrollThoughtIntoView = (thoughtKey: string) => {
  if (!containerRef.value || !thoughtKey) return
  const node = containerRef.value.querySelector(`[data-thought-key="${thoughtKey}"]`) as HTMLElement | null
  node?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
}

const syncLatestThought = async () => {
  if (!props.follow_latest_thought) return
  const latestKey = latestThoughtKey.value
  if (!latestKey) {
    activeThoughtKeys.value = []
    return
  }
  activeThoughtKeys.value = [latestKey]
  visible.value = true
  await nextTick()
  scrollThoughtIntoView(latestKey)
}

const handleCopyThought = async (agentThought: Record<string, any>) => {
  const content = getThoughtContent(agentThought)
  if (!content) {
    Message.warning('暂无可复制内容')
    return
  }
  await copyTextToClipboard(content)
  Message.success('推理内容已复制')
}

const isThoughtPlaying = (agentThoughtId: string) => {
  return (
    activeStreamType.value === 'thought' &&
    activeMessageId.value === props.message_id &&
    activeThoughtId.value === agentThoughtId
  )
}

const isThoughtLoading = (agentThoughtId: string) => {
  return (
    thoughtAudioLoading.value &&
    activeStreamType.value === 'thought' &&
    activeMessageId.value === props.message_id &&
    activeThoughtId.value === agentThoughtId
  )
}

const canShowThoughtAudioAction = computed(() => {
  return !props.loading && Boolean(props.message_id)
})

const handlePlayThought = async (agentThought: Record<string, any>) => {
  if (!props.message_id) {
    Message.warning('当前消息暂不支持语音播放')
    return
  }

  const content = getThoughtContent(agentThought)
  if (!content) {
    Message.warning('暂无可播放内容')
    return
  }

  const currentId = String(getThoughtKey(agentThought))
  if (!currentId) {
    Message.warning('当前推理内容暂不支持语音播放')
    return
  }

  if (isThoughtPlaying(currentId)) {
    stopAudioStream()
    return
  }

  await startThoughtAudioStream(props.message_id, currentId, content)
}

watch(
  () => thoughtItems.value.map((item) => String(getThoughtKey(item))),
  (currentIds, previousIds = []) => {
    if (!props.follow_latest_thought) return

    const latestChanged =
      currentIds.length !== previousIds.length ||
      currentIds[currentIds.length - 1] !== previousIds[previousIds.length - 1]

    const currentLatest = currentIds[currentIds.length - 1]
    const hasPinnedLatest =
      currentLatest !== undefined && activeThoughtKeys.value.map((key) => String(key)).includes(currentLatest)

    if (latestChanged || !hasPinnedLatest) {
      void syncLatestThought()
    }
  },
  { immediate: true },
)

watch(
  () => props.follow_latest_thought,
  (enabled) => {
    if (enabled) {
      void syncLatestThought()
    }
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  if (activeStreamType.value !== 'thought' || !activeThoughtId.value) return
  if (thoughtItems.value.some((item) => String(item?.id || '') === activeThoughtId.value)) {
    stopAudioStream()
  }
})
</script>

<template>
  <!-- 智能体推理步骤 -->
  <div ref="containerRef" :class="containerClass">
    <div :class="headerClass" :title="toggleTitle" @click="visible = !visible">
      <!-- 左侧图标与标题 -->
      <div class="flex items-center gap-2 font-medium text-gray-700 whitespace-nowrap">
        <icon-list />
        {{ toggleLabel }}
      </div>
      <!-- 右侧图标 -->
      <div class="absolute right-4 top-1/2 -translate-y-1/2 flex items-center">
        <template v-if="props.loading">
          <icon-loading />
        </template>
        <template v-else>
          <icon-up v-if="visible" />
          <icon-down v-else />
        </template>
      </div>
    </div>
    <!-- 底部内容 -->
    <a-collapse
      v-if="visible"
      class="agent-thought bg-transparent"
      destroy-on-hide
      :bordered="false"
      v-model:active-key="activeThoughtKeys"
    >
      <a-collapse-item
        v-for="agent_thought in thoughtItems"
        :key="getThoughtKey(agent_thought)"
        :class="['rounded-xl', { 'agent-thought-item--latest': isLatestThought(agent_thought) }]"
        :data-thought-key="String(getThoughtKey(agent_thought))"
      >
        <template #expand-icon>
          <icon-file v-if="agent_thought.event === QueueEvent.longTermMemoryRecall" />
          <icon-language v-else-if="agent_thought.event === QueueEvent.agentThought" />
          <icon-storage v-else-if="agent_thought.event === QueueEvent.datasetRetrieval" />
          <icon-tool v-else-if="agent_thought.event === QueueEvent.agentAction" />
          <icon-message v-else-if="agent_thought.event === QueueEvent.agentMessage" />
        </template>
        <template #header>
          <div
            :class="[
              'inline-block min-w-[6em] whitespace-nowrap font-semibold',
              isLatestThought(agent_thought) ? 'text-gray-800' : 'text-gray-700',
            ]"
            :title="getThoughtTitleTooltip(agent_thought.event)"
          >
            {{ getThoughtTitle(agent_thought.event) }}
          </div>
        </template>
        <template #extra>
          <div class="text-xs text-gray-400">{{ agent_thought.latency.toFixed(2) }}s</div>
        </template>
        <div class="flex items-start gap-2">
          <div class="flex-1 text-xs text-gray-500 line-clamp-4 break-all">
            {{ getThoughtContent(agent_thought) || '-' }}
          </div>
          <div class="flex items-center gap-1 flex-shrink-0">
            <icon-copy
              class="text-gray-400 cursor-pointer hover:text-gray-700"
              @click.stop="() => handleCopyThought(agent_thought)"
            />
            <template v-if="canShowThoughtAudioAction">
              <icon-loading
                v-if="isThoughtLoading(String(getThoughtKey(agent_thought)))"
                class="text-gray-400"
              />
              <icon-pause
                v-else-if="isThoughtPlaying(String(getThoughtKey(agent_thought)))"
                class="text-gray-400 cursor-pointer hover:text-gray-700"
                @click.stop="stopAudioStream"
              />
              <icon-play-circle
                v-else
                class="text-gray-400 cursor-pointer hover:text-gray-700"
                @click.stop="() => handlePlayThought(agent_thought)"
              />
            </template>
          </div>
        </div>
      </a-collapse-item>
    </a-collapse>
  </div>
</template>

<style scoped>
.agent-thought :deep(.arco-collapse-item) {
  border-bottom: 1px solid #f3f4f6;
}

.agent-thought :deep(.arco-collapse-item:last-child) {
  border-bottom: none;
}

.agent-thought :deep(.arco-collapse-item-header) {
  margin: 0;
  padding-top: 10px;
  padding-bottom: 10px;
  color: #374151;
  transition: background-color 0.18s ease;
}

.agent-thought :deep(.arco-collapse-item-header-left) {
  padding-right: 13px;
  padding-left: 34px;
}

.agent-thought :deep(.arco-collapse-item-header-right) {
  padding-right: 34px;
  padding-left: 13px;
}

.agent-thought :deep(.arco-collapse-item-header:hover) {
  background: #f9fafb;
}

.agent-thought :deep(.arco-collapse-item-active > .arco-collapse-item-header) {
  background: #f9fafb;
}

.agent-thought :deep(.arco-collapse-item-content) {
  padding-right: 13px;
  padding-bottom: 12px;
  padding-left: 34px;
}

.agent-thought-item--latest :deep(.arco-collapse-item-header) {
  background: #f9fafb;
}
</style>
