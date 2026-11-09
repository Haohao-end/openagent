<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { useI18n } from 'vue-i18n'
import { useGetPublishedConfig, useRegenerateWebAppToken } from '@/hooks/use-app'
import { useGetWechatConfig, useUpdateWechatConfig } from '@/hooks/use-platform'
import { shareAppToSquare, unshareAppFromSquare, getAppTags, type AppTag } from '@/services/public-app'
import { getErrorMessage } from '@/utils/error'
import { getPublicAppTagDisplayName } from '@/utils/public-app-tag-display'

const props = withDefaults(defineProps<{ publishedRefreshToken?: number }>(), {
  publishedRefreshToken: 0,
})

// 1.定义页面所需数据
const route = useRoute()
const router = useRouter()
const wechatConfigModalVisible = ref(false)
const shareToSquareModalVisible = ref(false)
const shareCategory = ref('')
const categories = ref<AppTag[]>([])
const wechatConfigForm = ref({
  wechat_app_id: '',
  wechat_app_secret: '',
  wechat_token: '',
})

const {
  loading: getPublishedConfigLoading,
  published_config,
  loadPublishedConfig,
} = useGetPublishedConfig()
const {
  loading: regenerateWebAppTokenLoading,
  token,
  handleRegenerateWebAppToken,
} = useRegenerateWebAppToken()
const { loading: getWechatConfigLoading, wechat_config, loadWechatConfig } = useGetWechatConfig()
const { loading: updateWechatConfigLoading, handleUpdateWechatConfig } = useUpdateWechatConfig()
const { t, locale } = useI18n()
let appRouteRequestId = 0
const webAppUrl = computed(() => {
  if (published_config.value?.web_app?.status === 'published') {
    return getFullPath('web-apps-index', {
      token: published_config.value?.web_app?.token,
    })
  }
  return ''
})

// 2.定义获取完整路由路径函数
const getFullPath = (name: string, params = {}, query = {}) => {
  // 通过 router.resolve 获取路由的完整路径
  const { href } = router.resolve({ name, params, query })

  // 如果需要包括 host 部分，结合 window.location.origin
  return window.location.origin + href
}

const loadPageData = async (appId: string) => {
  await Promise.all([
    loadPublishedConfig(appId),
    loadWechatConfig(appId),
  ])
}

// 3.定义打开微信配置模态窗处理器
const handleShowWechatConfigModal = async () => {
  const requestId = appRouteRequestId
  // 3.1 调用api接口获取微信配置
  await loadWechatConfig(String(route.params?.app_id))
  if (requestId !== appRouteRequestId) return

  // 3.2 更新表单配置
  wechatConfigForm.value = {
    wechat_app_id: wechat_config.value.wechat_app_id,
    wechat_app_secret: wechat_config.value.wechat_app_secret,
    wechat_token: wechat_config.value.wechat_token,
  }

  // 3.3 显示模态窗
  wechatConfigModalVisible.value = true
}

// 4.定义取消微信配置模态窗处理器
const handleCancelWechatConfigModal = () => {
  wechatConfigModalVisible.value = false
}

// 5.定义提交微信配置模态窗处理器
const handleSubmitWechatConfigModal = async () => {
  // 5.1 调用hooks完成数据上传
  await handleUpdateWechatConfig(String(route.params?.app_id), {
    wechat_app_id: wechatConfigForm.value.wechat_app_id,
    wechat_app_secret: wechatConfigForm.value.wechat_app_secret,
    wechat_token: wechatConfigForm.value.wechat_token,
  })

  // 5.2 隐藏模态窗
  handleCancelWechatConfigModal()

  // 5.3 重新调用获取微信公众号配置接口
  await loadWechatConfig(String(route.params?.app_id))
}

// 6.加载应用标签
const loadCategories = async () => {
  try {
    const res = await getAppTags()
    categories.value = res.data.tags
  } catch (error: unknown) {
    Message.error(getErrorMessage(error, t('appStudio.published.square.loadTagsFailed')))
  }
}

const getCategoryDisplayName = (tag: AppTag) => {
  return getPublicAppTagDisplayName(tag, locale.value as 'zh-CN' | 'en-US')
}

// 7.显示共享到广场模态窗
const handleShowShareToSquareModal = async () => {
  await loadCategories()
  shareCategory.value = ''
  shareToSquareModalVisible.value = true
}

// 8.取消共享到广场
const handleCancelShareToSquareModal = () => {
  shareToSquareModalVisible.value = false
}

// 9.提交共享到广场
const handleSubmitShareToSquare = async () => {
  if (!shareCategory.value) {
    Message.warning(t('appStudio.published.square.categoryRequired'))
    return
  }

  try {
    await shareAppToSquare(String(route.params?.app_id), shareCategory.value)
    Message.success(t('appStudio.published.square.sharedSuccess'))
    shareToSquareModalVisible.value = false
    // 重新加载配置
    await loadPublishedConfig(String(route.params?.app_id))
  } catch (error: unknown) {
    Message.error(getErrorMessage(error, t('appStudio.published.square.shareFailed')))
  }
}

// 10.取消共享
const handleUnshareFromSquare = async () => {
  try {
    await unshareAppFromSquare(String(route.params?.app_id))
    Message.success(t('appStudio.published.square.unsharedSuccess'))
    // 重新加载配置
    await loadPublishedConfig(String(route.params?.app_id))
  } catch (error: unknown) {
    Message.error(getErrorMessage(error, t('appStudio.published.square.actionFailed')))
  }
}

onMounted(() => {
  void loadPageData(String(route.params?.app_id))
})

watch(
  () => String(route.params?.app_id),
  (appId, previousAppId) => {
    if (appId === previousAppId) {
      return
    }
    appRouteRequestId += 1
    if (!appId) return
    void loadPageData(appId)
  },
)

watch(
  () => props.publishedRefreshToken,
  (refreshToken, previousRefreshToken) => {
    if (refreshToken === previousRefreshToken) {
      return
    }
    void loadPublishedConfig(String(route.params?.app_id))
  },
)
</script>

<template>
  <div class="bg-white flex-1 w-full min-h-0 px-6 py-5">
    <!-- 发布渠道列表 -->
    <a-spin :loading="getPublishedConfigLoading" class="w-full">
      <table class="w-full">
        <thead>
          <tr class="h-10 bg-gray-100">
            <th class="font-normal text-left px-4 text-gray-700 border-r border-white">{{ t('appStudio.published.columns.channel') }}</th>
            <th class="font-normal text-left px-4 text-gray-700 border-r border-white">{{ t('appStudio.published.columns.status') }}</th>
            <th class="font-normal text-left px-4 text-gray-700">{{ t('appStudio.published.columns.actions') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr class="border-b">
            <td class="py-3 px-4 w-2/3">
              <div class="flex items-center gap-2">
                <a-avatar :size="36" shape="square" class="bg-blue-100">
                  <icon-compass :size="18" class="text-blue-700" />
                </a-avatar>
                <div class="flex flex-col">
                  <div class="text-gray-700 font-semibold">{{ t('appStudio.published.web.title') }}</div>
                  <div class="text-gray-500">{{ t('appStudio.published.web.description') }}</div>
                </div>
              </div>
            </td>
            <td class="py-3 px-4 w-1/12">
              <a-tag v-if="published_config?.web_app?.status !== 'published'" color="gray" bordered>
                <template #icon>
                  <icon-minus-circle />
                </template>
                {{ t('appStudio.published.statuses.unpublished') }}
              </a-tag>
              <a-tag v-else color="blue" bordered>
                <template #icon>
                  <icon-check-circle-fill />
                </template>
                {{ t('appStudio.published.statuses.published') }}
              </a-tag>
            </td>
            <td class="py-3 px-4">
              <div class="flex items-center gap-3">
                <!-- 左侧URL链接 -->
                <div class="flex items-center">
                  <div
                    class="bg-gray-100 h-8 leading-8 px-3 rounded-tl-lg rounded-bl-lg text-gray-700 w-[300px] max-w-[360px] line-clamp-1 break-all">
                    <template v-if="published_config?.web_app?.status === 'published'">
                      {{ webAppUrl }}
                    </template>
                    <template v-else>{{ t('appStudio.published.web.noUrl') }}</template>
                  </div>
                  <a-button :loading="regenerateWebAppTokenLoading"
                    :disabled="published_config?.web_app?.status !== 'published'" type="primary"
                    class="rounded-tr-lg rounded-br-lg px-2" @click="
                      async () => {
                        // 1.调用API接口发起请求
                        await handleRegenerateWebAppToken(String(route.params?.app_id))

                        // 2.更新web_app对应token的值
                        published_config.web_app.token = token
                      }
                    ">
                    {{ t('appStudio.published.web.regenerate') }}
                  </a-button>
                </div>
                <!-- 右侧访问按钮 -->
                <a-button class="rounded-lg px-2">
                  <template v-if="published_config?.web_app?.status !== 'published'">
                    {{ t('appStudio.published.web.visit') }}
                  </template>
                  <template v-else>
                    <a :href="webAppUrl" target="_blank" rel="noopener noreferrer">{{ t('appStudio.published.web.visit') }}</a>
                  </template>
                </a-button>
              </div>
            </td>
          </tr>
          <tr class="border-b">
            <td class="py-3 px-4 w-2/3">
              <div class="flex items-center gap-2">
                <a-avatar :size="36" shape="square" class="bg-purple-100">
                  <icon-apps :size="18" class="text-purple-700" />
                </a-avatar>
                <div class="flex flex-col">
                  <div class="text-gray-700 font-semibold">{{ t('appStudio.published.square.title') }}</div>
                  <div class="text-gray-500">{{ t('appStudio.published.square.description') }}</div>
                </div>
              </div>
            </td>
            <td class="py-3 px-4 w-1/12">
              <a-tag v-if="!published_config?.is_public" color="gray" bordered>
                <template #icon>
                  <icon-minus-circle />
                </template>
                {{ t('appStudio.published.statuses.unshared') }}
              </a-tag>
              <a-tag v-else color="blue" bordered>
                <template #icon>
                  <icon-check-circle-fill />
                </template>
                {{ t('appStudio.published.statuses.shared') }}
              </a-tag>
            </td>
            <td class="py-3 px-4">
              <div class="flex items-center gap-3">
                <a-button v-if="!published_config?.is_public" type="primary" class="rounded-lg px-2"
                  @click="handleShowShareToSquareModal">
                  <template #icon>
                    <icon-share-alt />
                  </template>
                  {{ t('appStudio.published.square.share') }}
                </a-button>
                <a-button v-else type="outline" status="danger" class="rounded-lg px-2"
                  @click="handleUnshareFromSquare">
                  <template #icon>
                    <icon-close />
                  </template>
                  {{ t('appStudio.published.square.unshare') }}
                </a-button>
                <a-button v-if="published_config?.is_public" class="rounded-lg px-2"
                  @click="router.push('/store/public-apps')">
                  <template #icon>
                    <icon-eye />
                  </template>
                  {{ t('appStudio.published.square.viewSquare') }}
                </a-button>
              </div>
            </td>
          </tr>
          <tr class="border-b">
            <td class="py-3 px-4 w-2/3">
              <div class="flex items-center gap-2">
                <a-avatar :size="36" shape="square" class="bg-green-100">
                  <icon-wechat :size="18" class="text-green-700" />
                </a-avatar>
                <div class="flex flex-col">
                  <div class="text-gray-700 font-semibold">{{ t('appStudio.published.wechat.title') }}</div>
                  <div class="text-gray-500">{{ t('appStudio.published.wechat.description') }}</div>
                </div>
              </div>
            </td>
            <td class="py-3 px-4 w-1/12">
              <a-tag v-if="wechat_config?.status !== 'configured'" color="gray" bordered>
                <template #icon>
                  <icon-minus-circle />
                </template>
                {{ t('appStudio.published.statuses.unconfigured') }}
              </a-tag>
              <a-tag v-else color="blue" bordered>
                <template #icon>
                  <icon-check-circle-fill />
                </template>
                {{ t('appStudio.published.statuses.configured') }}
              </a-tag>
            </td>
            <td class="py-3 px-4">
              <div class="flex items-center gap-3">
                <!-- 立即配置 -->
                <a-button :loading="getWechatConfigLoading" type="primary" class="rounded-lg px-2"
                  @click="handleShowWechatConfigModal">
                  <template #icon>
                    <icon-settings />
                  </template>
                  {{ t('appStudio.published.wechat.configureNow') }}
                </a-button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </a-spin>
    <!-- 微信公众号配置模态窗 -->
    <a-modal :visible="wechatConfigModalVisible" hide-title :footer="false" modal-class="rounded-xl w-[600px]"
      @cancel="handleCancelWechatConfigModal">
      <!-- 顶部标题 -->
      <div class="flex items-center justify-between">
        <div class="text-lg font-bold text-gray-700">{{ t('appStudio.published.wechat.modalTitle') }}</div>
        <a-button type="text" class="!text-gray-700" size="small" @click="handleCancelWechatConfigModal">
          <template #icon>
            <icon-close />
          </template>
        </a-button>
      </div>
      <!-- 中间表单 -->
      <div class="py-4">
        <div class="flex flex-col gap-5">
          <!-- 服务器ip -->
          <div class="flex flex-col gap-2">
            <div class="flex flex-col">
              <div class="flex items-center gap-1 text-gray-700">
                {{ t('appStudio.published.wechat.serverIp') }}
                <div class="text-red-700">*</div>
              </div>
            </div>
            <div class="text-gray-500">{{ wechat_config?.ip }}</div>
          </div>
          <!-- 服务器地址 -->
          <div class="flex flex-col gap-2">
            <div class="flex flex-col">
              <div class="flex items-center gap-1 text-gray-700">
                {{ t('appStudio.published.wechat.serverUrl') }}
                <div class="text-red-700">*</div>
              </div>
            </div>
            <div class="text-gray-500">{{ wechat_config?.url }}</div>
          </div>
          <!-- 开发者ID(AppID) -->
          <div class="flex flex-col gap-2">
            <div class="flex items-center gap-1 text-gray-700">
              {{ t('appStudio.published.wechat.appIdOptional') }}
            </div>
            <a-input v-model:model-value="wechatConfigForm.wechat_app_id" :placeholder="t('appStudio.published.wechat.appIdPlaceholder')" />
          </div>
          <!-- 开发者秘钥(AppSecret) -->
          <div class="flex flex-col gap-2">
            <div class="flex items-center gap-1 text-gray-700">
              {{ t('appStudio.published.wechat.appSecretOptional') }}
            </div>
            <a-input v-model:model-value="wechatConfigForm.wechat_app_secret" :placeholder="t('appStudio.published.wechat.appSecretPlaceholder')" />
          </div>
          <!-- 令牌(Token) -->
          <div class="flex flex-col gap-2">
            <div class="flex items-center gap-1 text-gray-700">
              {{ t('appStudio.published.wechat.tokenLabel') }}
            </div>
            <a-input v-model:model-value="wechatConfigForm.wechat_token" :placeholder="t('appStudio.published.wechat.tokenPlaceholder')" />
          </div>
        </div>
      </div>
      <!-- 底部按钮 -->
      <div class="flex items-center justify-between">
        <div class=""></div>
        <a-space :size="16">
          <a-button class="rounded-lg" @click="handleCancelWechatConfigModal">{{ t('common.actions.cancel') }}</a-button>
          <a-button :loading="updateWechatConfigLoading" type="primary" class="rounded-lg"
            @click="handleSubmitWechatConfigModal">
            {{ t('common.actions.save') }}
          </a-button>
        </a-space>
      </div>
    </a-modal>
    <!-- 共享到广场模态窗 -->
    <a-modal :visible="shareToSquareModalVisible" hide-title :footer="false" modal-class="rounded-xl w-[500px]"
      @cancel="handleCancelShareToSquareModal">
      <!-- 顶部标题 -->
      <div class="flex items-center justify-between mb-4">
        <div class="text-lg font-bold text-gray-700">{{ t('appStudio.published.square.shareModalTitle') }}</div>
        <a-button type="text" class="!text-gray-700" size="small" @click="handleCancelShareToSquareModal">
          <template #icon>
            <icon-close />
          </template>
        </a-button>
      </div>
      <!-- 中间表单 -->
      <div class="py-4">
        <div class="flex flex-col gap-2">
          <div class="flex items-center gap-1 text-gray-700">
            {{ t('appStudio.published.square.selectTag') }}
            <div class="text-red-700">*</div>
          </div>
          <a-select v-model="shareCategory" :placeholder="t('appStudio.published.square.selectTagPlaceholder')" class="w-full">
            <a-option v-for="tag in categories" :key="tag.id" :value="tag.id" :label="getCategoryDisplayName(tag)" />
          </a-select>
          <div class="text-xs text-gray-500 mt-2">
            {{ t('appStudio.published.square.shareModalHint') }}
          </div>
        </div>
      </div>
      <!-- 底部按钮 -->
      <div class="flex items-center justify-end gap-3 mt-4">
        <a-button class="rounded-lg" @click="handleCancelShareToSquareModal">{{ t('common.actions.cancel') }}</a-button>
        <a-button type="primary" class="rounded-lg" @click="handleSubmitShareToSquare">
          {{ t('appStudio.published.square.confirmShare') }}
        </a-button>
      </div>
    </a-modal>
  </div>
</template>

<style scoped></style>
