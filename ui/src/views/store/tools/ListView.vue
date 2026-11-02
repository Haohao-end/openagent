<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Message, Form, type FileItem, type ValidatedError } from '@arco-design/web-vue'
import { apiPrefix } from '@/config'
import { useGetBuiltinTools, useGetCategories } from '@/hooks/use-builtin-tool'
import { useUploadImage } from '@/hooks/use-upload-file'
import { useCreateApiToolProvider, useGenerateIconPreview, useValidateOpenAPISchema } from '@/hooks/use-tool'
import { formatTimestampShort } from '@/utils/time-formatter'
import IconUploadGenerator from '@/components/IconUploadGenerator.vue'
import type { CreateApiToolProviderRequest } from '@/models/api-tool'
import { getStoreCategoryDisplayName, getStoreTypeDisplayName } from '@/utils/store-display'

// 1.定义页面所需数据
const { categories, loadCategories } = useGetCategories()
const { loading: getBuiltinToolsLoading, builtin_tools, loadBuiltinTools } = useGetBuiltinTools()
const { loading: createApiToolProviderLoading, handleCreateApiToolProvider } = useCreateApiToolProvider()
const { image_url, handleUploadImage } = useUploadImage()
const { loading: generateIconPreviewLoading, handleGenerateIconPreview } = useGenerateIconPreview()
const { loading: validateOpenapiSchemaLoading, handleValidateOpenAPISchema } =
  useValidateOpenAPISchema()
const { t, locale } = useI18n()
const category = ref<string>('all')
const search_word = ref<string>('')
const showIdx = ref<number>(-1)
const showCreateModal = ref(false)
const formRef = ref<InstanceType<typeof Form>>()
const form = ref<{
  fileList: FileItem[]
  icon: string
  name: string
  openapi_schema: string
  headers: Array<{ key: string; value: string }>
}>({
  fileList: [],
  icon: '',
  name: '',
  openapi_schema: '',
  headers: [],
})

const handleUploadIcon = async (file: File) => {
  await handleUploadImage(file)
  form.value.icon = image_url.value
  form.value.fileList = [{ uid: '1', name: t('space.tools.iconPlaceholder'), url: image_url.value }]
  Message.success(t('space.tools.iconUploadSuccess'))
}

const handleGenerateIcon = async () => {
  if (!form.value.name || form.value.name.trim() === '') {
    Message.warning(t('space.tools.enterNameFirst'))
    return
  }

  const iconUrl = await handleGenerateIconPreview(form.value.name, '')
  if (iconUrl) {
    form.value.icon = iconUrl
    form.value.fileList = [{ uid: '1', name: t('space.tools.iconPlaceholder'), url: iconUrl }]
    Message.success(t('space.tools.iconGenerateSuccess'))
  }
}

const handleCreateCancel = () => {
  formRef.value?.resetFields()
  showCreateModal.value = false
}

const handleCreateSubmit = async ({
  values,
  errors,
}: {
  values: { fileList: FileItem[]; icon: string; name: string; openapi_schema: string; headers: Array<{ key: string; value: string }> }
  errors: Record<string, ValidatedError> | undefined
}) => {
  if (errors) return
  const isSaved = await handleCreateApiToolProvider(values as CreateApiToolProviderRequest)
  if (!isSaved) return
  handleCreateCancel()
}

const handleValidateSchemaBlur = async () => {
  const schema = form.value.openapi_schema.trim()
  if (!schema) return
  try {
    await handleValidateOpenAPISchema(schema)
  } catch {
    // handled by hook
  }
}
const filterBuiltinTools = computed(() => {
  return builtin_tools.value.filter((item: any) => {
    // 分别检索分类信息+搜索词，只有同时符合的时候才返回数据
    const matchCategory = category.value === 'all' || item.category === category.value
    const matchSearchWord =
      search_word.value === '' || item.label.toLowerCase().includes(search_word.value.toLowerCase())

    return matchCategory && matchSearchWord
  })
})

const getCategoryLabel = (value: string) => {
  return getStoreCategoryDisplayName(value, locale.value as 'zh-CN' | 'en-US')
}

const getTypeLabel = (value: string) => {
  return getStoreTypeDisplayName(value, locale.value as 'zh-CN' | 'en-US')
}

// 2.页面DOM加载完毕时获取数据
onMounted(() => {
  loadCategories()
  loadBuiltinTools()
})
</script>

<template>
  <a-spin :loading="getBuiltinToolsLoading" class="block h-full w-full overflow-hidden">
    <div class="p-6 flex flex-col h-full min-h-0 overflow-hidden">
      <!-- 顶层标题+创建按钮 -->
      <div class="flex items-center justify-between mb-6">
        <!-- 左侧标题 -->
        <div class="flex items-center gap-2">
          <a-avatar :size="32" class="bg-blue-700">
            <icon-common :size="18" />
          </a-avatar>
          <div class="text-lg font-medium text-gray-900">{{ t('store.tools.title') }}</div>
        </div>
        <!-- 创建按钮 -->
        <router-link :to="{ name: 'space-tools-list', query: { create_type: 'tool' } }">
          <a-button type="primary" class="rounded-lg">
            {{ t('store.tools.createButton') }}
          </a-button>
        </router-link>
      </div>
      <!-- 插件分类+搜索框 -->
      <div class="flex items-center justify-between mb-6">
        <!-- 左侧分类 -->
        <div class="flex items-center gap-2">
          <a-button
            :type="category === 'all' ? 'secondary' : 'text'"
            class="rounded-lg !text-gray-700 px-3"
            @click="category = 'all'"
            >{{ t('store.tools.all') }}
          </a-button>
          <a-button
            v-for="item in categories"
            :key="item.category"
            :type="category === item.category ? 'secondary' : 'text'"
            class="rounded-lg !text-gray-700 px-3"
            @click="category = item.category"
          >
            {{ getCategoryLabel(item.category || item.name) }}
          </a-button>
        </div>
        <!-- 右侧搜索 -->
        <a-input-search
          v-model="search_word"
          :placeholder="t('store.tools.searchPlaceholder')"
          class="w-[240px] bg-white rounded-lg border-gray-300"
        />
      </div>
      <!-- 底部插件列表 -->
      <div class="flex-1 min-h-0 overflow-y-auto overflow-x-hidden scrollbar-w-none">
        <a-row :gutter="[20, 20]">
          <!-- 有数据的UI状态 -->
          <a-col v-for="(builtinTool, idx) in filterBuiltinTools" :key="builtinTool.name" :span="6">
            <a-card hoverable class="cursor-pointer rounded-lg" @click="showIdx = idx">
              <!-- 顶部提供商名称 -->
              <div class="flex items-center gap-3 mb-3">
                <!-- 左侧图标 -->
                <a-avatar
                  :size="40"
                  shape="square"
                  class="shrink-0"
                  :style="{ backgroundColor: builtinTool.background }"
                >
                  <img
                    :src="`${apiPrefix}/builtin-tools/${builtinTool.name}/icon`"
                    :alt="builtinTool.name"
                    class="w-full h-full object-contain"
                  />
                </a-avatar>
                <!-- 右侧工具信息 -->
                <div class="flex flex-col">
                  <div class="text-base text-gray-900 font-bold">{{ builtinTool.label }}</div>
                  <div class="text-xs text-gray-500 line-clamp-1">
                    {{ t('store.tools.providerSummary', { name: builtinTool.name, count: builtinTool.tools.length }) }}
                  </div>
                </div>
              </div>
              <!-- 提供商的描述信息 -->
              <div class="leading-[18px] text-gray-500 h-[72px] line-clamp-4 mb-2">
                {{ builtinTool.description }}
              </div>
              <!-- 提供商的发布信息 -->
              <div class="flex items-center gap-1.5">
                <a-avatar :size="18" class="bg-blue-700">
                  <icon-user />
                </a-avatar>
                <div class="text-xs text-gray-400">
                  {{ t('store.tools.publishedAt', { time: formatTimestampShort(builtinTool.created_at) }) }}
                </div>
              </div>
            </a-card>
          </a-col>
          <!-- 没数据的UI状态 -->
          <a-col v-if="filterBuiltinTools.length === 0" :span="24">
            <a-empty
              :description="t('store.tools.empty')"
              class="h-[400px] flex flex-col items-center justify-center"
            />
          </a-col>
        </a-row>
      </div>
      <!-- 卡片抽屉 -->
      <a-drawer
        :visible="showIdx != -1"
        :width="350"
        :footer="false"
        :title="t('store.tools.detailTitle')"
        :drawer-style="{ background: '#F9FAFB' }"
        @cancel="showIdx = -1"
      >
        <!-- 外部容器，用于判断showIdx是否为-1，为-1的时候就不显示 -->
        <div v-if="showIdx != -1" class="">
          <!-- 顶部提供商名称 -->
          <div class="flex items-center gap-3 mb-3">
            <!-- 左侧图标 -->
            <a-avatar
              :size="40"
              shape="square"
              class="shrink-0"
              :style="{ backgroundColor: filterBuiltinTools[showIdx].background }"
            >
              <img
                :src="`${apiPrefix}/builtin-tools/${filterBuiltinTools[showIdx].name}/icon`"
                :alt="filterBuiltinTools[showIdx].name"
                class="w-full h-full object-contain"
              />
            </a-avatar>
            <!-- 右侧工具信息 -->
            <div class="flex flex-col">
              <div class="text-base text-gray-900 font-bold">
                {{ filterBuiltinTools[showIdx].label }}
              </div>
              <div class="text-xs text-gray-500 line-clamp-1">
                {{ t('store.tools.providerSummary', { name: filterBuiltinTools[showIdx].name, count: filterBuiltinTools[showIdx].tools.length }) }}
              </div>
            </div>
          </div>
          <!-- 提供商的描述信息 -->
          <div class="leading-[18px] text-gray-500 mb-2">
            {{ filterBuiltinTools[showIdx].description }}
          </div>
          <!-- 分隔符 -->
          <hr class="my-4" />
          <!-- 提供者工具 -->
          <div class="flex flex-col gap-2">
              <div class="text-xs text-gray-500">
              {{ t('store.tools.containsTools', { count: filterBuiltinTools[showIdx].tools.length }) }}
            </div>
            <!-- 工具列表 -->
            <a-card
              v-for="tool in filterBuiltinTools[showIdx].tools"
              :key="tool.name"
              class="cursor-pointer flex flex-col rounded-xl"
            >
              <!-- 工具名称 -->
              <div class="font-bold text-gray-900 mb-2">{{ tool.label }}</div>
              <!-- 工具描述 -->
              <div class="text-gray-500 text-xs">{{ tool.description }}</div>
              <!-- 工具参数 -->
              <div v-if="tool.inputs.length > 0" class="">
                <!-- 分隔符 -->
                <div class="flex items-center gap-2 my-4">
                  <div class="text-xs font-bold text-gray-500">{{ t('store.tools.parameters') }}</div>
                  <hr class="flex-1" />
                </div>
                <!-- 参数列表 -->
                <div class="flex flex-col gap-4">
                  <div v-for="input in tool.inputs" :key="input.name" class="flex flex-col gap-2">
                    <!-- 上半部分 -->
                    <div class="flex items-center gap-2 text-xs">
                      <div class="text-gray-900 font-bold">{{ input.name }}</div>
                      <div class="text-gray-500">{{ getTypeLabel(input.type) }}</div>
                      <div v-if="input.required" class="text-red-700">{{ t('store.tools.required') }}</div>
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
        :width="630"
        :visible="showCreateModal"
        hide-title
        :footer="false"
        modal-class="rounded-xl"
        @cancel="handleCreateCancel"
      >
        <div class="flex items-center justify-between">
          <div class="text-lg font-bold text-gray-700">{{ t('space.tools.createTitle') }}</div>
          <a-button type="text" class="!text-gray-700" size="small" @click="handleCreateCancel">
            <template #icon>
              <icon-close />
            </template>
          </a-button>
        </div>

        <div class="pt-6">
          <a-form ref="formRef" :model="form" @submit="handleCreateSubmit" layout="vertical">
            <a-form-item
              field="fileList"
              hide-label
              :rules="[{ required: true, message: t('space.tools.iconRequired') }]"
            >
              <IconUploadGenerator
                :name="form.name"
                :description="''"
                :icon="form.icon"
                :file-list="form.fileList"
                :loading="generateIconPreviewLoading"
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
                <div class="rounded-lg border border-gray-200 p-3">
                  <a-textarea
                    v-model="form.openapi_schema"
                    :auto-size="{ minRows: 12, maxRows: 24 }"
                    :placeholder="t('space.tools.openapiSchemaPlaceholder')"
                    @blur="handleValidateSchemaBlur"
                  />
                </div>

                <div class="rounded-lg border border-gray-200 w-full overflow-x-auto">
                  <table class="w-full leading-[18px] text-xs text-gray-700 font-normal">
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
                          <a-input v-model="header.key" :placeholder="t('space.tools.headerKeyPlaceholder')" />
                        </td>
                        <td class="p-2 pl-3">
                          <a-input v-model="header.value" :placeholder="t('space.tools.headerValuePlaceholder')" />
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
              </div>
            </a-form-item>

            <div class="flex items-center justify-end gap-4">
              <a-button class="rounded-lg" @click="handleCreateCancel">{{ t('common.actions.cancel') }}</a-button>
              <a-button
                :loading="createApiToolProviderLoading || validateOpenapiSchemaLoading"
                type="primary"
                html-type="submit"
                class="rounded-lg"
              >
                {{ t('common.actions.save') }}
              </a-button>
            </div>
          </a-form>
        </div>
      </a-modal>
    </div>
  </a-spin>
</template>

<style scoped></style>
