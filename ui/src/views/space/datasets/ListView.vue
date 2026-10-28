<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import moment from 'moment'
import type { ValidatedError } from '@arco-design/web-vue'
import { useI18n } from 'vue-i18n'
import {
  useCreateOrUpdateDataset,
  useDeleteDataset,
  useGenerateIconPreview,
  useGetDataset,
  useGetDatasetsWithPage,
  useRegenerateIcon,
} from '@/hooks/use-dataset'
import { useUploadImage } from '@/hooks/use-upload-file'
import { useAccountStore } from '@/stores/account'
import IconUploadGenerator from '@/components/IconUploadGenerator.vue'
import { Message } from '@arco-design/web-vue'
import { getUserAvatarUrl } from '@/utils/helper'

// 1.定义页面所需数据
const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const accountStore = useAccountStore()
let updateDatasetID = ''
const showCreateModal = ref(false)
const { dataset, loadDataset } = useGetDataset()
const { loading, datasets, paginator, loadDatasets } = useGetDatasetsWithPage()
const { image_url, handleUploadImage } = useUploadImage()
const {
  loading: submitLoading,
  form,
  formRef,
  saveDataset,
  showUpdateModal,
  updateShowUpdateModal,
} = useCreateOrUpdateDataset()
const { handleDelete } = useDeleteDataset()
const { loading: regenerateIconLoading, handleRegenerateIcon } = useRegenerateIcon()
const { loading: generateIconPreviewLoading, handleGenerateIconPreview } = useGenerateIconPreview()
const search_word = computed(() => {
  return String(route.query?.search_word ?? '')
})

const clearCreateTypeQuery = async () => {
  const nextQuery = { ...route.query }
  delete nextQuery.create_type
  await router.replace({
    path: route.path,
    query: nextQuery,
  })
}

// 2.定义上传图标处理器
const handleUploadIcon = async (file: File) => {
  await handleUploadImage(file)
  form.value.icon = image_url.value
  form.value.fileList = [{ uid: '1', name: t('space.datasets.modal.iconPlaceholder'), url: image_url.value }]
  Message.success(t('space.datasets.uploadSuccess'))
}

// 3.定义生成图标处理器
const handleGenerateIcon = async () => {
  if (!form.value.name || form.value.name.trim() === '') {
    Message.warning(t('space.datasets.enterNameFirst'))
    return
  }

  try {
    // 更新模式：调用 regenerateIcon
    if (updateDatasetID) {
      const iconUrl = await handleRegenerateIcon(updateDatasetID)
      if (iconUrl) {
        form.value.icon = iconUrl
        form.value.fileList = [{ uid: '1', name: t('space.datasets.modal.iconPlaceholder'), url: iconUrl }]
        Message.success(t('space.datasets.generateSuccess'))
      }
    }
    // 创建模式：调用 generateIconPreview
    else {
      const iconUrl = await handleGenerateIconPreview(form.value.name, form.value.description)
      if (iconUrl) {
        form.value.icon = iconUrl
        form.value.fileList = [{ uid: '1', name: t('space.datasets.modal.iconPlaceholder'), url: iconUrl }]
        Message.success(t('space.datasets.generateSuccess'))
      }
    }
  } catch (_error: unknown) {
    // 错误已在 hooks 中处理
  }
}

// 4.定义滚动数据分页处理器
const handleScroll = async (event: UIEvent) => {
  // 2.1 获取滚动距离、可滚动的最大距离、客户端/浏览器窗口的高度
  const { scrollTop, scrollHeight, clientHeight } = event.target as HTMLElement

  // 2.2 判断是否滑动到底部
  if (scrollTop + clientHeight >= scrollHeight - 10) {
    if (loading.value) return
    await loadDatasets(false, search_word.value)
  }
}

// 5.定义编辑知识库处理器
const handleUpdate = (dataset_id: string) => {
  updateShowUpdateModal(true, async () => {
    // 1.调用api获取知识库详情
    const loadedDataset = await loadDataset(dataset_id)
    if (!loadedDataset) return
    updateDatasetID = dataset_id

    // 2.更新表单数据
    formRef.value?.resetFields()
    form.value.fileList = [{ uid: '1', name: t('space.datasets.modal.iconPlaceholder'), url: loadedDataset.icon }]
    form.value.icon = loadedDataset.icon
    form.value.name = loadedDataset.name
    form.value.description = loadedDataset.description
  })
}

const openCreateModal = async () => {
  showCreateModal.value = true
  await clearCreateTypeQuery()
}

// 6.定义取消显示模态窗
const handleCancel = async () => {
  showCreateModal.value = false
  updateShowUpdateModal(false, async () => {
    // 1.重置整个表单数据
    updateDatasetID = ''
    formRef.value?.resetFields()
  })
  await clearCreateTypeQuery()
}

// 7.定义提交模态窗处理器
const handleSubmit = async ({ errors }: { errors: Record<string, ValidatedError> | undefined }) => {
  // 1.如果出错则直接抛出
  if (errors) return

  // 2.调用保存知识库服务
  await saveDataset(updateDatasetID)

  // 3.关闭模态窗并且刷新数据
  handleCancel()
  await loadDatasets(true)
}

// 8.监听路由query的变化
watch(
  () => route.query?.search_word,
  (newValue) => loadDatasets(true, String(newValue)),
)

watch(
  () => route.query?.create_type,
  (newValue) => {
    if (newValue === 'dataset') {
      void openCreateModal()
    }
  },
  { immediate: true },
)

// 9.页面DOM加载后加载数据
onMounted(() => {
  loadDatasets(true, search_word.value)
})

// 10.定义卡片点击处理器
const handleCardClick = (datasetId: string) => {
  router.push({
    name: 'space-datasets-documents-list',
    params: { dataset_id: datasetId },
  })
}
</script>

<template>
  <a-spin
    :loading="loading"
    class="block h-full w-full scrollbar-w-none overflow-y-scroll overflow-x-hidden"
    @scroll="handleScroll"
  >
    <!-- 底部知识库列表 -->
    <a-row :gutter="[20, 20]">
      <!-- 有数据的UI状态 -->
      <a-col
        v-for="dataset in datasets"
        :key="dataset.id"
        :xs="24"
        :sm="12"
        :md="8"
        :lg="6"
        :xl="6"
      >
        <a-card hoverable class="cursor-pointer rounded-lg" @click="handleCardClick(dataset.id)">
          <!-- 顶部知识库名称 -->
          <div class="flex items-center gap-3 mb-3">
            <!-- 左侧图标 -->
            <a-avatar :size="40" shape="square" :image-url="dataset.icon" />
            <!-- 右侧知识库信息 -->
            <div class="flex flex-1 justify-between">
              <div class="flex flex-col min-w-0">
                <div class="text-base text-gray-900 font-bold line-clamp-1 min-w-0">
                  {{ dataset.name }}
                </div>
                <div class="text-xs text-gray-500 line-clamp-1">
                  {{ t('space.datasets.stats', {
                    documents: dataset.document_count,
                    characters: Math.round(dataset.character_count / 1000),
                    apps: dataset.related_app_count,
                  }) }}
                </div>
              </div>
              <!-- 操作按钮 -->
              <a-dropdown position="br" @click.stop>
                <a-button type="text" size="small" class="rounded-lg !text-gray-700">
                  <template #icon>
                    <icon-more />
                  </template>
                </a-button>
                <template #content>
                  <a-doption @click="() => handleUpdate(dataset.id)">{{ t('space.datasets.settings') }}</a-doption>
                  <a-doption
                    class="!text-red-500"
                    @click="() => handleDelete(dataset.id, () => loadDatasets(true))"
                  >
                    {{ t('space.datasets.delete') }}
                  </a-doption>
                </template>
              </a-dropdown>
            </div>
          </div>
          <!-- 知识库的描述信息 -->
          <div class="leading-[18px] text-gray-500 h-[72px] line-clamp-4 mb-2 break-all">
            {{ dataset.description }}
          </div>
          <!-- 知识库的归属者信息 -->
          <div class="flex items-center gap-1.5">
            <a-avatar :size="18" class="bg-blue-700" :image-url="getUserAvatarUrl(accountStore.account.avatar, accountStore.account.name)">
              {{ (accountStore.account.name || t('space.datasets.unknownUser'))[0] }}
            </a-avatar>
            <div class="text-xs text-gray-400">
              {{ accountStore.account.name || t('space.datasets.unknownUser') }} · {{ t('space.datasets.recentEdited') }}
              {{ moment((dataset.updated_at || dataset.created_at) * 1000).format('MM-DD HH:mm') }}
            </div>
          </div>
        </a-card>
      </a-col>
      <!-- 没数据的UI状态 -->
      <a-col v-if="datasets.length === 0" :span="24">
        <a-empty
          :description="t('space.datasets.empty')"
          class="h-[400px] flex flex-col items-center justify-center"
        />
      </a-col>
    </a-row>
    <!-- 加载器 -->
    <a-row v-if="paginator.total_page >= 2">
      <!-- 加载数据中 -->
      <a-col v-if="loading" :span="24" align="center">
        <a-space class="my-4">
          <a-spin />
          <div class="text-gray-400">{{ t('space.datasets.loading') }}</div>
        </a-space>
      </a-col>
      <!-- 数据加载完成 -->
      <a-col v-else-if="paginator.current_page > paginator.total_page" :span="24" align="center">
        <div class="text-gray-400 my-4">{{ t('space.datasets.loadedAll') }}</div>
      </a-col>
    </a-row>
    <!-- 新建/修改模态窗 -->
    <a-modal
      :width="520"
      :visible="showCreateModal || showUpdateModal"
      hide-title
      :footer="false"
      modal-class="rounded-xl"
      @cancel="handleCancel"
    >
      <!-- 顶部标题 -->
      <div class="flex items-center justify-between">
        <div class="text-lg font-bold text-gray-700">
          {{
            showCreateModal
              ? t('space.datasets.modal.createTitle')
              : t('space.datasets.modal.updateTitle')
          }}
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
            :rules="[{ required: true, message: t('space.datasets.modal.iconRequired') }]"
          >
            <IconUploadGenerator
              :name="form.name"
              :description="form.description"
              :icon="form.icon"
              :file-list="form.fileList"
              :loading="regenerateIconLoading || generateIconPreviewLoading"
              :placeholder="t('space.datasets.modal.iconPlaceholder')"
              :on-upload="handleUploadIcon"
              :on-generate="handleGenerateIcon"
              @update:icon="(val) => (form.icon = val)"
              @update:fileList="(val) => (form.fileList = val)"
            />
          </a-form-item>
          <a-form-item
            field="name"
            :label="t('space.datasets.modal.nameLabel')"
            asterisk-position="end"
            :rules="[{ required: true, message: t('space.datasets.modal.nameRequired') }]"
          >
            <a-input
              v-model="form.name"
              :placeholder="t('space.datasets.modal.namePlaceholder')"
              show-word-limit
              :max-length="60"
            />
          </a-form-item>
          <a-form-item field="description" :label="t('space.datasets.modal.descriptionLabel')" asterisk-position="end">
            <a-textarea
              v-model="form.description"
              :auto-size="{ minRows: 4, maxRows: 6 }"
              :placeholder="t('space.datasets.modal.descriptionPlaceholder')"
            />
          </a-form-item>
          <!-- 底部按钮 -->
          <div class="flex items-center justify-between">
            <div class=""></div>
            <a-space :size="16">
              <a-button class="rounded-lg" @click="handleCancel">{{ t('common.actions.cancel') }}</a-button>
              <a-button
                :loading="submitLoading"
                type="primary"
                html-type="submit"
                class="rounded-lg"
              >
                {{ t('common.actions.save') }}
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
