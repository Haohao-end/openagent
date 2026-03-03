<script setup lang="ts">
import { Handle, type NodeProps, Position } from '@vue-flow/core'

const props = defineProps<NodeProps>()

// 运算符显示映射
const operatorLabels: Record<string, string> = {
  equals: '等于',
  not_equals: '不等于',
  contains: '包含',
  not_contains: '不包含',
  starts_with: '开始于',
  ends_with: '结束于',
  is_empty: '为空',
  is_not_empty: '不为空',
  greater_than: '大于',
  less_than: '小于',
  greater_than_or_equal: '大于等于',
  less_than_or_equal: '小于等于',
}
</script>

<template>
  <div
    :class="[
      'flex w-[320px] flex-col gap-3 overflow-hidden rounded-2xl border-[2px] bg-white p-3 shadow-sm hover:shadow-md',
      props.selected ? 'border-amber-700' : 'border-transparent',
    ]"
  >
    <!-- 顶部节点标题 -->
    <div class="flex items-center gap-2 min-w-0">
      <a-avatar shape="square" :size="24" class="bg-amber-500 rounded-lg flex-shrink-0">
        <icon-branch :size="16" />
      </a-avatar>
      <div class="text-gray-700 font-semibold break-words line-clamp-2">{{ props.data?.title }}</div>
    </div>

    <!-- 输入变量列表 -->
    <div v-if="props.data?.inputs?.length > 0" class="flex flex-col items-start bg-gray-100 rounded-lg p-3 min-w-0">
      <div class="flex items-center gap-2 mb-2 text-gray-700">
        <icon-caret-down />
        <div class="text-xs font-semibold">输入数据</div>
      </div>
      <div class="w-full flex flex-col gap-2 min-w-0">
        <div
          v-for="input in props.data.inputs"
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
              v-if="input.value.type == 'ref'"
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

    <!-- 条件配置 -->
    <div class="flex flex-col items-start bg-gray-100 rounded-lg p-3 min-w-0">
      <div class="flex items-center gap-2 mb-2 text-gray-700">
        <icon-caret-down />
        <div class="text-xs font-semibold">条件配置</div>
      </div>
      <div class="w-full flex flex-col gap-2 min-w-0">
        <div
          v-for="(condition, idx) in props.data?.conditions"
          :key="idx"
          class="text-xs text-gray-700 bg-white rounded px-2 py-1.5 break-words"
        >
          <span class="font-medium">{{ condition.variable_name }}</span>
          <span class="text-gray-500 mx-1">{{ operatorLabels[condition.operator] || condition.operator }}</span>
          <span v-if="!['is_empty', 'is_not_empty'].includes(condition.operator)" class="font-medium">
            "{{ condition.compare_value }}"
          </span>
        </div>
        <div v-if="!props.data?.conditions?.length" class="text-gray-500 text-xs px-0.5">
          未配置条件
        </div>
        <div v-if="props.data?.conditions?.length > 1" class="text-xs text-gray-500 break-words">
          逻辑关系: {{ props.data?.logical_operator === 'and' ? '且 (AND)' : '或 (OR)' }}
        </div>
      </div>
    </div>

    <!-- 输入句柄 -->
    <handle
      type="target"
      :position="Position.Left"
      class="!w-4 !h-4 !bg-blue-700 !text-white flex items-center justify-center"
    >
      <icon-plus :size="12" class="pointer-events-none" />
    </handle>

    <!-- True 分支输出句柄 -->
    <handle
      id="true"
      type="source"
      :position="Position.Right"
      class="![top:35%] !flex !h-6 !w-6 !items-center !justify-center !border-2 !border-white !bg-green-600 !text-white"
    >
      <icon-check :size="16" class="pointer-events-none" />
    </handle>

    <!-- False 分支输出句柄 -->
    <handle
      id="false"
      type="source"
      :position="Position.Right"
      class="![top:65%] !flex !h-6 !w-6 !items-center !justify-center !border-2 !border-white !bg-red-600 !text-white"
    >
      <icon-close :size="16" class="pointer-events-none" />
    </handle>
  </div>
</template>
