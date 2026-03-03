<script setup lang="ts">
import { useVueFlow } from '@vue-flow/core'
import { computed, ref, watch } from 'vue'
import { useDebugWorkflow } from '@/hooks/use-workflow'
import type { ValidatedError } from '@arco-design/web-vue'
import {
  findWorkflowOutputs,
  sumWorkflowLatency,
  sumWorkflowToolLatency,
  type DebugNodeResult,
} from '@/views/space/workflows/utils/debug-metrics'

type WorkflowInput = {
  name: string
  type: string
  required?: boolean
}

// 1.定义自定义组件所需数据
const props = defineProps({
  visible: { type: Boolean, required: true, default: false },
  workflow_id: { type: String, required: true, default: '' },
})
const emits = defineEmits(['update:visible', 'debug-success'])
const { nodes } = useVueFlow()
const form = ref<Record<string, string | number | boolean>>({})
const nodeResults = ref<DebugNodeResult[]>([])
const activatedTab = ref('input')
const {
  error: debugWorkflowError,
  loading: debugWorkflowLoading,
  handleDebugWorkflow,
} = useDebugWorkflow()

// 2.输入变量列表动态计算函数
const inputs = computed<WorkflowInput[]>(() => {
  // 2.1 获取节点数据中的开始节点
  const startNode = nodes.value.find((item) => item.type === 'start')

  // 2.2 检查节点数据并返回
  return (startNode?.data?.inputs ?? []) as WorkflowInput[]
})

// 3.定义输出结果动态计算函数
const outputs = computed(() => {
  return findWorkflowOutputs(nodeResults.value)
})

// 4.定义整个工作流的响应耗时
const latency = computed(() => {
  return sumWorkflowLatency(nodeResults.value)
})

// 5.定义工具/插件响应耗时
const toolLatency = computed(() => {
  return sumWorkflowToolLatency(nodeResults.value)
})

// 6.定义表单提交函数
const onSubmit = async ({ errors }: { errors: Record<string, ValidatedError> | undefined }) => {
  // 6.1 运行前先将历史运行清空
  nodeResults.value = []
  debugWorkflowError.value = ''

  // 6.2 检查表单是否出错，如果出错则直接结束
  if (errors) return

  // 6.3 将tab选项切换到输出选项卡
  activatedTab.value = 'output'

  // 6.4 调用hooks发起请求
  await handleDebugWorkflow(
    props.workflow_id,
    form.value,
    (event_response: { data?: DebugNodeResult }) => {
      if (event_response?.data) {
        nodeResults.value.push(event_response.data)
      }
    },
  )

  // 6.5 如果调试成功（没有错误且有输出结果），触发 debug-success 事件
  if (!debugWorkflowError.value && outputs.value) {
    emits('debug-success')
  }
}

// 7.监听调试模态窗的显示或隐藏
watch(
  () => props.visible,
  (newValue) => {
    if (newValue) {
      debugWorkflowError.value = ''
      nodeResults.value = []
      activatedTab.value = 'input'
      form.value = {}
    }
  },
)
</script>

<template>
  <div
    v-if="props.visible"
    class="absolute right-0 top-0 bottom-0 w-[400px] bg-white z-50 border-l overflow-scroll scrollbar-w-none p-4"
  >
    <!-- 调试面板标题 -->
    <div class="flex items-center justify-between mb-2">
      <!-- 左侧标题 -->
      <div class="text-base font-bold text-gray-700">工作流调试</div>
      <!-- 右侧关闭按钮 -->
      <a-button
        size="mini"
        type="text"
        class="!text-gray-700"
        @click="() => emits('update:visible', false)"
      >
        <template #icon>
          <icon-close />
        </template>
      </a-button>
    </div>
    <!-- tab面板 -->
    <a-tabs v-model:active-key="activatedTab">
      <a-tab-pane key="input" title="输入">
        <!-- 无输入数据样式 -->
        <a-empty v-if="inputs.length <= 0" class="my-4">该工作流暂无输入数据</a-empty>
        <!-- 有数据的UI -->
        <a-form :model="form" layout="vertical" @submit="onSubmit">
          <!-- 输入数据表单列表 -->
          <a-form-item
            v-for="(input, idx) in inputs"
            :key="idx"
            :field="input.name"
            :required="input.required"
            hide-asterisk
          >
            <template #label>
              <div class="flex items-center gap-2">
                <div class="">{{ input.name }}</div>
                <div v-if="input.required" class="text-red-700">*</div>
                <div class="text-xs text-gray-500 bg-gray-200 px-1 py-0.5 rounded flex-shrink-0">
                  {{ input.type }}
                </div>
              </div>
            </template>
            <a-input
              v-if="input.type === 'string'"
              v-model="form[input.name]"
              placeholder="请输入参考值"
              class="!rounded-lg"
            />
            <a-input-number
              v-else-if="['int', 'float'].includes(input.type)"
              v-model="form[input.name]"
              placeholder="请输入参考值"
              class="!rounded-lg"
            />
            <a-radio-group v-else-if="input.type === 'boolean'" v-model="form[input.name]">
              <a-radio :value="true">是</a-radio>
              <a-radio :value="false">否</a-radio>
            </a-radio-group>
          </a-form-item>
          <a-button
            :loading="debugWorkflowLoading"
            type="primary"
            html-type="submit"
            long
            class="rounded-lg"
          >
            <template #icon>
              <icon-play-arrow />
            </template>
            开始运行
          </a-button>
        </a-form>
      </a-tab-pane>
      <a-tab-pane key="output" title="输出">
        <!-- 运行中的状态 -->
        <div
          v-if="debugWorkflowLoading"
          class="flex flex-col gap-2 bg-green-100 rounded-lg border border-green-500 p-3 mb-2"
        >
          <!-- 加载状态 -->
          <div class="flex items-center gap-2">
            <icon-loading class="text-green-500" />
            <div class="text-green-500">工作流运行中</div>
          </div>
          <!-- 当前执行完成的节点 -->
          <div class="text-gray-500 text-xs">
            已成功运行节点【{{ nodeResults.slice(-1)[0]?.node_data?.title ?? '-' }}】
          </div>
        </div>
        <!-- 非运行时状态 -->
        <div v-else class="flex flex-col gap-2">
          <!-- 运行失败UI -->
          <div
            v-if="debugWorkflowError"
            class="flex flex-col gap-2 bg-red-100 p-3 rounded-lg border border-red-700"
          >
            <div class="flex items-center gap-2 text-red-500">
              <icon-exclamation-circle-fill />
              <div>工作流运行失败</div>
            </div>
            <div class="text-xs text-gray-500">{{ debugWorkflowError }}</div>
          </div>
          <!-- 运行成功UI -->
          <div
            v-if="outputs"
            class="flex flex-col gap-2 bg-green-100 p-3 rounded-lg border border-green-500"
          >
            <!-- 状态统计 -->
            <div class="flex items-center gap-2 text-green-500">
              <icon-check-circle-fill />
              <div class="">运行成功</div>
            </div>
            <!-- 数据统计 -->
            <div class="flex items-center gap-2 text-xs">
              <div class="flex-1 flex flex-col gap-2">
                <div class="text-gray-500">总消耗</div>
                <div class="text-gray-700">500 Tokens</div>
              </div>
              <div class="flex-1 flex flex-col gap-2">
                <div class="text-gray-500">总用时</div>
                <div class="text-gray-700">{{ latency.toFixed(2) }}s</div>
              </div>
              <div class="flex-1 flex flex-col gap-2">
                <div class="text-gray-500">插件消耗</div>
                <div class="text-gray-700">{{ toolLatency.toFixed(2) }}s</div>
              </div>
            </div>
          </div>
          <!-- 运行结果 -->
          <div v-if="outputs" class="bg-gray-700 rounded-lg p-3 text-white">{{ outputs }}</div>
        </div>
        <!-- 空数据状态 -->
        <a-empty v-if="!debugWorkflowLoading && !outputs && !debugWorkflowError" class="my-4">
          该工作流暂无运行调试结果
        </a-empty>
      </a-tab-pane>
    </a-tabs>
  </div>
</template>

<style scoped></style>
