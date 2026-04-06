<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch, inject } from 'vue'
import { useVueFlow } from '@vue-flow/core'
import { cloneDeep, debounce } from 'lodash'
import { type ValidatedError, Message } from '@arco-design/web-vue'
import { getReferencedVariables } from '@/utils/helper'

type NodeInputField = {
  name: string
  type: string
  value: {
    type: string
    content: {
      ref_node_id: string
      ref_var_name: string
    }
  }
}

type FormInputField = {
  name: string
  type: string
  ref: string
  content?: unknown
}

type VariableAssignerNodeForm = {
  id: string
  type: string
  title: string
  description: string
  inputs: FormInputField[]
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
const form = ref<VariableAssignerNodeForm>({
  id: '',
  type: '',
  title: '',
  description: '',
  inputs: [],
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

const variableDefaultValue = (type: string) => {
  if (type === 'int') return 0
  if (type === 'float') return 0
  if (type === 'boolean') return false
  return ''
}

const addFormInputField = () => {
  form.value?.inputs.push({ name: '', type: 'string', content: '', ref: '' })
  Message.success('新增变量成功')
}

const removeFormInputField = (idx: number) => {
  form.value?.inputs?.splice(idx, 1)
}

const onSubmit = async ({ errors }: { errors: Record<string, ValidatedError> | undefined }) => {
  if (errors) return

  const cloneInputs = cloneDeep(form.value.inputs)
  const normalizedInputs = cloneInputs.map((input: FormInputField) => {
    const normalizedType = input.type === 'ref' ? 'string' : input.type
    return {
      name: input.name,
      description: '',
      required: true,
      type: normalizedType,
      value: {
        type: input.type === 'ref' ? 'ref' : 'literal',
        content:
          input.type === 'ref'
            ? {
                ref_node_id: input.ref.split('/', 2)[0] || '',
                ref_var_name: input.ref.split('/', 2)[1] || '',
              }
            : input.content,
      },
      meta: {},
    }
  })

  emits('updateNode', {
    id: props.node.id,
    title: form.value.title,
    description: form.value.description,
    inputs: normalizedInputs,
    outputs: normalizedInputs.map((input: { name: string; type: string }) => {
      return {
        name: input.name,
        description: '',
        required: true,
        type: input.type,
        value: {
          type: 'generated',
          content: variableDefaultValue(input.type),
        },
        meta: {},
      }
    }),
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
    const cloneInputs = cloneDeep(newNode.data.inputs)
    form.value = {
      id: newNode.id,
      type: newNode.type,
      title: newNode.data.title,
      description: newNode.data.description,
      inputs: cloneInputs.map((input: NodeInputField) => {
        const ref =
          input.value.type === 'ref'
            ? `${input.value.content.ref_node_id}/${input.value.content.ref_var_name}`
            : ''

        let refExists = false
        if (input.value.type === 'ref') {
          for (const inputRefOption of inputRefOptions.value) {
            for (const option of inputRefOption.options) {
              if (option.value === ref) {
                refExists = true
                break
              }
            }
          }
        }

        return {
          name: input.name,
          type: input.value.type === 'literal' ? input.type : 'ref',
          content: input.value.type === 'literal' ? input.value.content : '',
          ref: input.value.type === 'ref' && refExists ? ref : '',
        }
      }),
      outputs: cloneDeep(newNode.data.outputs ?? []),
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
    id="variable-assigner-node-info"
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
        <a-avatar :size="30" shape="square" class="bg-lime-600 rounded-lg flex-shrink-0">
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
      <div class="flex flex-col gap-2">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2 text-gray-700 font-semibold">
            <div>赋值变量</div>
            <a-tooltip content="定义变量和值，供后续节点引用。值支持字面量或引用上游变量。">
              <icon-question-circle />
            </a-tooltip>
          </div>
          <a-button v-if="!isReadonly" type="text" size="mini" class="!text-gray-700" @click="() => addFormInputField()">
            <template #icon>
              <icon-plus />
            </template>
          </a-button>
        </div>
        <div class="flex items-center gap-1 text-xs text-gray-500 mb-2">
          <div class="w-[20%]">变量名</div>
          <div class="w-[25%]">类型</div>
          <div class="w-[47%]">值</div>
          <div class="w-[8%]"></div>
        </div>
        <div v-for="(input, idx) in form?.inputs" :key="idx" class="flex items-center gap-1">
          <div class="w-[20%] flex-shrink-0">
            <a-input v-model="input.name" size="mini" placeholder="请输入变量名" class="!px-2" />
          </div>
          <div class="w-[25%] flex-shrink-0">
            <a-select
              size="mini"
              v-model="input.type"
              class="px-2"
              :options="[
                { label: '引用', value: 'ref' },
                { label: 'STRING', value: 'string' },
                { label: 'INT', value: 'int' },
                { label: 'FLOAT', value: 'float' },
                { label: 'BOOLEAN', value: 'boolean' },
              ]"
            />
          </div>
          <div class="w-[47%] flex-shrink-0 flex items-center gap-1">
            <a-input
              v-if="input.type !== 'ref'"
              size="mini"
              v-model="input.content"
              placeholder="请输入变量值"
            />
            <a-select
              v-else
              placeholder="请选择引用变量"
              size="mini"
              tag-nowrap
              v-model="input.ref"
              :options="inputRefOptions"
            />
          </div>
          <div class="w-[8%] text-right">
            <icon-minus-circle
              v-if="!isReadonly" class="text-gray-500 hover:text-gray-700 cursor-pointer flex-shrink-0"
              @click="() => removeFormInputField(idx as number)"
            />
          </div>
        </div>
        <a-empty v-if="form?.inputs.length <= 0" class="my-4">该节点暂无变量</a-empty>
      </div>

      <a-divider class="my-4" />

      <div class="flex flex-col gap-2">
        <div class="font-semibold text-gray-700">输出数据</div>
        <div class="text-gray-500 text-xs">输出会自动与赋值变量保持一致</div>
        <div v-for="(output, idx) in form?.outputs" :key="idx" class="flex items-center gap-2">
          <div class="text-gray-700">{{ output.name }}</div>
          <div class="text-gray-500 bg-gray-200 px-1 py-0.5 rounded">{{ output.type }}</div>
        </div>
      </div>
    </a-form>
  </div>
</template>

<style>
#variable-assigner-node-info {
  .arco-select-option-content {
    @apply !text-xs;
  }
}
</style>
