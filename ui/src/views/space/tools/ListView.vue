<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  useCreateApiToolProvider,
  useDeleteApiToolProvider,
  useGenerateIconPreview,
  useGetApiToolProvider,
  useGetApiToolProvidersWithPage,
  useRegenerateIcon,
  useUpdateApiToolProvider,
  useValidateOpenAPISchema,
} from '@/hooks/use-tool'
import { useUploadImage } from '@/hooks/use-upload-file'
import { type CreateApiToolProviderRequest } from '@/models/api-tool'
import { useAccountStore } from '@/stores/account'
import { openapiSchemaAssistantChat } from '@/services/ai'
import moment from 'moment/moment'
import { typeMap } from '@/config'
import { type FileItem, Form, type ValidatedError, Message } from '@arco-design/web-vue'
import IconUploadGenerator from '@/components/IconUploadGenerator.vue'
import { getUserAvatarUrl } from '@/utils/helper'
import { getErrorMessage } from '@/utils/error'
import { useI18n } from 'vue-i18n'

type HeaderItem = {
  key: string
  value: string
}

type ApiToolProviderFormValues = {
  fileList: FileItem[]
  icon: string
  name: string
  openapi_schema: string
  headers: HeaderItem[]
}

type OpenapiToolPreview = {
  name: string
  description: string
  method: string
  path: string
}

// 1.定义额面所需数据
const route = useRoute()
const { t } = useI18n()
const router = useRouter()
const accountStore = useAccountStore()
const form = ref<{
  fileList: FileItem[]
  icon: string
  name: string
  openapi_schema: string
  headers: HeaderItem[]
}>({
  fileList: [],
  icon: '',
  name: '',
  openapi_schema: '',
  headers: [],
})
const { image_url, handleUploadImage } = useUploadImage()
const {
  loading: getApiToolProviderLoading,
  api_tool_provider,
  loadApiToolProvider,
} = useGetApiToolProvider()
const {
  loading: getApiToolProvidersLoading,
  paginator,
  api_tool_providers,
  loadApiToolProviders,
} = useGetApiToolProvidersWithPage()
const { handleDelete: handleDeleteApiToolProvider } = useDeleteApiToolProvider()
const {
  loading: updateApiToolProviderLoading,
  handleUpdateApiToolProvider, //
} = useUpdateApiToolProvider()
const {
  loading: createApiToolProviderLoading,
  handleCreateApiToolProvider, //
} = useCreateApiToolProvider()
const { handleValidateOpenAPISchema } = useValidateOpenAPISchema()
const { loading: regenerateIconLoading, handleRegenerateIcon } = useRegenerateIcon()
const { loading: generateIconPreviewLoading, handleGenerateIconPreview } = useGenerateIconPreview()
const formRef = ref<InstanceType<typeof Form>>()
const showIdx = ref<number>(-1)
const loading = ref<boolean>(false)
const showCreateModal = ref<boolean>(false)
const showUpdateModal = ref<boolean>(false)
const showOpenapiSchemaExampleModal = ref<boolean>(false)
const openapiAssistantQuestion = ref<string>('')
const openapiAssistantContent = ref<string>('')
const openapiAssistantLoading = ref<boolean>(false)
let iconUploadRequestId = 0
let providerEditRequestId = 0
let openapiAssistantRequestId = 0
let providerListRequestId = 0
let isUnmounted = false
let openapiAssistantAbortController: AbortController | undefined

const handleLoadApiToolProviders = async (init: boolean, searchWord: string = '') => {
  const requestId = ++providerListRequestId
  try {
    await loadApiToolProviders(init, searchWord)
  } catch (error) {
    if (!isUnmounted && requestId === providerListRequestId) {
      Message.error(getErrorMessage(error, t('space.tools.loadFailed')))
    }
  }
}

const cancelOpenapiSchemaAssistant = () => {
  openapiAssistantRequestId += 1
  openapiAssistantAbortController?.abort()
  openapiAssistantAbortController = undefined
  openapiAssistantLoading.value = false
}

onBeforeUnmount(() => {
  isUnmounted = true
  iconUploadRequestId += 1
  providerEditRequestId += 1
  cancelOpenapiSchemaAssistant()
})

const clearCreateTypeQuery = async () => {
  const nextQuery = { ...route.query }
  delete nextQuery.create_type
  await router.replace({
    path: route.path,
    query: nextQuery,
  })
}

// 定义上传图标处理器
const handleUploadIcon = async (file: File) => {
  const requestId = ++iconUploadRequestId
  await handleUploadImage(file)
  if (requestId !== iconUploadRequestId) return
  form.value.icon = image_url.value
  form.value.fileList = [{ uid: '1', name: t('space.tools.iconPlaceholder'), url: image_url.value }]
  Message.success(t('space.tools.iconUploadSuccess'))
}

// 定义生成图标处理器
const handleGenerateIcon = async () => {
  if (!form.value.name || form.value.name.trim() === '') {
    Message.warning(t('space.tools.enterNameFirst'))
    return
  }

  const requestId = ++iconUploadRequestId
  try {
    // 更新模式：调用 regenerateIcon
    if (showUpdateModal.value) {
      const provider_id = api_tool_providers.value[showIdx.value]['id']
      const iconUrl = await handleRegenerateIcon(
        provider_id,
        () => requestId === iconUploadRequestId,
      )
      if (requestId !== iconUploadRequestId) return
      if (iconUrl) {
        form.value.icon = iconUrl
        form.value.fileList = [{ uid: '1', name: t('space.tools.iconPlaceholder'), url: iconUrl }]
        Message.success(t('space.tools.iconGenerateSuccess'))
      }
    }
    // 创建模式：调用 generateIconPreview
    else {
      const iconUrl = await handleGenerateIconPreview(
        form.value.name,
        '',
        () => requestId === iconUploadRequestId,
      )
      if (requestId !== iconUploadRequestId) return
      if (iconUrl) {
        form.value.icon = iconUrl
        form.value.fileList = [{ uid: '1', name: t('space.tools.iconPlaceholder'), url: iconUrl }]
        Message.success(t('space.tools.iconGenerateSuccess'))
      }
    }
  } catch (_error: unknown) {
    // 错误已在 hooks 中处理
  }
}

const openapiSchemaInputExample = `{
  "server": "https://api.weather-service.com/v1",
  "description": "Provides global real-time weather and forecast APIs",
  "paths": {
    "/current": {
      "get": {
        "description": "Get current weather for a city",
        "operationId": "getCurrentWeather",
        "parameters": [
          {
            "name": "city",
            "in": "query",
            "description": "City name, for example: Beijing",
            "required": true,
            "type": "str"
          },
          {
            "name": "units",
            "in": "query",
            "description": "Temperature unit (metric/imperial), default metric",
            "required": false,
            "type": "str"
          },
          {
            "name": "lang",
            "in": "query",
            "description": "Response language (zh/en), default en",
            "required": false,
            "type": "str"
          }
        ]
      }
    },
    "/forecast": {
      "get": {
        "description": "Get the 7-day forecast for a city",
        "operationId": "getWeatherForecast",
        "parameters": [
          {
            "name": "city",
            "in": "query",
            "description": "City name, for example: Shanghai",
            "required": true,
            "type": "str"
          },
          {
            "name": "days",
            "in": "query",
            "description": "Forecast days (1-14), default 7",
            "required": false,
            "type": "int"
          },
          {
            "name": "units",
            "in": "query",
            "description": "Temperature unit (metric/imperial), default metric",
            "required": false,
            "type": "str"
          }
        ]
      }
    }
  }
}`

const extractOpenapiSchemaJson = (content: string): string => {
  const fenceResult = content.match(/```(?:json)?\s*([\s\S]*?)```/i)
  const normalized = (fenceResult?.[1] ?? content).trim()
  const firstBrace = normalized.indexOf('{')
  const lastBrace = normalized.lastIndexOf('}')

  if (firstBrace !== -1 && lastBrace > firstBrace) {
    return normalized.slice(firstBrace, lastBrace + 1)
  }

  return normalized
}

const handleUseOpenapiSchemaExample = async () => {
  form.value.openapi_schema = openapiSchemaInputExample
  const isValid = await handleValidateOpenAPISchema(form.value.openapi_schema)
  if (!isValid) return
  showOpenapiSchemaExampleModal.value = false
  Message.success(t('space.tools.aiFilled'))
}

const toggleOpenapiSchemaExampleModal = () => {
  showOpenapiSchemaExampleModal.value = !showOpenapiSchemaExampleModal.value
}

const handleGenerateOpenapiSchemaByAI = async () => {
  const question = openapiAssistantQuestion.value.trim()
  if (!question) {
    Message.warning(t('space.tools.aiDescriptionRequired'))
    return
  }

  cancelOpenapiSchemaAssistant()
  const requestId = openapiAssistantRequestId
  const abortController = new AbortController()
  openapiAssistantAbortController = abortController
  openapiAssistantLoading.value = true
  openapiAssistantContent.value = ''

  try {
    const response = await openapiSchemaAssistantChat(question, (eventResponse) => {
      if (requestId !== openapiAssistantRequestId) return
      const content = String(eventResponse?.data?.content ?? '')
      if (!content) return
      openapiAssistantContent.value += content
    }, abortController.signal)

    if (requestId !== openapiAssistantRequestId) return

    if (response && typeof response === 'object' && 'code' in response) {
      throw new Error(String((response as { message?: string }).message || t('space.tools.aiFillFailed')))
    }

    const schemaText = extractOpenapiSchemaJson(openapiAssistantContent.value)
    const schemaObject = JSON.parse(schemaText)
    form.value.openapi_schema = JSON.stringify(schemaObject, null, 2)

    const isValid = await handleValidateOpenAPISchema(form.value.openapi_schema)
    if (requestId !== openapiAssistantRequestId) return
    if (!isValid) return
    Message.success(t('space.tools.aiFilled'))
  } catch (_error: unknown) {
    if (requestId === openapiAssistantRequestId) {
      Message.error(t('space.tools.aiFillFailed'))
    }
  } finally {
    if (requestId === openapiAssistantRequestId) {
      openapiAssistantLoading.value = false
      openapiAssistantAbortController = undefined
    }
  }
}
const tools = computed(() => {
  try {
    // 1.解析openapi_schema数据
    const available_tools: OpenapiToolPreview[] = []
    const openapi_schema = JSON.parse(form.value.openapi_schema)

    // 2.检测是否存在paths路径
    if ('paths' in openapi_schema) {
      // 3.循环所有paths并提取工具
      for (const path in openapi_schema['paths']) {
        // 4.遍历对应path下的get和post方法
        for (const method in openapi_schema['paths'][path]) {
          if (['get', 'post'].includes(method)) {
            // 5.提取工具信息，并校验是否存在name、description这两个字段
            const tool = openapi_schema['paths'][path][method]
            if ('operationId' in tool && 'description' in tool) {
              available_tools.push({
                name: tool?.operationId,
                description: tool?.description,
                method: method,
                path: path,
              })
            }
          }
        }
      }
    }
    return available_tools
  } catch (_error: unknown) {
    return []
  }
})

// 2.定义滚动分页处理器
const handleScroll = (event: UIEvent) => {
  // 2.1 获取滚动距离、可滚动的最大距离、客户端/浏览器窗口的高度
  const { scrollTop, scrollHeight, clientHeight } = event.target as HTMLElement

  // 2.2 判断是否滑动到底部
  if (scrollTop + clientHeight >= scrollHeight - 10) {
    if (getApiToolProvidersLoading.value) return
    void handleLoadApiToolProviders(false, String(route.query?.search_word ?? ''))
  }
}

// 3.定义打开更新模态窗
const handleUpdate = async () => {
  const requestId = ++providerEditRequestId
  iconUploadRequestId += 1
  // 3.1 获取当前显示的provider_id
  const provider_id = api_tool_providers.value[showIdx.value]['id']

  // 3.2 根据拿到的id获取该工具提供商的详情信息
  try {
    await loadApiToolProvider(provider_id)
  } catch (error) {
    if (requestId === providerEditRequestId && !isUnmounted) {
      Message.error(getErrorMessage(error, t('space.tools.loadFailed')))
    }
    return
  }
  if (requestId !== providerEditRequestId || showIdx.value < 0) return

  // 3.3 更新form表单数据
  formRef.value?.resetFields()
  form.value.fileList = [{ uid: '1', name: t('space.tools.iconPlaceholder'), url: api_tool_provider.value.icon }]
  form.value.icon = api_tool_provider.value.icon
  form.value.name = api_tool_provider.value.name
  form.value.openapi_schema = api_tool_provider.value.openapi_schema
  form.value.headers = api_tool_provider.value.headers

  showUpdateModal.value = true
}

const handleProviderDrawerCancel = () => {
  providerEditRequestId += 1
  showIdx.value = -1
}

// 4.定义删除工具提供者处理器
const handleDelete = () => {
  // 4.1 提取选中数据条目的提供者id
  const provider_id = api_tool_providers.value[showIdx.value]['id']

  // 4.2 调用删除Api工具提供者处理器
  handleDeleteApiToolProvider(provider_id, () => {
    // 4.3 关闭模态窗+抽屉
    handleCancel()
    showIdx.value = -1

    // 4.4 重新加载数据
    void handleLoadApiToolProviders(true, String(route.query?.search_word ?? ''))
  })
}

// 提交模态窗处理器
const handleSubmit = async ({
  values,
  errors,
}: {
  values: ApiToolProviderFormValues
  errors: Record<string, ValidatedError> | undefined
}) => {
  // 1.如果存在错误则直接结束
  if (errors) return

  // 2.根据不同的类型发起不同的请求
  let isSaved = false
  if (showCreateModal.value) {
    // 3.调用处理器发起创建请求
    isSaved = await handleCreateApiToolProvider(values as CreateApiToolProviderRequest)
  } else if (showUpdateModal.value) {
    // 4.调用接口发起更新API工具请求
    isSaved = await handleUpdateApiToolProvider(
      api_tool_providers.value[showIdx.value]['id'],
      values as CreateApiToolProviderRequest,
    )
  }

  if (!isSaved) return

  // 5.执行后续操作，涵盖隐藏模态窗、隐藏抽屉
  handleCancel()
  showIdx.value = -1

  // 6.重新加载数据
  await handleLoadApiToolProviders(true, String(route.query?.search_word ?? ''))
}

// 取消显示模态窗处理器
const handleCancel = () => {
  iconUploadRequestId += 1
  cancelOpenapiSchemaAssistant()
  // 1.重置整个表单的数据
  formRef.value?.resetFields()
  openapiAssistantQuestion.value = ''
  openapiAssistantContent.value = ''
  showOpenapiSchemaExampleModal.value = false
  showCreateModal.value = false

  // 2.隐藏表单模态窗
  showUpdateModal.value = false
  void clearCreateTypeQuery()
}

// 页面DOM加载完毕初始化数据
onMounted(() => handleLoadApiToolProviders(true, String(route.query?.search_word ?? '')))

// 监听路由query变化
watch(
  () => route.query?.search_word,
  (newValue) => {
    void handleLoadApiToolProviders(true, String(newValue ?? ''))
  },
)

// 监听路由create_type变化
watch(
  () => route.query?.create_type,
  (newValue) => {
    if (newValue !== 'tool') return
    iconUploadRequestId += 1
    showCreateModal.value = true
    void clearCreateTypeQuery()
  },
  { immediate: true },
)
</script>

<template>
  <a-spin
    :loading="loading"
    class="block h-full w-full scrollbar-w-none overflow-y-scroll overflow-x-hidden"
    @scroll="handleScroll"
  >
    <!-- 底部插件列表 -->
    <a-row :gutter="[20, 20]">
      <!-- 有数据的UI状态 -->
      <a-col
        v-for="(provider, idx) in api_tool_providers"
        :key="provider.name"
        :xs="24"
        :sm="12"
        :md="8"
        :lg="6"
        :xl="6"
      >
        <a-card hoverable class="cursor-pointer rounded-lg" @click="showIdx = Number(idx)">
          <!-- 顶部提供商名称 -->
          <div class="flex items-center gap-3 mb-3">
            <!-- 左侧图标 -->
            <a-avatar :size="40" shape="square" :image-url="provider.icon" />
            <!-- 右侧工具信息 -->
            <div class="flex flex-col">
              <div class="text-base text-gray-900 font-bold">{{ provider.name }}</div>
              <div class="text-xs text-gray-500 line-clamp-1">
                {{ t('space.tools.providerSummary', { name: provider.name, count: provider.tools.length }) }}
              </div>
            </div>
          </div>
          <!-- 提供商的描述信息 -->
          <div class="leading-[18px] text-gray-500 h-[72px] line-clamp-4 mb-2">
            {{ provider.description }}
          </div>
          <!-- 提供商的发布信息 -->
          <div class="flex items-center gap-1.5">
            <a-avatar :size="18" class="bg-blue-700" :image-url="getUserAvatarUrl(accountStore.account.avatar, accountStore.account.name)">
              {{ (accountStore.account.name || t('common.status.unknown'))[0] }}
            </a-avatar>
            <div class="text-xs text-gray-400">
              {{ accountStore.account.name }} · {{ t('space.tools.recentEdited') }}
              {{ moment((provider.updated_at || provider.created_at) * 1000).format('MM-DD HH:mm') }}
            </div>
          </div>
        </a-card>
      </a-col>
      <!-- 没数据的UI状态 -->
      <a-col v-if="api_tool_providers.length === 0" :span="24">
        <a-empty
          :description="t('space.tools.empty')"
          class="h-[400px] flex flex-col items-center justify-center"
        />
      </a-col>
    </a-row>
    <!-- 加载器 -->
    <a-row v-if="paginator.total_page >= 2">
      <!-- 加载数据中 -->
        <a-col v-if="getApiToolProvidersLoading" :span="24" align="center">
          <a-space class="my-4">
            <a-spin />
            <div class="text-gray-400">{{ t('space.tools.loading') }}</div>
          </a-space>
        </a-col>
        <!-- 数据加载完成 -->
        <a-col v-else-if="paginator.current_page > paginator.total_page" :span="24" align="center">
        <div class="text-gray-400 my-4">{{ t('space.tools.loadedAll') }}</div>
        </a-col>
    </a-row>
    <!-- 卡片抽屉 -->
    <a-drawer
      :visible="showIdx != -1"
      :width="350"
      :footer="false"
      :title="t('space.tools.detailTitle')"
      :drawer-style="{ background: '#F9FAFB' }"
      @cancel="handleProviderDrawerCancel"
    >
      <!-- 外部容器，用于判断showIdx是否为-1，为-1的时候就不显示 -->
      <div v-if="showIdx != -1" class="">
        <!-- 顶部提供商名称 -->
        <div class="flex items-center gap-3 mb-3">
          <!-- 左侧图标 -->
          <a-avatar :size="40" shape="square" :image-url="api_tool_providers[showIdx].icon" />
          <!-- 右侧工具信息 -->
          <div class="flex flex-col">
            <div class="text-base text-gray-900 font-bold">
              {{ api_tool_providers[showIdx].name }}
            </div>
            <div class="text-xs text-gray-500 line-clamp-1">
              {{ t('space.tools.providerSummary', { name: api_tool_providers[showIdx].name, count: api_tool_providers[showIdx].tools.length }) }}
            </div>
          </div>
        </div>
        <!-- 提供商的描述信息 -->
        <div class="leading-[18px] text-gray-500 mb-4">
          {{ api_tool_providers[showIdx].description || t('space.tools.noDescription') }}
        </div>
        <!-- 编辑按钮 -->
        <a-button
          :loading="getApiToolProviderLoading"
          type="dashed"
          long
          class="mb-2 rounded-lg"
          @click="handleUpdate"
          >
            <template #icon>
              <icon-settings />
            </template>
          {{ t('space.tools.edit') }}
        </a-button>
        <!-- 分隔符 -->
        <hr class="my-4" />
        <!-- 提供者工具 -->
        <div class="flex flex-col gap-2">
          <div class="text-xs text-gray-500">
            {{ t('space.tools.containsTools', { count: api_tool_providers[showIdx].tools.length }) }}
          </div>
          <!-- 工具列表 -->
          <a-card
            v-for="tool in api_tool_providers[showIdx].tools"
            :key="tool.name"
            class="cursor-pointer flex flex-col rounded-xl"
          >
            <!-- 工具名称 -->
            <div class="font-bold text-gray-900 mb-2">{{ tool.name }}</div>
            <!-- 工具描述 -->
            <div class="text-gray-500 text-xs">{{ tool.description || t('space.tools.noDescription') }}</div>
            <!-- 工具参数 -->
            <div v-if="tool.inputs.length > 0" class="">
              <!-- 分隔符 -->
              <div class="flex items-center gap-2 my-4">
                <div class="text-xs font-bold text-gray-500">{{ t('space.tools.parameters') }}</div>
                <hr class="flex-1" />
              </div>
              <!-- 参数列表 -->
              <div class="flex flex-col gap-4">
                <div v-for="input in tool.inputs" :key="input.name" class="flex flex-col gap-2">
                  <!-- 上半部分 -->
                  <div class="flex items-center gap-2 text-xs">
                    <div class="text-gray-900 font-bold">{{ input.name }}</div>
                    <div class="text-gray-500">{{ typeMap[input.type] }}</div>
                    <div v-if="input.required" class="text-red-700">{{ t('space.tools.required') }}</div>
                  </div>
                  <!-- 参数描述信息 -->
                  <div class="text-xs text-gray-500">{{ input.description }}</div>
                </div>
              </div>
            </div>
          </a-card>
        </div>
      </div>
    </a-drawer>
    <a-modal
      :visible="showOpenapiSchemaExampleModal"
      :width="760"
      :title="t('space.tools.openapiSchemaExampleTitle')"
      :footer="false"
      :mask-closable="true"
      @cancel="showOpenapiSchemaExampleModal = false"
    >
      <div class="flex flex-col gap-3">
        <pre
          class="w-full max-h-[460px] overflow-auto rounded border border-gray-200 bg-white p-3 text-[12px] leading-[18px] text-gray-700"
        >{{ openapiSchemaInputExample }}</pre>
        <div class="flex justify-end gap-2">
        <a-button class="rounded-lg" @click="showOpenapiSchemaExampleModal = false">{{ t('space.tools.close') }}</a-button>
        <a-button type="primary" class="rounded-lg" @click="handleUseOpenapiSchemaExample">
            {{ t('space.tools.useExample') }}
        </a-button>
        </div>
      </div>
    </a-modal>

    <!-- 新建/修改模态窗 -->
    <a-modal
      :width="630"
      :visible="showCreateModal || showUpdateModal"
      hide-title
      :footer="false"
      modal-class="rounded-xl"
      @cancel="handleCancel"
    >
      <!-- 顶部标题 -->
      <div class="flex items-center justify-between">
        <div class="text-lg font-bold text-gray-700">
          {{ showCreateModal ? t('space.tools.createTitle') : t('space.tools.updateTitle') }}
        </div>
        <a-button type="text" class="!text-gray-700" size="small" @click="handleCancel">
          <template #icon>
            <icon-close />
          </template>
        </a-button>
      </div>
      <!-- 中间表单 -->
      <div class="pt-6">
        <a-form ref="formRef" :model="form" @submit="handleSubmit" layout="vertical">
          <a-form-item
            field="fileList"
            hide-label
            :rules="[{ required: true, message: t('space.tools.iconRequired') }]"
          >
            <IconUploadGenerator
              :name="form.name"
              description=""
              :icon="form.icon"
              :file-list="form.fileList"
              :loading="regenerateIconLoading || generateIconPreviewLoading"
              :placeholder="t('space.tools.iconPlaceholder')"
              :on-upload="handleUploadIcon"
              :on-generate="handleGenerateIcon"
              @update:icon="(val) => (form.icon = val)"
              @update:fileList="(val) => (form.fileList = val)"
            />
          </a-form-item>
          <a-form-item
            field="name"
            :label="t('space.tools.pluginName')"
            asterisk-position="end"
            :rules="[{ required: true, message: t('space.tools.pluginNameRequired') }]"
          >
            <a-input
              v-model="form.name"
              :placeholder="t('space.tools.pluginNamePlaceholder')"
              show-word-limit
              :max-length="60"
            />
          </a-form-item>
          <a-form-item
            field="openapi_schema"
            label="OpenAPI Schema"
            asterisk-position="end"
            :rules="[{ required: true, message: t('space.tools.openapiSchemaRequired') }]"
          >
            <div class="w-full flex flex-col gap-3">
              <div class="rounded-lg border border-gray-200 p-3 bg-gray-50">
                <div class="flex items-center justify-between gap-2 mb-2">
                  <div class="text-xs text-gray-600">{{ t('space.tools.schemaHint') }}</div>
                  <a-button
                    size="mini"
                    type="text"
                    class="!text-gray-700"
                    @click="toggleOpenapiSchemaExampleModal"
                  >
                    {{ showOpenapiSchemaExampleModal ? t('space.tools.hideExample') : t('space.tools.showExample') }}
                  </a-button>
                </div>

                <div class="text-xs text-gray-600 mb-2">{{ t('space.tools.aiHint') }}</div>
                <a-textarea
                  v-model="openapiAssistantQuestion"
                  :auto-size="{ minRows: 4, maxRows: 10 }"
                  :placeholder="t('space.tools.aiPlaceholder')"
                />
                <div class="mt-2">
                  <a-button
                    type="secondary"
                    long
                    class="rounded-lg !text-gray-700"
                    :loading="openapiAssistantLoading"
                    @click="handleGenerateOpenapiSchemaByAI"
                  >
                    {{ t('space.tools.aiAssist') }}
                  </a-button>
                </div>
              </div>

              <div class="rounded-lg border border-gray-200 p-3">
                <div class="text-xs text-gray-600 mb-2">{{ t('space.tools.openapiSchema') }}(JSON)</div>
                <a-textarea
                  v-model="form.openapi_schema"
                  :auto-size="{ minRows: 12, maxRows: 24 }"
                  :placeholder="t('space.tools.openapiSchemaPlaceholder')"
                  @blur="
                    () => {
                      if (form.openapi_schema.trim() !== '') {
                        // 调用验证openapi_schema接口
                        handleValidateOpenAPISchema(form.openapi_schema)
                      }
                    }
                  "
                />
              </div>
            </div>
          </a-form-item>
          <a-form-item :label="t('space.tools.availableTools')">
            <!-- 可用工具表格 -->
            <div class="rounded-lg border border-gray-200 w-full overflow-x-auto">
              <table class="w-full leading-[18px] text-xs text-gray-700 font-normal">
                <thead class="text-gray-500">
                  <tr class="border-b border-gray-200">
                    <th class="p-2 pl-3 font-medium">{{ t('space.tools.columns.name') }}</th>
                    <th class="p-2 pl-3 font-medium w-[236px]">{{ t('space.tools.columns.description') }}</th>
                    <th class="p-2 pl-3 font-medium">{{ t('space.tools.columns.method') }}</th>
                    <th class="p-2 pl-3 font-medium">{{ t('space.tools.columns.path') }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="(tool, idx) in tools"
                    :key="idx"
                    class="border-b last:border-0 border-gray-200 text-gray-700"
                  >
                    <td class="p-2 pl-3">{{ tool.name }}</td>
                    <td class="p-2 pl-3 w-[236px]">{{ tool.description }}</td>
                    <td class="p-2 pl-3">{{ tool.method }}</td>
                    <td class="p-2 pl-3 w-[62px]">{{ tool.path }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </a-form-item>
          <a-form-item :label="t('space.tools.headers')">
            <!-- 请求头表单 -->
            <div class="rounded-lg border border-gray-200 w-full overflow-x-auto">
              <table class="w-full leading-[18px] text-xs text-gray-700 font-normal mb-3">
                <thead class="text-gray-500">
                  <tr class="border-b border-gray-200">
                    <th class="p-2 pl-3 font-medium">{{ t('space.tools.columns.key') }}</th>
                    <th class="p-2 pl-3 font-medium">{{ t('space.tools.columns.value') }}</th>
                    <th class="p-2 pl-3 font-medium w-[50px]">{{ t('space.tools.columns.action') }}</th>
                  </tr>
                </thead>
                <tbody v-if="form.headers.length > 0" class="border-b border-gray-200">
                  <tr
                    v-for="(header, idx) in form.headers"
                    :key="idx"
                    class="border-b last:border-0 border-gray-200"
                  >
                    <td class="p-2 pl-3">
                      <a-form-item :field="`headers[${idx}].key`" hide-label class="m-0">
                        <a-input v-model="header.key" :placeholder="t('space.tools.headerKeyPlaceholder')" />
                      </a-form-item>
                    </td>
                    <td class="p-2 pl-3">
                      <a-form-item :field="`headers[${idx}].value`" hide-label class="m-0">
                        <a-input v-model="header.value" :placeholder="t('space.tools.headerValuePlaceholder')" />
                      </a-form-item>
                    </td>
                    <td class="p-2 pl-3">
                      <a-button
                        size="mini"
                        type="text"
                        class="!text-gray-700"
                        @click="form.headers.splice(idx, 1)"
                      >
                        <template #icon>
                          <icon-delete />
                        </template>
                      </a-button>
                    </td>
                  </tr>
                </tbody>
              </table>
              <a-button
                size="mini"
                class="rounded ml-3 mb-3 !text-gray-700"
                @click="form.headers.push({ key: '', value: '' })"
              >
                <template #icon>
                  <icon-plus />
                </template>
                {{ t('space.tools.addHeader') }}
              </a-button>
            </div>
          </a-form-item>
          <!-- 底部按钮 -->
          <div class="flex items-center justify-between">
            <div class="">
              <a-button
                v-if="showUpdateModal"
                class="rounded-lg !text-red-700"
                @click="handleDelete"
              >
                {{ t('space.tools.delete') }}
              </a-button>
            </div>
            <a-space :size="16">
              <a-button class="rounded-lg" @click="handleCancel">{{ t('space.tools.cancel') }}</a-button>
              <a-button
                :loading="updateApiToolProviderLoading || createApiToolProviderLoading"
                type="primary"
                html-type="submit"
                class="rounded-lg"
              >
                {{ t('space.tools.save') }}
              </a-button>
            </a-space>
          </div>
        </a-form>
      </div>
    </a-modal>
  </a-spin>
</template>

<style scoped>
:deep(.arco-row) {
  width: 100% !important;
  max-width: 100% !important;
}
</style>
