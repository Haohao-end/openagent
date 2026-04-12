<script setup lang="ts">
import AiMessage from '@/components/AiMessage.vue'
import HumanMessage from '@/components/HumanMessage.vue'
import { nextTick, ref, watch, type PropType } from 'vue'
import { DynamicScroller, DynamicScrollerItem } from 'vue-virtual-scroller'
import 'vue-virtual-scroller/dist/vue-virtual-scroller.css'
import type { StreamMessage } from '@/views/shared/chat-stream'

type TimelineMessage = StreamMessage & {
  query: string
  image_urls: string[]
  suggested_questions?: string[]
}

const props = defineProps({
  messages: {
    type: Array as PropType<TimelineMessage[]>,
    default: () => [],
    required: true,
  },
  account: {
    type: Object as PropType<{ name: string; avatar: string }>,
    default: () => ({ name: '', avatar: '' }),
    required: true,
  },
  app: {
    type: Object,
    default: () => ({}),
    required: true,
  },
  loading: { type: Boolean, default: false },
  textToSpeechEnable: { type: Boolean, default: true },
})

const scroller = ref<{ $el?: HTMLElement; scrollToBottom?: () => void } | null>(null)
let scrollToBottomScheduled = false

const scheduleScrollToBottom = () => {
  if (scrollToBottomScheduled) return
  scrollToBottomScheduled = true

  const flushScrollToBottom = () => {
    scrollToBottomScheduled = false
    void nextTick(() => {
      void scrollToBottom()
      if (typeof requestAnimationFrame === 'function') {
        requestAnimationFrame(() => {
          void scrollToBottom()
        })
      }
    })
  }

  if (typeof requestAnimationFrame === 'function') {
    requestAnimationFrame(flushScrollToBottom)
    return
  }
  setTimeout(flushScrollToBottom, 16)
}

const scrollToBottom = async () => {
  await nextTick()
  scroller.value?.scrollToBottom?.()
  const element = scroller.value?.$el as HTMLElement | undefined
  if (element) element.scrollTop = element.scrollHeight
}

watch(
  () => props.messages.length,
  () => {
    scheduleScrollToBottom()
  },
)

defineExpose({ scrollToBottom })
</script>

<template>
  <dynamic-scroller
    ref="scroller"
    :items="props.messages.slice().reverse()"
    :min-item-size="1"
    class="h-full min-h-0 overflow-y-auto scrollbar-w-none"
  >
    <template #default="{ item, active }">
      <dynamic-scroller-item :key="item.id" :item="item" :active="active" :data-index="item.id">
        <div class="flex flex-col gap-6 py-6">
          <human-message :account="props.account" :query="item.query || ''" :image_urls="item.image_urls || []" />
          <ai-message
            :message_id="item.id"
            :enable_text_to_speech="props.textToSpeechEnable"
            :agent_thoughts="item.agent_thoughts"
            :answer="item.answer"
            :app="props.app"
            :suggested_questions="item.suggested_questions || []"
            :loading="props.loading && item.id === props.messages[0]?.id"
            :latency="item.latency"
            :total_token_count="item.total_token_count"
            :agent_thought_default_visible="false"
            :agent_thought_follow_latest="false"
          />
        </div>
      </dynamic-scroller-item>
    </template>
  </dynamic-scroller>
</template>
