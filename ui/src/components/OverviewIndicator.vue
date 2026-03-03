<script setup lang="ts">
// 1.定义自定义组件所需数据
const props = defineProps({
  title: { type: String, default: '' },
  help: { type: String, default: '' },
  data: { type: Number, default: 0 },
  unit: { type: String, default: '次' },
  pop: { type: Number, default: 0 },
})
</script>

<template>
  <div class="flex flex-col flex-1 gap-3 bg-white border border-gray-200 rounded-lg px-6 py-5">
    <!-- 指标卡标题 -->
    <div class="flex items-center gap-2 text-gray-700">
      <a-avatar shape="circle" :size="32" class="bg-blue-200">
        <!-- 创建命名插槽 -->
        <slot name="icon" />
      </a-avatar>
      <div class="">{{ props.title }}</div>
      <a-tooltip :content="props.help">
        <icon-question-circle />
      </a-tooltip>
    </div>
    <!-- 指标卡数据 -->
    <div class="flex items-baseline gap-4">
      <!-- 数据 -->
      <div class="flex items-baseline gap-1 text-gray-700 font-semibold">
        <div class="text-2xl">
          {{ props.data % 1 !== 0 ? props.data.toFixed(2) : props.data.toString() }}
        </div>
        <div class="">{{ props.unit }}</div>
      </div>
      <!-- 环比 -->
      <div class="flex items-center gap-1 text-gray-500 text-xs">
        <div class="">环比</div>
        <a-avatar shape="circle" :size="14" class="bg-blue-200">
          <icon-sync class="text-[14px] text-blue-700" />
        </a-avatar>
        <div class="text-blue-700">{{ (props.pop * 100).toFixed(2) }}%</div>
      </div>
    </div>
  </div>
</template>

<style scoped></style>
