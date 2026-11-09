<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch, inject } from 'vue'
import { useVueFlow } from '@vue-flow/core'
import { cloneDeep, debounce } from 'lodash'
import { type ValidatedError } from '@arco-design/web-vue'
import { getReferencedVariables } from '@/utils/helper'
import { useI18n } from 'vue-i18n'

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

type ConditionField = {
  variable_name: string
  operator: string
  compare_value: string
}

type IfElseNodeForm = {
  id: string
  type: string
  title: string
  description: string
  logical_operator: string
  conditions: ConditionField[]
  inputs: FormInputField[]
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
const { t } = useI18n()
const form = ref<IfElseNodeForm>({
  id: '',
  type: '',
  title: '',
  description: '',
  logical_operator: 'and',
  conditions: [],
  inputs: [],
})
const isSyncingForm = ref(false)

// 注入只读状态
const isReadonly = inject<boolean>('isReadonly', false)
const debounceAutoSave = debounce(() => {
  // 只读模式下不自动保存
  if (isReadonly) return
  void onSubmit({ errors: undefined })
}, 800)

// 运算符选项
const operatorOptions = [
  { label: t('workflowEditor.operators.equals'), value: 'equals' },
  { label: t('workflowEditor.operators.not_equals'), value: 'not_equals' },
  { label: t('workflowEditor.operators.contains'), value: 'contains' },
  { label: t('workflowEditor.operators.not_contains'), value: 'not_contains' },
  { label: t('workflowEditor.operators.starts_with'), value: 'starts_with' },
  { label: t('workflowEditor.operators.ends_with'), value: 'ends_with' },
  { label: t('workflowEditor.operators.is_empty'), value: 'is_empty' },
  { label: t('workflowEditor.operators.is_not_empty'), value: 'is_not_empty' },
  { label: t('workflowEditor.operators.greater_than'), value: 'greater_than' },
  { label: t('workflowEditor.operators.less_than'), value: 'less_than' },
  { label: t('workflowEditor.operators.greater_than_or_equal'), value: 'greater_than_or_equal' },
  { label: t('workflowEditor.operators.less_than_or_equal'), value: 'less_than_or_equal' },
]

// 逻辑运算符选项
const logicalOperatorOptions = [
  { label: t('workflowEditor.logicOptions.and'), value: 'and' },
  { label: t('workflowEditor.logicOptions.or'), value: 'or' },
]

// 节点可引用的变量选项
const inputRefOptions = computed(() => {
  return getReferencedVariables(cloneDeep(nodes.value), cloneDeep(edges.value), props.node.id)
})

// 添加输入字段
const addFormInputField = () => {
  form.value?.inputs.push({ name: '', type: 'string', content: '', ref: '' })
}

// 移除输入字段
const removeFormInputField = (idx: number) => {
  form.value?.inputs?.splice(idx, 1)
}

// 添加条件
const addCondition = () => {
  form.value?.conditions.push({
    variable_name: '',
    operator: 'equals',
    compare_value: '',
  })
}

// 移除条件
const removeCondition = (idx: number) => {
  form.value?.conditions?.splice(idx, 1)
}

// 表单提交函数
const onSubmit = async ({ errors }: { errors: Record<string, ValidatedError> | undefined }) => {
  if (errors) return

  const cloneInputs = cloneDeep(form.value.inputs)
  const cloneConditions = cloneDeep(form.value.conditions)

  emits('updateNode', {
    id: form.value.id,
    title: form.value.title,
    description: form.value.description,
    logical_operator: form.value.logical_operator,
    conditions: cloneConditions,
    inputs: cloneInputs.map((input: FormInputField) => {
      return {
        name: input.name,
        description: '',
        required: true,
        type: input.type === 'ref' ? 'string' : input.type,
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
    }),
    outputs: [{ name: 'result', type: 'boolean', value: { type: 'generated', content: false } }],
  })
}

// 监听数据，将数据映射到表单模型上
watch(
  () => props.node?.id,
  () => {
    const newNode = props.node
    if (!newNode?.id) return
    isSyncingForm.value = true
    debounceAutoSave.flush()
    debounceAutoSave.cancel()
    const cloneInputs = cloneDeep(newNode.data.inputs || [])
    const cloneConditions = cloneDeep(newNode.data.conditions || [])
    form.value = {
      id: newNode.id,
      type: newNode.type,
      title: newNode.data.title,
      description: newNode.data.description,
      logical_operator: newNode.data.logical_operator || 'and',
      conditions: cloneConditions,
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
    id="if-else-node-info"
    class="absolute top-0 right-0 bottom-0 w-[400px] border-l z-50 bg-white overflow-scroll scrollbar-w-none p-3"
  >
    <!-- 只读模式提示横幅 -->
    <div v-if="isReadonly" class="mb-3 p-3 bg-orange-50 border border-orange-200 rounded-lg">
      <div class="flex items-center gap-2 text-orange-700">
        <icon-lock class="flex-shrink-0" />
        <span class="text-sm font-medium">{{ t('workflowEditor.previewMode') }}</span>
      </div>
    </div>

    <div class="flex items-center justify-between gap-3 mb-2">
      <div class="flex items-center gap-1 flex-1">
        <a-avatar :size="30" shape="square" class="bg-amber-500 rounded-lg flex-shrink-0">
          <icon-branch />
        </a-avatar>
        <a-input
          v-model:model-value="form.title"
          :disabled="isReadonly" :placeholder="t('workflowEditor.titlePlaceholder')"
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
      :placeholder="t('workflowEditor.descriptionPlaceholder')"
    />

    <a-divider class="my-2" />

    <a-form size="mini" :model="form" :disabled="isReadonly" layout="vertical">
      <!-- 输入变量 -->
      <div class="flex flex-col gap-2 mb-3">
        <div class="flex items-center gap-2 text-gray-700 font-semibold">{{ t('workflowEditor.inputParameters') }}</div>
        <div class="flex items-center gap-1 text-xs text-gray-500 mb-2">
          <div class="w-[30%]">{{ t('workflowEditor.parameterName') }}</div>
          <div class="w-[24%]">{{ t('workflowEditor.parameterType') }}</div>
          <div class="w-[46%]">{{ t('workflowEditor.parameterValue') }}</div>
        </div>
        <div
          v-for="(input, idx) in form.inputs"
          :key="idx"
          class="flex items-center gap-1"
        >
          <div class="w-[30%] flex-shrink-0">
            <a-input v-model="input.name" size="mini" :placeholder="t('workflowEditor.parameterName')" class="!px-2" />
          </div>
          <div class="w-[24%] flex-shrink-0">
            <a-select
              size="mini"
              v-model="input.type"
              class="px-2"
              :options="[
                { label: t('workflowEditor.variableTypes.ref'), value: 'ref' },
                { label: t('workflowEditor.variableTypes.string'), value: 'string' },
                { label: t('workflowEditor.variableTypes.int'), value: 'int' },
                { label: t('workflowEditor.variableTypes.float'), value: 'float' },
                { label: t('workflowEditor.variableTypes.boolean'), value: 'boolean' },
              ]"
            />
          </div>
          <div class="w-[38%] flex-shrink-0">
            <a-input
              v-if="input.type !== 'ref'"
              size="mini"
              v-model="input.content"
              :placeholder="t('workflowEditor.parameterValue')"
            />
            <a-select
              v-else
              :placeholder="t('workflowEditor.selectReference')"
              size="mini"
              tag-nowrap
              v-model="input.ref"
              :options="inputRefOptions"
            />
          </div>
          <div class="w-[8%] flex-shrink-0">
            <a-button v-if="!isReadonly" type="text" size="mini" status="danger" @click="removeFormInputField(idx)">
              <icon-delete />
            </a-button>
          </div>
        </div>
        <a-button v-if="!isReadonly" type="dashed" size="mini" long @click="addFormInputField">
          <icon-plus />
          {{ t('workflowEditor.addField') }}
        </a-button>
      </div>

      <!-- 条件配置 -->
      <div class="flex flex-col gap-2 mb-3">
        <div class="flex items-center gap-2 text-gray-700 font-semibold">{{ t('workflowEditor.ifElse.title') }}</div>
        <div
          v-for="(condition, idx) in form.conditions"
          :key="idx"
          class="flex flex-col gap-2 p-2 bg-gray-50 rounded"
        >
          <div class="flex items-center gap-1">
            <a-input
              size="mini"
              v-model="condition.variable_name"
              :placeholder="t('workflowEditor.variableName')"
              class="flex-1"
            />
            <a-button v-if="!isReadonly" type="text" size="mini" status="danger" @click="removeCondition(idx)">
              <icon-delete />
            </a-button>
          </div>
          <a-select size="mini" v-model="condition.operator" :placeholder="t('workflowEditor.logic')">
            <a-option
              v-for="op in operatorOptions"
              :key="op.value"
              :value="op.value"
              :label="op.label"
            />
          </a-select>
          <a-input
            v-if="!['is_empty', 'is_not_empty'].includes(condition.operator)"
            size="mini"
            v-model="condition.compare_value"
            :placeholder="t('workflowEditor.parameterValue')"
          />
        </div>
        <a-button v-if="!isReadonly" type="dashed" size="mini" long @click="addCondition">
          <icon-plus />
          {{ t('workflowEditor.ifElse.addCondition') }}
        </a-button>
      </div>

      <!-- 逻辑运算符 -->
      <a-form-item v-if="form.conditions?.length > 1" field="logical_operator" :label="t('workflowEditor.logic')">
        <a-radio-group v-model="form.logical_operator" size="mini">
          <a-radio
            v-for="op in logicalOperatorOptions"
            :key="op.value"
            :value="op.value"
          >
            {{ op.label }}
          </a-radio>
        </a-radio-group>
      </a-form-item>
    </a-form>
  </div>
</template>

<style>
#if-else-node-info {
  .arco-textarea {
    @apply !text-xs;
  }
}
</style>
