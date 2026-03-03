<script setup lang="ts">
import { Handle, type NodeProps, Position } from '@vue-flow/core'

// 1.定义自定义组件所需数据
const props = defineProps<NodeProps>()
</script>

<template>
  <div
    :class="[
      'flex w-[360px] flex-col gap-3 overflow-hidden rounded-2xl border-[2px] bg-white p-3 shadow-sm transition-all hover:shadow-md',
      props.selected ? 'border-blue-700' : 'border-transparent',
    ]"
  >
    <!-- 节点标题信息 -->
    <div class="flex items-center gap-2 min-w-0">
      <a-avatar shape="square" :size="24" class="bg-red-700 rounded-lg flex-shrink-0">
        <icon-filter :size="16" />
      </a-avatar>
      <div class="text-gray-700 font-semibold break-words line-clamp-2">{{ props.data?.title }}</div>
    </div>
    <!-- 输出变量列表 -->
    <div class="flex flex-col items-start bg-gray-100 rounded-lg p-3 min-w-0">
      <!-- 标题 -->
      <div class="flex items-center gap-2 mb-2 text-gray-700">
        <icon-caret-down />
        <div class="text-xs font-semibold">输出数据</div>
      </div>
      <!-- 输出变量列表 -->
      <div class="w-full flex flex-col gap-2 min-w-0">
        <div
          v-for="output in props.data?.outputs"
          :key="output.name"
          class="w-full flex flex-col gap-1 text-xs min-w-0"
        >
          <!-- 变量名和类型 -->
          <div class="flex items-center gap-2">
            <div class="text-gray-700 break-words">{{ output.name }}</div>
            <div class="text-gray-500 bg-gray-200 px-1 py-0.5 rounded flex-shrink-0 text-[10px]">
              {{ output.type }}
            </div>
          </div>
          <!-- 变量值 -->
          <div class="w-full min-w-0">
            <div
              v-if="output.value.type == 'ref'"
              class="bg-white text-gray-500 border px-2 py-1 rounded break-words"
            >
              引用 / {{ output.value.content.ref_var_name }}
            </div>
            <div v-else class="text-gray-500 px-2 py-1 bg-white rounded break-words">
              {{ output.value.content || '-' }}
            </div>
          </div>
        </div>
        <div v-if="!props.data?.outputs?.length" class="text-gray-500 text-xs px-0.5">-</div>
      </div>
    </div>
    <!-- 结束节点-连接句柄 -->
    <handle
      type="target"
      :position="Position.Left"
      class="!w-4 !h-4 !bg-blue-700 !text-white flex items-center justify-center"
    >
      <icon-plus :size="12" class="pointer-events-none" />
    </handle>
  </div>
</template>
