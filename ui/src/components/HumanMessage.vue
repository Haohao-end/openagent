<script setup lang="ts">
import { Message } from '@arco-design/web-vue'
import { copyTextToClipboard } from '@/utils/clipboard'
import { getUserAvatarUrl } from '@/utils/helper'

// 1.定义自定义组件所需数据
const props = defineProps({
  account: {
    type: Object,
    default: () => {
      return {}
    },
    required: true,
  },
  query: { type: String, default: '', required: true },
  image_urls: { type: Array, default: () => [] },
})

const handleCopyHumanMessage = async () => {
  const imageUrls = props.image_urls.map((image_url) => String(image_url))
  const humanMessage = [...imageUrls, props.query].filter((item) => item.trim() !== '').join('\n')
  if (!humanMessage) return

  await copyTextToClipboard(humanMessage)
  Message.success('用户消息已复制')
}
</script>

<template>
  <div class="flex justify-end">
    <div class="flex items-start gap-2 group">
      <!-- 左侧昵称与消息 -->
      <div class="flex flex-col items-end gap-2">
        <!-- 账号昵称 -->
        <div class="text-gray-700 font-bold text-right text-sm">{{ props.account?.name }}</div>
        <!-- 人类消息 -->
        <div class="flex flex-col items-end gap-1">
          <div
            class="glass-message-bubble px-4 py-3 rounded-2xl break-all max-w-[600px] transition-all duration-300"
          >
            <a-image v-for="(image_url, idx) in props.image_urls" :key="idx" :src="String(image_url)" />
            {{ props.query }}
          </div>
          <div class="flex items-center justify-end pr-1">
            <icon-copy
              class="text-gray-400 cursor-pointer hover:text-gray-700 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none group-hover:pointer-events-auto"
              @click="handleCopyHumanMessage"
            />
          </div>
        </div>
      </div>
      <!-- 右侧头像 -->
      <a-avatar :size="36" shape="circle" class="flex-shrink-0" :image-url="getUserAvatarUrl(props.account?.avatar, props.account?.name)" />
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
</style>
