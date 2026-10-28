<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import { useI18n } from 'vue-i18n'
import CardGridSkeleton from '@/components/skeletons/CardGridSkeleton.vue'
import ResourceCardDescription from '@/components/ResourceCardDescription.vue'
import { getErrorMessage } from '@/utils/error'
import { formatTimestampShort } from '@/utils/time-formatter'
import { getUserAvatarUrl } from '@/utils/helper'
import { getStoreCategoryDisplayName } from '@/utils/store-display'
import { useAccountStore } from '@/stores/account'
import {
  deleteMcpProvider,
  getMcpProvidersWithPage,
  publishMcpProvider,
  unpublishMcpProvider,
} from '@/services/mcp'
import type { McpProvider } from '@/models/mcp'
import CreateOrUpdateMcpModal from './components/CreateOrUpdateMcpModal.vue'

const route = useRoute()
const router = useRouter()
const accountStore = useAccountStore()
const { t, locale } = useI18n()

const loading = ref(false)
let latestProvidersRequest = 0
const providers = ref<McpProvider[]>([])
const hasMore = ref(true)
const page = ref(1)
const pageSize = ref(20)
const showCreateOrUpdateMcpModalVisible = ref(false)
const updateMcpProviderId = ref('')

const searchWord = computed(() => String(route.query?.search_word ?? ''))

const clearCreateTypeQuery = async () => {
  const nextQuery = { ...route.query }
  delete nextQuery.create_type
  await router.replace({
    path: route.path,
    query: nextQuery,
  })
}

const getCategoryLabel = (value: string) => {
  return getStoreCategoryDisplayName(value, locale.value as 'zh-CN' | 'en-US')
}

const loadProviders = async (init = false) => {
  if (loading.value && !init) return
  if (!hasMore.value && !init) return

  if (init) {
    page.value = 1
    hasMore.value = true
    providers.value = []
  }

  const requestId = ++latestProvidersRequest
  loading.value = true
  try {
    const res = await getMcpProvidersWithPage({
      current_page: page.value,
      page_size: pageSize.value,
      search_word: searchWord.value.trim(),
      category: '',
    })

    if (requestId !== latestProvidersRequest) return
    const list = res.data.list || []
    if (page.value === 1) {
      providers.value = list
    } else {
      providers.value.push(...list)
    }

    hasMore.value = page.value < res.data.paginator.total_page
    if (hasMore.value) {
      page.value += 1
    }
  } catch (error: unknown) {
    if (requestId === latestProvidersRequest) {
      Message.error(getErrorMessage(error, t('space.mcp.loadFailed')))
    }
  } finally {
    if (requestId === latestProvidersRequest) loading.value = false
  }
}

const handleScroll = (event: Event) => {
  const target = event.target as HTMLElement | null
  if (!target) return
  const { scrollTop, scrollHeight, clientHeight } = target
  if (scrollTop + clientHeight >= scrollHeight - 10) {
    if (loading.value || !hasMore.value) return
    void loadProviders()
  }
}

const openCreateModal = () => {
  updateMcpProviderId.value = ''
  showCreateOrUpdateMcpModalVisible.value = true
}

const openEditModal = (provider: McpProvider) => {
  updateMcpProviderId.value = provider.id
  showCreateOrUpdateMcpModalVisible.value = true
}

const handleCardClick = (provider: McpProvider) => {
  openEditModal(provider)
}

const handleDelete = (provider: McpProvider) => {
  Modal.warning({
    title: t('space.mcp.deleteConfirmTitle'),
    content: t('space.mcp.deleteConfirmContent'),
    hideCancel: false,
    onOk: async () => {
      try {
        const resp = await deleteMcpProvider(provider.id)
        Message.success(resp.message)
        await loadProviders(true)
      } catch (error: unknown) {
        Message.error(getErrorMessage(error, t('space.mcp.deleteFailed')))
      }
    },
  })
}

const handleTogglePublish = async (provider: McpProvider) => {
  try {
    const resp = provider.is_public
      ? await unpublishMcpProvider(provider.id)
      : await publishMcpProvider(provider.id)
    Message.success(resp.message)
    await loadProviders(true)
  } catch (error: unknown) {
    Message.error(
      getErrorMessage(
        error,
        provider.is_public ? t('space.mcp.unpublishFailed') : t('space.mcp.publishFailed'),
      ),
    )
  }
}

watch(
  () => route.query?.search_word,
  async () => {
    await loadProviders(true)
  },
)

watch(
  () => route.query?.create_type,
  (newValue) => {
    if (newValue !== 'mcp') return
    openCreateModal()
    void clearCreateTypeQuery()
  },
  { immediate: true },
)

onMounted(async () => {
  await loadProviders(true)
})
</script>

<template>
  <a-spin :loading="loading" class="block h-full w-full scrollbar-w-none overflow-y-scroll overflow-x-hidden" @scroll="handleScroll">
    <div class="p-6 flex flex-col h-full min-h-0">
      <card-grid-skeleton v-if="loading && providers.length === 0" :count="8" />
      <a-row v-else :gutter="[20, 20]" class="flex-1 min-h-0 overflow-hidden">
        <a-col
          v-for="provider in providers"
          :key="provider.id"
          :xs="24"
          :sm="12"
          :md="8"
          :lg="6"
          :xl="6"
        >
          <a-card hoverable class="cursor-pointer rounded-lg h-full" @click="handleCardClick(provider)">
            <div class="flex items-start gap-3 mb-3">
              <a-avatar :size="40" shape="square" :style="{ backgroundColor: provider.background }">
                <img
                  v-if="provider.icon"
                  :src="provider.icon"
                  :alt="provider.name"
                  class="w-full h-full object-cover"
                />
                <span v-else class="text-white font-semibold">
                  {{ (provider.label || provider.name || 'M')[0] }}
                </span>
              </a-avatar>
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 min-w-0">
                  <div class="text-base font-bold text-gray-900 truncate">{{ provider.label }}</div>
                  <a-tag size="small" :color="provider.is_public ? 'green' : 'orange'">
                    {{ provider.is_public ? t('appStudio.shell.published') : t('appStudio.shell.draft') }}
                  </a-tag>
                </div>
                <div class="text-xs text-gray-500 line-clamp-1">
                  {{ provider.name }} · {{ provider.transport }} · {{ t('space.mcp.toolCount', { count: provider.tool_count }) }}
                </div>
              </div>
            </div>

            <resource-card-description :text="provider.description" />

            <div class="flex items-center gap-2 flex-wrap mt-3">
              <a-tag size="small" :color="provider.background">{{ getCategoryLabel(provider.category) }}</a-tag>
              <a-tag size="small" color="arcoblue">{{ provider.transport }}</a-tag>
              <a-tag size="small" :color="provider.is_bindable ? 'green' : 'gray'">
                {{ provider.is_bindable ? t('space.mcp.bindable') : t('space.mcp.viewOnly') }}
              </a-tag>
            </div>

            <div v-if="provider.bind_reason" class="mt-3 text-xs text-amber-700">
              {{ provider.bind_reason }}
            </div>

            <div class="flex items-center gap-1.5 mt-3">
              <a-avatar
                :size="18"
                class="bg-blue-700"
                :image-url="getUserAvatarUrl(provider.creator_avatar || accountStore.account.avatar, provider.creator_name || accountStore.account.name)"
              >
                {{ (provider.creator_name || accountStore.account.name || t('common.status.unknown'))[0] }}
              </a-avatar>
              <div class="text-xs text-gray-400">
                {{ provider.creator_name || accountStore.account.name || t('common.status.unknown') }} ·
                {{ t('space.mcp.recentEdited', { time: formatTimestampShort(provider.updated_at || provider.created_at) }) }}
              </div>
            </div>

            <div class="flex items-center justify-between gap-2 mt-4" @click.stop>
              <a-dropdown position="br" @click.stop>
                <a-button size="small" type="text" class="rounded-lg !text-gray-700">
                  <template #icon>
                    <icon-more />
                  </template>
                </a-button>
                <template #content>
                  <a-doption @click="() => openEditModal(provider)">
                    {{ t('space.mcp.edit') }}
                  </a-doption>
                  <a-doption @click="() => handleTogglePublish(provider)">
                    {{ provider.is_public ? t('space.mcp.unpublish') : t('space.mcp.publish') }}
                  </a-doption>
                  <a-doption class="text-red-700" @click="() => handleDelete(provider)">
                    {{ t('common.actions.delete') }}
                  </a-doption>
                </template>
              </a-dropdown>

              <a-button
                size="small"
              type="primary"
              class="rounded-lg"
              @click.stop="openEditModal(provider)"
            >
                {{ t('space.mcp.edit') }}
              </a-button>
            </div>
          </a-card>
        </a-col>

        <a-col v-if="providers.length === 0" :span="24">
          <a-empty :description="t('space.mcp.empty')" class="py-20" />
        </a-col>
      </a-row>
    </div>

    <create-or-update-mcp-modal
      v-model:visible="showCreateOrUpdateMcpModalVisible"
      v-model:mcp_provider_id="updateMcpProviderId"
      :callback="async () => await loadProviders(true)"
    />
  </a-spin>
</template>

<style scoped>
.scrollbar-w-none {
  scrollbar-width: none;
}

.scrollbar-w-none::-webkit-scrollbar {
  display: none;
}

.line-clamp-1 {
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
