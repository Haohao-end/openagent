<script setup lang="ts">
import { cloneDeep, isEqual } from 'lodash'
import { nextTick, ref, watch } from 'vue'
import { useUpdateDraftAppConfig } from '@/hooks/use-app'

type ReviewConfig = {
  enable: boolean
  keywords: string[]
  inputs_config: {
    enable: boolean
    preset_response: string
  }
  outputs_config: {
    enable: boolean
  }
}

type ReviewConfigForm = {
  enable: boolean
  keywords: string
  inputs_config: {
    enable: boolean
    preset_response: string
  }
  outputs_config: {
    enable: boolean
  }
}

// 1.定义自定义组件所需数据
const props = defineProps({
  app_id: { type: String, default: '', required: true },
  review_config: {
    type: Object,
    default: () => {
      return {}
    },
    required: true,
  },
})
const { loading, handleUpdateDraftAppConfig } = useUpdateDraftAppConfig()
const isInit = ref(false)
const reviewConfigModalVisible = ref(false)
const reviewConfigForm = ref<ReviewConfigForm>({
  enable: Boolean(props.review_config?.enable),
  keywords: String(props.review_config?.keywords?.join('\n') || ''),
  inputs_config: {
    enable: Boolean(props.review_config?.inputs_config?.enable),
    preset_response: String(props.review_config?.inputs_config?.preset_response || ''),
  },
  outputs_config: {
    enable: Boolean(props.review_config?.outputs_config?.enable),
  },
})
const originReviewConfigForm = ref({ ...cloneDeep(reviewConfigForm.value) })

// 2.定义检查表单修改函数
const isFormModified = () => {
  return isEqual(originReviewConfigForm.value, reviewConfigForm.value)
}

// 3.隐藏审核配置模态窗处理器
const handleCancelReviewConfigModal = () => {
  // 3.1 隐藏模态窗
  reviewConfigModalVisible.value = false

  // 3.2 还原表单数据
  reviewConfigForm.value = cloneDeep(originReviewConfigForm.value)
}

// 4.提交审核配置模态窗存储的内容
const handleSubmitReviewConfig = async () => {
  // 4.1 处理数据并完成API接口提交
  await handleUpdateDraftAppConfig(props.app_id, {
    review_config: {
      enable: reviewConfigForm.value.enable,
      keywords: reviewConfigForm.value.keywords
        .split(/\r?\n/)
        .filter((item: string) => item.trim() !== ''),
      inputs_config: reviewConfigForm.value.inputs_config,
      outputs_config: reviewConfigForm.value.outputs_config,
    },
  })

  // 4.2 接口更新更新成功，同步表单信息
  originReviewConfigForm.value = cloneDeep(reviewConfigForm.value)
  await nextTick()

  // 4.3 隐藏模态窗
  handleCancelReviewConfigModal()
}

// 5.监听review_config变化并同步到表单
watch(
  () => props.review_config,
  (newValue: unknown) => {
    const currentConfig = newValue as ReviewConfig
    // 5.1 检测数据是否更新并且未初始化
    if (!isInit.value || !isFormModified()) {
      if (currentConfig && Object.keys(currentConfig).length > 0) {
        // 5.2 更新表单数据和备份数据，使用深拷贝
        reviewConfigForm.value = cloneDeep({
          enable: Boolean(currentConfig.enable),
          keywords: (currentConfig.keywords || []).join('\n'),
          inputs_config: {
            enable: Boolean(currentConfig.inputs_config?.enable),
            preset_response: String(currentConfig.inputs_config?.preset_response || ''),
          },
          outputs_config: {
            enable: Boolean(currentConfig.outputs_config?.enable),
          },
        })
        originReviewConfigForm.value = cloneDeep(reviewConfigForm.value)

        // 5.3 标记为已初始化
        isInit.value = true
      }
    }
  },
  { immediate: true, deep: true },
)
</script>

<template>
  <div class="">
    <a-collapse-item key="review_config" class="app-ability-item review-config-ability-item">
      <template #header>
        <div class="text-gray-700 font-bold">内容审查</div>
      </template>
      <template #extra>
        <a-dropdown
          @select="
            async (value: string | number | boolean) => {
              if (Boolean(value) !== reviewConfigForm.enable) {
                const previousEnable = reviewConfigForm.enable
                try {
                  // 1.表盖表单数据并确保数据同步
                  reviewConfigForm.enable = Boolean(value)
                  await nextTick()

                  // 2.提交表单更新数据
                  await handleSubmitReviewConfig()
                } catch (_error: unknown) {
                  reviewConfigForm.enable = previousEnable
                }
              }
            }
          "
        >
          <a-button size="mini" class="rounded-lg flex items-center gap-1 px-1" @click.stop>
            {{ reviewConfigForm.enable ? '开启' : '关闭' }}
            <icon-down />
          </a-button>
          <template #content>
            <a-doption :value="1" class="text-xs py-1.5 text-gray-700">开启</a-doption>
            <a-doption :value="0" class="text-xs py-1.5 text-red-700">关闭</a-doption>
          </template>
        </a-dropdown>
      </template>
      <div class="group py-2">
        <div class="text-xs text-gray-500 leading-[22px] group-hover:hidden">
          对用户输入以及大语言模型输出内容进行审查。
        </div>
        <a-button
          size="small"
          long
          class="hidden group-hover:block rounded-lg transition-all"
          @click="reviewConfigModalVisible = true"
        >
          <template #icon>
            <icon-settings />
          </template>
          设置
        </a-button>
      </div>
    </a-collapse-item>
    <!-- 模态窗组件 -->
    <a-modal
      :visible="reviewConfigModalVisible"
      hide-title
      :footer="false"
      modal-class="rounded-xl"
      @cancel="handleCancelReviewConfigModal"
    >
      <!-- 顶部标题 -->
      <div class="flex items-center justify-between">
        <div class="text-lg font-bold text-gray-700">内容审核</div>
        <a-button
          type="text"
          class="!text-gray-700"
          size="small"
          @click="handleCancelReviewConfigModal"
        >
          <template #icon>
            <icon-close />
          </template>
        </a-button>
      </div>
      <!-- 中间表单 -->
      <div class="py-4">
        <div class="flex flex-col gap-5">
          <!-- 关键词 -->
          <div class="flex flex-col gap-2">
            <div class="flex flex-col">
              <div class="flex items-center gap-1 text-gray-700">
                关键词
                <div class="text-red-700">*</div>
              </div>
              <div class="text-gray-500 text-xs">每行一个，用换行符分割，最多填写100个关键词</div>
            </div>
            <a-textarea
              v-model:model-value="reviewConfigForm.keywords"
              class="bg-white rounded-lg border border-gray-200"
              placeholder="每行一个，用换行符分隔。"
              :max-length="100"
              show-word-limit
              :auto-size="{ minRows: 4, maxRows: 4 }"
              :word-length="
                (value) => {
                  if (value.trim() === '') return 0
                  return value.split(/\r?\n/).length
                }
              "
              :word-slice="
                (value, maxLength) => {
                  // 1.分割内容并截取前100个关键词
                  const lines = value.split(/\r?\n/)
                  const first100Lines = lines.slice(0, maxLength)

                  // 2.拼接换行符后返回
                  return first100Lines.join('\n')
                }
              "
            />
          </div>
          <!-- 输入审核 -->
          <div class="flex flex-col gap-2 p-3 bg-gray-50 border border-gray-200 rounded-lg">
            <div class="flex items-center justify-between">
              <div class="text-gray-700">输入审查内容</div>
              <a-switch
                v-model:model-value="reviewConfigForm.inputs_config.enable"
                size="small"
                type="round"
              />
            </div>
            <div class="flex flex-col gap-2">
              <div class="text-gray-700 text-xs">预设回复</div>
              <a-textarea
                v-model:model-value="reviewConfigForm.inputs_config.preset_response"
                placeholder="这里是预设回复内容"
                class="bg-white rounded-lg border border-gray-200"
                :auto-size="{ minRows: 3, maxRows: 3 }"
              />
            </div>
          </div>
          <!-- 输出审核 -->
          <div class="flex flex-col p-3 bg-gray-50 border border-gray-200 rounded-lg">
            <div class="flex items-center justify-between">
              <div class="text-gray-700">输出审查内容</div>
              <a-switch
                v-model:model-value="reviewConfigForm.outputs_config.enable"
                size="small"
                type="round"
              />
            </div>
          </div>
        </div>
      </div>
      <!-- 底部按钮 -->
      <div class="flex items-center justify-between">
        <div class=""></div>
        <a-space :size="16">
          <a-button class="rounded-lg" @click="handleCancelReviewConfigModal">取消</a-button>
          <a-button
            :loading="loading"
            type="primary"
            class="rounded-lg"
            @click="handleSubmitReviewConfig"
          >
            保存
          </a-button>
        </a-space>
      </div>
    </a-modal>
  </div>
</template>

<style>
.review-config-ability-item {
  .arco-collapse-item-content-box {
    @apply p-0;
  }
}
</style>
