<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch, inject } from 'vue'
import { useVueFlow } from '@vue-flow/core'
import { cloneDeep, debounce } from 'lodash'
import { type ValidatedError, Message } from '@arco-design/web-vue'
import { getReferencedVariables } from '@/utils/helper'
import { useI18n } from 'vue-i18n'

type OutputField = {
  name: string
  type: string
  required?: boolean
}

type ParameterExtractorInput = {
  name: string
  type: string
  content?: string
  ref: string
}

type ParameterExtractorNodeForm = {
  id: string
  type: string
  title: string
  description: string
  mode: string
  input: ParameterExtractorInput
  outputs: OutputField[]
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
const form = ref<ParameterExtractorNodeForm>({
  id: '',
  type: '',
  title: '',
  description: '',
  mode: 'auto',
  input: {
    name: 'text',
    type: 'string',
    content: '',
    ref: '',
  },
  outputs: [{ name: 'param', type: 'string', required: true }],
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

const addFormOutputField = () => {
  form.value?.outputs.push({ name: '', type: 'string', required: true })
  Message.success(t('workflowEditor.addExtractorFieldSuccess'))
}

const removeFormOutputField = (idx: number) => {
  if ((form.value?.outputs?.length ?? 0) <= 1) {
    Message.warning(t('workflowEditor.keepAtLeastOneExtractor'))
    return
  }
  form.value?.outputs?.splice(idx, 1)
}

const onSubmit = async ({ errors }: { errors: Record<string, ValidatedError> | undefined }) => {
  if (errors) return

  const input = form.value.input
  const outputs = cloneDeep(form.value.outputs)
  emits('updateNode', {
    id: form.value.id,
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
    outputs: outputs.map((output: OutputField) => {
      return {
        name: output.name,
        description: '',
        required: Boolean(output.required),
        type: output.type,
        value: {
          type: 'generated',
          content: variableDefaultValue(output.type),
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
      mode: newNode.data.mode || 'auto',
      input: {
        name: sourceInput?.name || 'text',
        type: sourceInput?.value?.type === 'ref' ? 'ref' : 'string',
        content: sourceInput?.value?.type === 'literal' ? sourceInput?.value?.content : '',
        ref,
      },
      outputs: cloneDeep(newNode.data.outputs ?? []).map((output: OutputField) => {
        return {
          name: output.name,
          type: output.type || 'string',
          required: output.required ?? true,
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
    id="parameter-extractor-node-info"
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
        <a-avatar :size="30" shape="square" class="bg-indigo-500 rounded-lg flex-shrink-0">
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
      <a-form-item field="mode" :label="t('workflowEditor.extractMode')">
        <a-select v-model="form.mode" size="mini">
          <a-option value="auto">{{ t('workflowEditor.extractModes.auto') }}</a-option>
          <a-option value="json">{{ t('workflowEditor.extractModes.json') }}</a-option>
          <a-option value="kv">{{ t('workflowEditor.extractModes.kv') }}</a-option>
        </a-select>
      </a-form-item>

      <div class="flex flex-col gap-2">
        <div class="flex items-center gap-2 text-gray-700 font-semibold">{{ t('workflowEditor.inputText') }}</div>
        <div class="flex items-center gap-1 text-xs text-gray-500 mb-2">
          <div class="w-[30%]">{{ t('workflowEditor.parameterName') }}</div>
          <div class="w-[24%]">{{ t('workflowEditor.parameterType') }}</div>
          <div class="w-[46%]">{{ t('workflowEditor.parameterValue') }}</div>
        </div>
        <div class="flex items-center gap-1">
          <div class="w-[30%] flex-shrink-0">
            <a-input v-model="form.input.name" size="mini" :placeholder="t('workflowEditor.parameterName')" class="!px-2" />
          </div>
          <div class="w-[24%] flex-shrink-0">
            <a-select
              size="mini"
              v-model="form.input.type"
              class="px-2"
              :options="[
                { label: t('workflowEditor.variableTypes.ref'), value: 'ref' },
                { label: t('workflowEditor.variableTypes.string'), value: 'string' },
              ]"
            />
          </div>
          <div class="w-[46%] flex-shrink-0">
            <a-input
              v-if="form.input.type !== 'ref'"
              size="mini"
              v-model="form.input.content"
              :placeholder="t('workflowEditor.inputText')"
            />
            <a-select
              v-else
              :placeholder="t('workflowEditor.selectReference')"
              size="mini"
              tag-nowrap
              v-model="form.input.ref"
              :options="inputRefOptions"
            />
          </div>
        </div>
      </div>

      <a-divider class="my-4" />

      <div class="flex flex-col gap-2">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2 text-gray-700 font-semibold">
            <div>{{ t('workflowEditor.parameterExtractor.fieldLabel') }}</div>
            <a-tooltip :content="t('workflowEditor.parameterExtractor.help')">
              <icon-question-circle />
            </a-tooltip>
          </div>
          <a-button v-if="!isReadonly" type="text" size="mini" class="!text-gray-700" @click="() => addFormOutputField()">
            <template #icon>
              <icon-plus />
            </template>
          </a-button>
        </div>
        <div class="flex items-center gap-1 text-xs text-gray-500 mb-2">
          <div class="w-[32%]">{{ t('workflowEditor.parameterName') }}</div>
          <div class="w-[30%]">{{ t('workflowEditor.parameterType') }}</div>
          <div class="w-[24%]">{{ t('workflowEditor.startNode.requiredLabel') }}</div>
          <div class="w-[14%]"></div>
        </div>
        <div v-for="(output, idx) in form?.outputs" :key="idx" class="flex items-center gap-1">
          <div class="w-[32%] flex-shrink-0">
            <a-input v-model="output.name" size="mini" :placeholder="t('workflowEditor.parameterName')" class="!px-2" />
          </div>
          <div class="w-[30%] flex-shrink-0">
            <a-select
              size="mini"
              v-model="output.type"
              class="px-2"
              :options="[
                { label: t('workflowEditor.variableTypes.string'), value: 'string' },
                { label: t('workflowEditor.variableTypes.int'), value: 'int' },
                { label: t('workflowEditor.variableTypes.float'), value: 'float' },
                { label: t('workflowEditor.variableTypes.boolean'), value: 'boolean' },
              ]"
            />
          </div>
          <div class="w-[24%] flex-shrink-0">
            <a-switch size="small" v-model="output.required" />
          </div>
          <div class="w-[14%] text-right">
            <icon-minus-circle
              v-if="!isReadonly" class="text-gray-500 hover:text-gray-700 cursor-pointer flex-shrink-0"
              @click="() => removeFormOutputField(idx as number)"
            />
          </div>
        </div>
      </div>
    </a-form>
  </div>
</template>

<style>
#parameter-extractor-node-info {
  .arco-select-option-content {
    @apply !text-xs;
  }
}
</style>
