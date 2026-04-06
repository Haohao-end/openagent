<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { apiPrefix } from '@/config'
import { useGetLanguageModel, useGetLanguageModels } from '@/hooks/use-language-model'

type ModelForm = {
  selectValue: string
  provider: string
  model: string
  parameters: Record<string, unknown>
}

const props = defineProps({
  model_config: {
    type: Object,
    default: () => ({}),
    required: true,
  },
})
const emits = defineEmits(['update:model_config'])
const popupVisible = ref(false)
const form = ref<ModelForm>({
  selectValue: '',
  provider: '',
  model: '',
  parameters: {},
})
const {
  loading: getLanguageModelLoading,
  language_model,
  loadLanguageModel,
} = useGetLanguageModel()
const { language_models, loadLanguageModels } = useGetLanguageModels()
const modelOptions = computed(() => {
  return language_models.value.map((language_model) => {
    return {
      isGroup: true,
      label: language_model.label,
      options: language_model.models.map((model) => {
        return {
          label: model.label,
          value: `${language_model.name}/${model.model_name}`,
        }
      }),
    }
  })
})

const syncFormFromProps = (value: Record<string, any>) => {
  form.value.selectValue = value?.provider && value?.model ? `${value.provider}/${value.model}` : ''
  form.value.provider = String(value?.provider || '')
  form.value.model = String(value?.model || '')
  form.value.parameters = (value?.parameters || {}) as Record<string, unknown>
}

const changeModel = (value: string) => {
  const [provider_name, model_name] = value.split('/')

  loadLanguageModel(provider_name, model_name).then(() => {
    form.value.provider = provider_name
    form.value.model = model_name
    form.value.parameters = language_model.value.parameters.reduce(
      (acc: Record<string, unknown>, parameter: { name: string; default?: unknown }) => {
        acc[parameter.name] = parameter.default ?? null
        return acc
      },
      {} as Record<string, unknown>,
    )
  })
}

const handleApply = () => {
  const [provider_name, model_name] = form.value.selectValue.split('/')
  if (!provider_name || !model_name) return

  emits('update:model_config', {
    provider: provider_name,
    model: model_name,
    parameters: form.value.parameters,
  })
  popupVisible.value = false
}

watch(
  () => props.model_config,
  (newValue) => {
    syncFormFromProps((newValue || {}) as Record<string, any>)
    if (newValue?.provider && newValue?.model) {
      void loadLanguageModel(String(newValue.provider), String(newValue.model))
    }
  },
  { immediate: true },
)

watch(popupVisible, (visible) => {
  if (!visible) return
  syncFormFromProps((props.model_config || {}) as Record<string, any>)
  if (props.model_config?.provider && props.model_config?.model) {
    void loadLanguageModel(String(props.model_config.provider), String(props.model_config.model))
  }
})

onMounted(() => {
  void loadLanguageModels()
})
</script>

<template>
  <a-trigger
    v-model:popup-visible="popupVisible"
    trigger="click"
    position="bl"
    :popup-translate="[0, 12]"
  >
    <div class="flex items-center gap-1 cursor-pointer hover:bg-gray-100 px-1.5 py-1 rounded-lg">
      <a-avatar
        v-if="form.provider"
        :size="16"
        shape="square"
        :image-url="`${apiPrefix}/language-models/${form.provider}/icon`"
      />
      <icon-robot v-else />
      <div class="text-gray-700 text-xs">{{ form.model || '未配置模型' }}</div>
      <icon-down />
    </div>
    <template #content>
      <div class="bg-white px-6 py-5 shadow rounded-lg w-[460px]">
        <div class="text-gray-700 text-base font-semibold mb-3">对比模型</div>
        <div class="flex flex-col gap-2 mb-2">
          <div class="text-gray-700">模型</div>
          <a-select
            v-model:model-value="form.selectValue"
            :options="modelOptions"
            size="small"
            class="rounded-lg mb-2"
            placeholder="请选择用于对比的大语言模型"
            @change="changeModel"
          >
            <template #label="{ data }">
              <div class="flex items-center gap-2">
                <a-avatar
                  :size="16"
                  shape="square"
                  :image-url="`${apiPrefix}/language-models/${data.value.split('/')[0]}/icon`"
                />
                <a-space :size="4">
                  <div class="text-xs text-gray-700">{{ data.value.split('/')[0] }}</div>
                  <div class="text-xs text-gray-500">·</div>
                  <div class="text-xs text-gray-700">{{ data.value.split('/')[1] }}</div>
                </a-space>
              </div>
            </template>
            <template #option="{ data }">
              <div class="flex items-center gap-2">
                <a-avatar
                  :size="16"
                  shape="square"
                  :image-url="`${apiPrefix}/language-models/${data.value.split('/')[0]}/icon`"
                />
                <div class="text-xs text-gray-700 py-2">{{ data.label }}</div>
              </div>
            </template>
          </a-select>
        </div>

        <div class="text-gray-700 mb-2">参数</div>
        <a-spin :loading="getLanguageModelLoading" class="w-full">
          <div
            v-for="parameter in language_model?.parameters"
            :key="parameter.name"
            class="flex items-center gap-2 h-8 mb-4"
          >
            <div class="flex items-center gap-2 text-gray-500 w-[120px] flex-shrink-0">
              <div class="text-xs">{{ parameter?.label }}</div>
              <a-tooltip :content="parameter?.help">
                <icon-question-circle />
              </a-tooltip>
            </div>
            <template v-if="parameter?.options?.length > 0">
              <a-select
                v-model:model-value="form.parameters[parameter.name]"
                :default-value="parameter.default"
                placeholder="请选择参数值"
                :options="parameter.options"
              />
            </template>
            <template v-else-if="parameter.type === 'boolean'">
              <a-select
                v-model:model-value="form.parameters[parameter.name]"
                :default-value="parameter.default"
                placeholder="请选择参数值"
                :options="[
                  { label: '是', value: true },
                  { label: '否', value: false },
                ]"
              />
            </template>
            <template v-else-if="['int', 'float'].includes(parameter.type)">
              <a-slider
                v-model:model-value="form.parameters[parameter.name]"
                :default-value="parameter.default"
                :min="parameter?.min"
                :max="parameter?.max"
                :step="parameter?.type === 'float' ? 0.1 : 1"
                show-input
              />
            </template>
            <template v-else-if="parameter.type === 'string'">
              <a-input
                v-model:model-value="form.parameters[parameter.name]"
                :default-value="parameter.default"
                placeholder="请输入参数值"
              />
            </template>
          </div>
        </a-spin>

        <div class="flex justify-end gap-2 pt-2">
          <a-button class="rounded-lg" @click="popupVisible = false">取消</a-button>
          <a-button type="primary" class="rounded-lg" @click="handleApply">应用模型</a-button>
        </div>
      </div>
    </template>
  </a-trigger>
</template>
