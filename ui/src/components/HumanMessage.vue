<script setup lang="ts">
import { Message } from '@arco-design/web-vue'
import { copyTextToClipboard } from '@/utils/clipboard'

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
    <div class="flex items-start gap-2 group max-w-full">
      <!-- 左侧昵称与消息 -->
      <div class="flex flex-col items-end gap-2 min-w-0 max-w-[80%]">
        <!-- 账号昵称 -->
        <div class="text-gray-700 font-bold text-right">{{ props.account?.name }}</div>
        <!-- 人类消息 -->
        <div class="inline-flex flex-col items-end max-w-full gap-1">
          <div
            class="bg-blue-100 border border-blue-200 text-gray-700 px-4 py-3 rounded-2xl break-all w-fit max-w-full"
          >
            <a-image v-for="(image_url, idx) in props.image_urls" :key="idx" :src="String(image_url)" />
            {{ props.query }}
          </div>
          <div class="h-4 flex items-center justify-end pr-1">
            <icon-copy
              class="text-gray-400 cursor-pointer hover:text-gray-700 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none group-hover:pointer-events-auto"
              @click="handleCopyHumanMessage"
            />
          </div>
        </div>
      </div>
      <!-- 右侧头像 -->
      <a-avatar :size="36" shape="circle" class="flex-shrink-0" :image-url="props.account?.avatar" />
    </div>
  </div>
</template>

<style scoped></style>
