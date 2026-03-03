<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch, inject } from 'vue'
import { useVueFlow } from '@vue-flow/core'
import { cloneDeep, debounce } from 'lodash'
import { type ValidatedError } from '@arco-design/web-vue'
import { getReferencedVariables } from '@/utils/helper'

type TextProcessorInput = {
  name: string
  type: string
  content?: string
  ref: string
}

type TextProcessorNodeForm = {
  id: string
  type: string
  title: string
  description: string
  mode: string
  input: TextProcessorInput
  outputs: Array<Record<string, unknown>>
}

const props = defineProps({
  visible: { type: Boolean, required: true, default: false },
  node: {
    type: Object,
    required: true,
    default: () => {
      return {}
    },
  },
  loading: { type: Boolean, required: true, default: false },
})
const emits = defineEmits(['update:visible', 'updateNode'])
const { nodes, edges } = useVueFlow()
const form = ref<TextProcessorNodeForm>({
  id: '',
  type: '',
  title: '',
  description: '',
  mode: 'trim',
  input: {
    name: 'text',
    type: 'string',
    content: '',
    ref: '',
  },
  outputs: [],
})
const isSyncingForm = ref(false)

// 注入只读状态
const isReadonly = inject<boolean>('isReadonly', false)
const debounceAutoSave = debounce(() => {
  // 只读模式下不自动保存
  if (isReadonly) return
  void onSubmit({ errors: undefined })
}, 800)

const inputRefOptions = computed(() => {
  return getReferencedVariables(cloneDeep(nodes.value), cloneDeep(edges.value), props.node.id)
})

const onSubmit = async ({ errors }: { errors: Record<string, ValidatedError> | undefined }) => {
  if (errors) return

  const input = form.value.input
  emits('updateNode', {
    id: props.node.id,
    title: form.value.title,
    description: form.value.description,
    mode: form.value.mode,
    inputs: [
      {
        name: input.name,
        description: '',
        required: true,
        type: 'string',
        value: {
          type: input.type === 'ref' ? 'ref' : 'literal',
          content:
            input.type === 'ref'
              ? {
                  ref_node_id: input.ref.split('/', 2)[0] || '',
                  ref_var_name: input.ref.split('/', 2)[1] || '',
                }
              : String(input.content ?? ''),
        },
        meta: {},
      },
    ],
    outputs: [
      { name: 'output', type: 'string', value: { type: 'generated', content: '' } },
      { name: 'length', type: 'int', value: { type: 'generated', content: 0 } },
    ],
  })
}

watch(
  () => props.node?.id,
  () => {
    const newNode = props.node
    if (!newNode?.id) return
    isSyncingForm.value = true
    debounceAutoSave.flush()
    debounceAutoSave.cancel()

    const sourceInput = cloneDeep(newNode.data?.inputs?.[0])
    const ref =
      sourceInput?.value?.type === 'ref'
        ? `${sourceInput.value.content.ref_node_id}/${sourceInput.value.content.ref_var_name}`
        : ''

    form.value = {
      id: newNode.id,
      type: newNode.type,
      title: newNode.data.title,
      description: newNode.data.description,
      mode: newNode.data.mode || 'trim',
      input: {
        name: sourceInput?.name || 'text',
        type: sourceInput?.value?.type === 'ref' ? 'ref' : 'string',
        content: sourceInput?.value?.type === 'literal' ? sourceInput?.value?.content : '',
        ref,
      },
      outputs: [
        { name: 'output', type: 'string', value: { type: 'generated', content: '' } },
        { name: 'length', type: 'int', value: { type: 'generated', content: 0 } },
      ],
    }

    nextTick(() => {
      isSyncingForm.value = false
    })
  },
  { immediate: true },
)

watch(
  form,
  () => {
    if (isSyncingForm.value) return
    debounceAutoSave()
  },
  { deep: true },
)

onBeforeUnmount(() => {
  debounceAutoSave.flush()
  debounceAutoSave.cancel()
})
</script>

<template>
  <div
    v-if="props.visible"
    id="text-processor-node-info"
    class="absolute top-0 right-0 bottom-0 w-[400px] border-l z-50 bg-white overflow-scroll scrollbar-w-none p-3"
  >
    <!-- 只读模式提示横幅 -->
    <div v-if="isReadonly" class="mb-3 p-3 bg-orange-50 border border-orange-200 rounded-lg">
      <div class="flex items-center gap-2 text-orange-700">
        <icon-lock class="flex-shrink-0" />
        <span class="text-sm font-medium">预览模式：所有配置仅供查看，无法修改</span>
      </div>
    </div>

    <div class="flex items-center justify-between gap-3 mb-2">
      <div class="flex items-center gap-1 flex-1">
        <a-avatar :size="30" shape="square" class="bg-teal-500 rounded-lg flex-shrink-0">
          <icon-branch />
        </a-avatar>
        <a-input
          v-model:model-value="form.title"
          :disabled="isReadonly" placeholder="请输入标题"
          class="!bg-white text-gray-700 font-semibold px-2"
        />
      </div>
      <a-button
        type="text"
        size="mini"
        class="!text-gray700 flex-shrink-0"
        @click="() => emits('update:visible', false)"
      >
        <template #icon>
          <icon-close />
        </template>
      </a-button>
    </div>

    <a-textarea
      :auto-size="{ minRows: 3, maxRows: 5 }"
      v-model="form.description"
      :disabled="isReadonly" class="rounded-lg text-gray-700 !text-xs"
      placeholder="输入描述..."
    />

    <a-divider class="my-2" />

    <a-form size="mini" :model="form" :disabled="isReadonly" layout="vertical">
      <a-form-item field="mode" label="处理模式">
        <a-select v-model="form.mode" size="mini">
          <a-option value="trim">去首尾空格</a-option>
          <a-option value="lower">转小写</a-option>
          <a-option value="upper">转大写</a-option>
          <a-option value="title">标题格式</a-option>
        </a-select>
      </a-form-item>

      <div class="flex flex-col gap-2">
        <div class="flex items-center gap-2 text-gray-700 font-semibold">输入参数</div>
        <div class="flex items-center gap-1 text-xs text-gray-500 mb-2">
          <div class="w-[30%]">参数名</div>
          <div class="w-[24%]">类型</div>
          <div class="w-[46%]">值</div>
        </div>
        <div class="flex items-center gap-1">
          <div class="w-[30%] flex-shrink-0">
            <a-input v-model="form.input.name" size="mini" placeholder="请输入参数名" class="!px-2" />
          </div>
          <div class="w-[24%] flex-shrink-0">
            <a-select
              size="mini"
              v-model="form.input.type"
              class="px-2"
              :options="[
                { label: '引用', value: 'ref' },
                { label: 'STRING', value: 'string' },
              ]"
            />
          </div>
          <div class="w-[46%] flex-shrink-0">
            <a-input
              v-if="form.input.type !== 'ref'"
              size="mini"
              v-model="form.input.content"
              placeholder="请输入文本"
            />
            <a-select
              v-else
              placeholder="请选择引用变量"
              size="mini"
              tag-nowrap
              v-model="form.input.ref"
              :options="inputRefOptions"
            />
          </div>
        </div>
      </div>
    </a-form>
  </div>
</template>

<style>
#text-processor-node-info {
  .arco-textarea {
    @apply !text-xs;
  }
}
</style>
