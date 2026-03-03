<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { apiPrefix } from '@/config'
import { useGetLanguageModel, useGetLanguageModels } from '@/hooks/use-language-model'
import { useUpdateDraftAppConfig } from '@/hooks/use-app'

type ModelForm = {
  selectValue: string
  provider: string
  model: string
  parameters: Record<string, unknown>
  dialog_round: number
}

// 1.定义自定义组件所需数据
const props = defineProps({
  app_id: { type: String, default: '', required: true },
  model_config: {
    type: Object,
    default: () => {
      return {}
    },
    required: true,
  },
  dialog_round: { type: Number, default: 3, required: true },
})
const emits = defineEmits(['update:model_config'])
const form = ref<ModelForm>({
  selectValue: '',
  provider: '',
  model: '',
  parameters: {},
  dialog_round: 3,
})
const {
  loading: getLanguageModelLoading,
  language_model,
  loadLanguageModel,
} = useGetLanguageModel()
const { language_models, loadLanguageModels } = useGetLanguageModels()
const { handleUpdateDraftAppConfig } = useUpdateDraftAppConfig()
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

// 2.定义选择模型处理器
const changeModel = (value: string) => {
  // 2.1 使用/拆分出提供商+模型名字
  const [provider_name, model_name] = value.split('/')

  // 2.2 发起请求获取模型详情
  loadLanguageModel(provider_name, model_name).then(() => {
    // 2.3 重新赋值parameters
    form.value.parameters = language_model.value.parameters.reduce(
      (acc: Record<string, unknown>, parameter: { name: string; default?: unknown }) => {
        acc[parameter.name] = parameter.default ?? null
        return acc
      },
      {} as Record<string, unknown>,
    )
  })
}

// 3.触发器隐藏处理器，提交数据进行更新
const hideModelTrigger = () => {
  // 3.1 处理表单数据
  const [provider_name, model_name] = form.value.selectValue.split('/')

  // 3.2 提取表单模型配置
  const model_config = {
    provider: provider_name,
    model: model_name,
    parameters: form.value.parameters,
  }

  // 3.3 提交应用草稿配置更新
  handleUpdateDraftAppConfig(props.app_id, {
    model_config: model_config,
    dialog_round: form.value.dialog_round,
  }).then(() => emits('update:model_config', model_config))
}

watch(
  () => props.model_config,
  (newValue) => {
    // 1.完成表单数据初始化
    form.value.selectValue = `${newValue?.provider}/${newValue.model}`
    form.value.provider = String(newValue?.provider || '')
    form.value.model = String(newValue?.model || '')
    form.value.parameters = (newValue?.parameters || {}) as Record<string, unknown>

    // 2.请求语言模型详情API接口
    newValue?.provider && loadLanguageModel(String(newValue?.provider), String(newValue?.model))
  },
  { immediate: true },
)

watch(
  () => props.dialog_round,
  (newValue) => {
    form.value.dialog_round = Number(newValue)
  },
  { immediate: true },
)

onMounted(() => {
  loadLanguageModels()
})
</script>

<template>
  <a-trigger
    v-if="props.model_config?.provider"
    trigger="click"
    position="bl"
    :popup-translate="[0, 12]"
    @hide="hideModelTrigger"
  >
    <div class="flex items-center gap-1 cursor-pointer hover:bg-gray-100 px-1.5 py-1 rounded-lg">
      <a-avatar
        :size="16"
        shape="square"
        :image-url="`${apiPrefix}/language-models/${form?.provider}/icon`"
      />
      <div class="text-gray-700 text-xs">{{ form?.model }}</div>
      <icon-down />
    </div>
    <template #content>
      <div class="bg-white px-6 py-5 shadow rounded-lg w-[460px]">
        <!-- 标题 -->
        <div class="text-gray-700 text-base font-semibold mb-3">模型设置</div>
        <!-- 模型选择 -->
        <div class="flex flex-col gap-2 mb-2">
          <div class="text-gray-700">模型</div>
          <a-select
            v-model:model-value="form.selectValue"
            :options="modelOptions"
            size="small"
            class="rounded-lg mb-2"
            placeholder="请选择Agent使用的大语言模型"
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
        <!-- 参数列表 -->
        <div class="text-gray-700 mb-2">参数</div>
        <a-spin :loading="getLanguageModelLoading" class="w-full">
          <div
            v-for="parameter in language_model?.parameters"
            :key="parameter.name"
            class="flex items-center gap-2 h-8 mb-4"
          >
            <!-- 字段标签 -->
            <div class="flex items-center gap-2 text-gray-500 w-[120px] flex-shrink-0">
              <div class="text-xs">{{ parameter?.label }}</div>
              <a-tooltip :content="parameter?.help">
                <icon-question-circle />
              </a-tooltip>
            </div>
            <!-- 字段输入框 -->
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
        <!-- 携带上下文轮数 -->
        <div class="text-gray-700 mb-2">输入及输出设置</div>
        <div class="flex items-center gap-2 h-8">
          <!-- 字段标签 -->
          <div class="flex items-center gap-2 text-gray-500 w-[120px] flex-shrink-0">
            <div class="text-xs">携带上下文轮数</div>
            <a-tooltip content="每次向Agent提问时需要携带的最近消息对话轮数，默认为3。">
              <icon-question-circle />
            </a-tooltip>
          </div>
          <!-- 滑动输入框 -->
          <a-slider
            v-model:model-value="form.dialog_round"
            :default-value="3"
            show-input
            :min="0"
            :max="10"
            :step="1"
          />
        </div>
      </div>
    </template>
  </a-trigger>
</template>

<style scoped></style>
