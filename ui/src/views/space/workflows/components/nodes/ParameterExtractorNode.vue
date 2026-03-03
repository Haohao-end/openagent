<script setup lang="ts">
import { Handle, type NodeProps, Position } from '@vue-flow/core'

const props = defineProps<NodeProps>()

const MODE_LABEL_MAP: Record<string, string> = {
  auto: '自动(JSON/KV)',
  json: '仅 JSON',
  kv: '仅 Key-Value',
}
</script>

<template>
  <div
    :class="[
      'flex w-[340px] flex-col gap-3 overflow-hidden rounded-2xl border-[2px] bg-white p-3 shadow-sm hover:shadow-md',
      props.selected ? 'border-blue-700' : 'border-transparent',
    ]"
  >
    <div class="flex items-center gap-2 min-w-0">
      <a-avatar shape="square" :size="24" class="bg-indigo-500 rounded-lg flex-shrink-0">
        <icon-branch :size="16" />
      </a-avatar>
      <div class="text-gray-700 font-semibold break-words line-clamp-2">{{ props.data?.title }}</div>
    </div>

    <div class="flex flex-col items-start bg-gray-100 rounded-lg p-3 min-w-0">
      <div class="flex items-center gap-2 mb-2 text-gray-700">
        <icon-caret-down />
        <div class="text-xs font-semibold">提取模式</div>
      </div>
      <div class="text-xs text-gray-700 break-words w-full">
        {{ MODE_LABEL_MAP[String(props.data?.mode ?? 'auto')] ?? '自动(JSON/KV)' }}
      </div>
    </div>

    <div class="flex flex-col items-start bg-gray-100 rounded-lg p-3 min-w-0">
      <div class="flex items-center gap-2 mb-2 text-gray-700">
        <icon-caret-down />
        <div class="text-xs font-semibold">输入文本</div>
      </div>
      <div class="w-full flex flex-col gap-2 min-w-0">
        <div
          v-for="input in props.data?.inputs"
          :key="input.name"
          class="w-full flex flex-col gap-1 text-xs min-w-0"
        >
          <!-- 变量名和类型 -->
          <div class="flex items-center gap-2">
            <div class="text-gray-700 break-words">{{ input.name }}</div>
            <div class="text-gray-500 bg-gray-200 px-1 py-0.5 rounded flex-shrink-0 text-[10px]">{{ input.type }}</div>
          </div>
          <!-- 变量值 -->
          <div class="w-full min-w-0">
            <div
              v-if="input.value.type === 'ref'"
              class="bg-white text-gray-500 border px-2 py-1 rounded break-words"
            >
              引用 / {{ input.value.content.ref_var_name }}
            </div>
            <div v-else class="text-gray-500 px-2 py-1 bg-white rounded break-words">
              {{ input.value.content || '-' }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="flex flex-col items-start bg-gray-100 rounded-lg p-3 min-w-0">
      <div class="flex items-center gap-2 mb-2 text-gray-700">
        <icon-caret-down />
        <div class="text-xs font-semibold">提取字段</div>
      </div>
      <div class="flex flex-wrap gap-2 w-full min-w-0">
        <div
          v-for="output in props.data?.outputs"
          :key="output.name"
          class="flex items-center gap-2 text-xs bg-white px-2 py-1 rounded"
        >
          <div class="text-gray-700 break-words">
            {{ output.name }}
            <span v-if="output.required" class="text-red-700">*</span>
          </div>
          <div class="text-gray-500 bg-gray-200 px-1 py-0.5 rounded flex-shrink-0 text-[10px]">{{ output.type }}</div>
        </div>
      </div>
    </div>

    <handle
      type="source"
      :position="Position.Right"
      class="!w-4 !h-4 !bg-blue-700 !text-white flex items-center justify-center"
    >
      <icon-plus :size="12" class="pointer-events-none" />
    </handle>
    <handle
      type="target"
      :position="Position.Left"
      class="!w-4 !h-4 !bg-blue-700 !text-white flex items-center justify-center"
    >
      <icon-plus :size="12" class="pointer-events-none" />
    </handle>
  </div>
</template>
