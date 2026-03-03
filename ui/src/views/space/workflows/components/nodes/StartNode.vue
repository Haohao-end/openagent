<script setup lang="ts">
import { Handle, type NodeProps, Position } from '@vue-flow/core'

// 1.定义自定义组件所需数据
const props = defineProps<NodeProps>()
</script>

<template>
  <div
    :class="[
      'flex w-[240px] flex-col gap-3 overflow-hidden rounded-3xl border-[2px] bg-white p-3 shadow-sm hover:shadow-md',
      props.selected ? 'border-blue-700' : 'border-transparent',
    ]"
  >
    <!-- 顶部节点标题 -->
    <div class="flex items-center gap-2 min-w-0">
      <a-avatar shape="square" :size="24" class="bg-blue-700 rounded-lg flex-shrink-0">
        <icon-home :size="16" />
      </a-avatar>
      <div class="text-gray-700 font-semibold break-words line-clamp-2">{{ props.data?.title }}</div>
    </div>
    <!-- 底部输入变量列表 -->
    <div class="flex flex-col items-start bg-gray-100 rounded-lg p-3 min-w-0">
      <!-- 标题 -->
      <div class="flex items-center gap-2 mb-2 text-gray-700">
        <icon-caret-down />
        <div class="text-xs font-semibold">输入数据</div>
      </div>
      <!-- 变量列表 -->
      <div class="flex flex-wrap gap-2 w-full min-w-0">
        <div
          v-for="input in props.data?.inputs"
          :key="input.name"
          class="flex items-center gap-1 text-xs bg-white px-2 py-1 rounded"
        >
          <div class="text-gray-700 break-words">{{ input.name }}</div>
          <div v-if="input.required" class="flex-shrink-0 text-red-700">*</div>
          <div class="text-gray-500 bg-gray-200 px-1 py-0.5 rounded flex-shrink-0 text-[10px]">{{ input.type }}</div>
        </div>
        <div v-if="!props.data?.inputs?.length" class="text-gray-500 text-xs px-0.5">-</div>
      </div>
    </div>
    <!-- 边起点句柄位置在右侧 -->
    <handle
      type="source"
      :position="Position.Right"
      class="!w-4 !h-4 !bg-blue-700 !text-white flex items-center justify-center"
    >
      <icon-plus :size="12" class="pointer-events-none" />
    </handle>
  </div>
</template>
