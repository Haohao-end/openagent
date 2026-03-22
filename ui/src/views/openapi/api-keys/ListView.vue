<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  useDeleteApiKey,
  useGetApiKeysWithPage,
  useUpdateApiKeyIsActive,
} from '@/hooks/use-api-key'
import { Message } from '@arco-design/web-vue'
import { useCredentialStore } from '@/stores/credential'
import { AUTH_REQUIRED_EVENT } from '@/utils/request'
import { getErrorMessage } from '@/utils/error'
import CreateOrUpdateApiKeyModal from './components/CreateOrUpdateApiKeyModal.vue'
import { formatTimestampDate } from '@/utils/time-formatter'

// 1.定义页面所需基础数据
const route = useRoute()
const router = useRouter()
const credentialStore = useCredentialStore()
const props = defineProps({
  create_api_key: { type: Boolean, default: false, required: true },
})
const emits = defineEmits(['update:create_api_key'])
const {
  loading: getApiKeysWithPageLoading,
  paginator,
  api_keys,
  loadApiKeys,
} = useGetApiKeysWithPage()
const { handleUpdateApiKeyIsActive } = useUpdateApiKeyIsActive()
const { handleDeleteApiKey } = useDeleteApiKey()
const createOrUpdateApiKeyModalVisible = ref(false)
const updateApiKeyId = ref('')
const updateApiKeyIsActive = ref(false)
const updateApiKeyRemark = ref('')
const isLoggedIn = computed(() => {
  const now = Math.floor(Date.now() / 1000)
  return Boolean(
    credentialStore.credential.access_token &&
    credentialStore.credential.expire_at &&
    credentialStore.credential.expire_at > now,
  )
})

const openLoginModal = () => {
  if (typeof window === 'undefined') return
  window.dispatchEvent(
    new CustomEvent(AUTH_REQUIRED_EVENT, {
      detail: { redirect: route.fullPath },
    }),
  )
}

const loadApiKeysSafely = async (init: boolean = false) => {
  if (!isLoggedIn.value) return
  try {
    await loadApiKeys(init)
  } catch (error: unknown) {
    // 授权失效时 request 层会清空凭证并触发登录弹窗，这里不重复提示
    if (!isLoggedIn.value) return
    Message.error(getErrorMessage(error, '加载 API 密钥失败，请稍后重试'))
  }
}

// 3.监听create_api_key是否开启，执行创建操作
watch(
  () => props.create_api_key,
  (value) => {
    if (value && !isLoggedIn.value) {
      emits('update:create_api_key', false)
      createOrUpdateApiKeyModalVisible.value = false
      openLoginModal()
      return
    }

    // 3.1 清空updateApiKeyId
    updateApiKeyId.value = ''

    // 3.2 显示or隐藏模态窗
    createOrUpdateApiKeyModalVisible.value = Boolean(value)
  },
)

// 4.监听路由query变化，重新加载数据
watch(
  () => route.query,
  async (newQuery, oldQuery) => {
    if (!isLoggedIn.value) return
    if (newQuery.current_page != oldQuery.current_page) {
      await loadApiKeysSafely()
    }
  },
)

watch(
  isLoggedIn,
  async (loggedIn) => {
    if (!loggedIn) {
      api_keys.value = []
      createOrUpdateApiKeyModalVisible.value = false
      return
    }
    await loadApiKeysSafely(true)
  },
  { immediate: true },
)
</script>

<template>
  <div class="h-[calc(100vh-160px)] overflow-scroll scrollbar-w-none">
    <!-- 未登录状态 -->
    <div
      v-if="!isLoggedIn"
      class="flex flex-col items-center justify-center h-full bg-white rounded-lg border border-gray-200"
    >
      <div class="w-24 h-24 mb-6 bg-gray-100 rounded-full flex items-center justify-center">
        <icon-user class="text-5xl text-gray-400" />
      </div>
      <h3 class="text-lg font-semibold text-gray-900 mb-2">请先登录</h3>
      <p class="text-gray-500 mb-6 text-center max-w-md">
        登录后即可查看、创建和管理您的 API 密钥
      </p>
      <a-button
        type="primary"
        size="large"
        class="!rounded-lg !bg-gray-900 hover:!bg-gray-800"
        @click="openLoginModal"
      >
        立即登录
      </a-button>
    </div>

    <!-- 空状态 -->
    <div
      v-else-if="!getApiKeysWithPageLoading && api_keys.length === 0"
      class="flex flex-col items-center justify-center h-full bg-white rounded-lg border border-gray-200"
    >
      <div class="w-24 h-24 mb-6 bg-gray-100 rounded-full flex items-center justify-center">
        <icon-safe class="text-5xl text-gray-400" />
      </div>
      <h3 class="text-lg font-semibold text-gray-900 mb-2">暂无 API 密钥</h3>
      <p class="text-gray-500 mb-6 text-center max-w-md">
        创建您的第一个 API 密钥以开始使用 LLMOps 开放 API
      </p>
      <a-button type="primary" size="large" class="!rounded-lg !bg-gray-900 hover:!bg-gray-800" @click="emits('update:create_api_key', true)">
        <template #icon>
          <icon-plus />
        </template>
        创建密钥
      </a-button>
    </div>

    <!-- 表格内容 -->
    <div v-else class="bg-white rounded-lg border border-gray-200 overflow-hidden">
      <a-table
        :pagination="{
          total: paginator.total_record,
          current: paginator.current_page,
          defaultCurrent: 1,
          pageSize: paginator.page_size,
          defaultPageSize: 20,
          showTotal: true,
        }"
        :loading="getApiKeysWithPageLoading"
        :bordered="false"
        :data="api_keys"
        :hoverable="true"
        @page-change="
          (page: number) => {
            router.push({
              path: route.path,
              query: { current_page: page },
            })
          }
        "
      >
        <template #columns>
          <a-table-column
            title="密钥"
            data-index="api_key"
            :width="320"
            header-cell-class="!bg-gray-50 !text-gray-900 !font-semibold !border-b !border-gray-200"
            cell-class="!py-4"
          >
            <template #cell="{ record }">
              <div class="flex items-center gap-3">
                <div class="flex-shrink-0 w-8 h-8 bg-blue-500 rounded flex items-center justify-center">
                  <icon-safe class="text-white text-sm" />
                </div>
                <div class="flex-1 min-w-0">
                  <div class="font-mono text-sm text-gray-700">
                    {{ record.api_key }}
                  </div>
                  <div class="text-xs text-gray-500 mt-1">仅创建时展示完整密钥</div>
                </div>
              </div>
            </template>
          </a-table-column>
          <a-table-column
            title="状态"
            data-index="is_active"
            :width="120"
            header-cell-class="!bg-gray-50 !text-gray-900 !font-semibold !border-b !border-gray-200"
            cell-class="!py-4"
          >
            <template #cell="{ record }">
              <div
                v-if="record.is_active"
                class="inline-flex items-center gap-2 px-2.5 py-1 bg-green-50 border border-green-200 rounded text-green-700 text-sm font-medium whitespace-nowrap"
              >
                <div class="w-1.5 h-1.5 bg-green-500 rounded-full"></div>
                可用
              </div>
              <div
                v-else
                class="inline-flex items-center gap-2 px-2.5 py-1 bg-gray-100 border border-gray-200 rounded text-gray-600 text-sm font-medium whitespace-nowrap"
              >
                <div class="w-1.5 h-1.5 bg-gray-400 rounded-full"></div>
                已禁用
              </div>
            </template>
          </a-table-column>
          <a-table-column
            title="创建时间"
            data-index="created_at"
            :width="140"
            header-cell-class="!bg-gray-50 !text-gray-900 !font-semibold !border-b !border-gray-200"
            cell-class="!py-4"
          >
            <template #cell="{ record }">
              <div class="flex items-center gap-2 text-gray-600 text-sm whitespace-nowrap">
                <icon-clock-circle class="text-gray-400 flex-shrink-0" :size="16" />
                <span>{{ formatTimestampDate(record.created_at) }}</span>
              </div>
            </template>
          </a-table-column>
          <a-table-column
            title="备注"
            data-index="remark"
            :width="280"
            header-cell-class="!bg-gray-50 !text-gray-900 !font-semibold !border-b !border-gray-200"
            cell-class="!py-4"
          >
            <template #cell="{ record }">
              <div class="text-sm text-gray-700" :title="record.remark">
                {{ record.remark ? (record.remark.length > 35 ? record.remark.substring(0, 35) + '...' : record.remark) : '暂无备注' }}
              </div>
            </template>
          </a-table-column>
          <a-table-column
            title="操作"
            data-index="operator"
            header-cell-class="!bg-gray-50 !text-gray-900 !font-semibold !border-b !border-gray-200"
            cell-class="!py-4"
            :width="200"
          >
            <template #cell="{ record, rowIndex }">
              <div class="flex items-center gap-3">
                <!-- Switch 开关 -->
                <a-tooltip :content="record.is_active ? '点击禁用密钥' : '点击启用密钥'">
                  <a-switch
                    size="small"
                    :model-value="record.is_active"
                    @change="
                      (value: string | number | boolean) => {
                        const nextValue = Boolean(value)
                        handleUpdateApiKeyIsActive(record.id, nextValue, () => {
                          api_keys[rowIndex].is_active = nextValue
                        })
                      }
                    "
                  />
                </a-tooltip>

                <!-- 编辑 -->
                <a-tooltip content="编辑备注">
                  <a-button
                    size="small"
                    class="!rounded !text-gray-600 hover:!text-gray-900 hover:!bg-gray-100"
                    @click="
                      () => {
                        updateApiKeyId = record.id
                        updateApiKeyIsActive = record.is_active
                        updateApiKeyRemark = record.remark
                        createOrUpdateApiKeyModalVisible = true
                      }
                    "
                  >
                    <template #icon>
                      <icon-edit />
                    </template>
                  </a-button>
                </a-tooltip>

                <!-- 删除 -->
                <a-tooltip content="删除密钥">
                  <a-button
                    size="small"
                    class="!rounded !text-red-600 hover:!text-red-700 hover:!bg-red-50"
                    @click="
                      () =>
                        handleDeleteApiKey(record.id, async () => {
                          await loadApiKeys()
                        })
                    "
                  >
                    <template #icon>
                      <icon-delete />
                    </template>
                  </a-button>
                </a-tooltip>
              </div>
            </template>
          </a-table-column>
        </template>
      </a-table>
    </div>

    <!-- 新增or重命名模态窗 -->
    <create-or-update-api-key-modal
      v-model:visible="createOrUpdateApiKeyModalVisible"
      v-model:api_key_id="updateApiKeyId"
      v-model:is_active="updateApiKeyIsActive"
      v-model:remark="updateApiKeyRemark"
      @update:visible="(value) => emits('update:create_api_key', value)"
      :callback="async () => await loadApiKeys()"
    />
  </div>
</template>

<style scoped>
:deep(.arco-table-tr:hover) {
  background-color: rgb(249 250 251) !important;
}

/* 优化 Switch 样式 */
:deep(.arco-switch) {
  background-color: rgb(209 213 219) !important;
}

:deep(.arco-switch-checked) {
  background-color: rgb(34 197 94) !important;
}

:deep(.arco-switch:hover) {
  opacity: 0.9;
}
</style>
