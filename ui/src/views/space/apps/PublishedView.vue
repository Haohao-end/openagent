<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { useGetPublishedConfig, useRegenerateWebAppToken } from '@/hooks/use-app'
import { useGetWechatConfig, useUpdateWechatConfig } from '@/hooks/use-platform'
import { shareAppToSquare, unshareAppFromSquare, getAppCategories, type AppCategory } from '@/services/public-app'
import { getErrorMessage } from '@/utils/error'

// 1.定义页面所需数据
const route = useRoute()
const router = useRouter()
const wechatConfigModalVisible = ref(false)
const shareToSquareModalVisible = ref(false)
const shareCategory = ref('')
const categories = ref<AppCategory[]>([])
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

// 3.定义打开微信配置模态窗处理器
const handleShowWechatConfigModal = async () => {
  // 3.1 调用api接口获取微信配置
  await loadWechatConfig(String(route.params?.app_id))

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

// 6.加载应用分类
const loadCategories = async () => {
  try {
    const res = await getAppCategories()
    categories.value = res.data.categories
  } catch (error: unknown) {
    Message.error(getErrorMessage(error, '加载分类失败'))
  }
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
    Message.warning('请选择应用分类')
    return
  }

  try {
    await shareAppToSquare(String(route.params?.app_id), shareCategory.value)
    Message.success('已共享到应用广场')
    shareToSquareModalVisible.value = false
    // 重新加载配置
    await loadPublishedConfig(String(route.params?.app_id))
  } catch (error: unknown) {
    Message.error(getErrorMessage(error, '共享失败'))
  }
}

// 10.取消共享
const handleUnshareFromSquare = async () => {
  try {
    await unshareAppFromSquare(String(route.params?.app_id))
    Message.success('已从应用广场取消共享')
    // 重新加载配置
    await loadPublishedConfig(String(route.params?.app_id))
  } catch (error: unknown) {
    Message.error(getErrorMessage(error, '操作失败'))
  }
}

onMounted(() => {
  loadPublishedConfig(String(route.params?.app_id))
  loadWechatConfig(String(route.params?.app_id))
})
</script>

<template>
  <div class="bg-white flex-1 w-full min-h-0 px-6 py-5">
    <!-- 顶部提示信息 -->
    <a-alert class="mb-5">
      如应用访问链接或二维码意外泄露，请及时重新生成或进行停止分发，避免资源出现异常消耗
    </a-alert>
    <!-- 发布渠道列表 -->
    <a-spin :loading="getPublishedConfigLoading" class="w-full">
      <table class="w-full">
        <thead>
          <tr class="h-10 bg-gray-100">
            <th class="font-normal text-left px-4 text-gray-700 border-r border-white">发布渠道</th>
            <th class="font-normal text-left px-4 text-gray-700 border-r border-white">状态</th>
            <th class="font-normal text-left px-4 text-gray-700">操作</th>
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
                  <div class="text-gray-700 font-semibold">网页版</div>
                  <div class="text-gray-500">可通过访问PC网页立即开始对话。</div>
                </div>
              </div>
            </td>
            <td class="py-3 px-4 w-1/12">
              <a-tag v-if="published_config?.web_app?.status !== 'published'" color="gray" bordered>
                <template #icon>
                  <icon-minus-circle />
                </template>
                未发布
              </a-tag>
              <a-tag v-else color="blue" bordered>
                <template #icon>
                  <icon-check-circle-fill />
                </template>
                已发布
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
                    <template v-else>应用未发布，无可访问链接</template>
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
                    重新生成
                  </a-button>
                </div>
                <!-- 右侧访问按钮 -->
                <a-button class="rounded-lg px-2">
                  <template v-if="published_config?.web_app?.status !== 'published'">
                    立即访问
                  </template>
                  <template v-else>
                    <a :href="webAppUrl" target="_blank" rel="noopener noreferrer">立即访问</a>
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
                  <div class="text-gray-700 font-semibold">应用广场</div>
                  <div class="text-gray-500">将应用共享到应用广场，让更多用户发现和使用。</div>
                </div>
              </div>
            </td>
            <td class="py-3 px-4 w-1/12">
              <a-tag v-if="!published_config?.is_public" color="gray" bordered>
                <template #icon>
                  <icon-minus-circle />
                </template>
                未共享
              </a-tag>
              <a-tag v-else color="blue" bordered>
                <template #icon>
                  <icon-check-circle-fill />
                </template>
                已共享
              </a-tag>
            </td>
            <td class="py-3 px-4">
              <div class="flex items-center gap-3">
                <a-button v-if="!published_config?.is_public" type="primary" class="rounded-lg px-2"
                  @click="handleShowShareToSquareModal">
                  <template #icon>
                    <icon-share-alt />
                  </template>
                  共享到广场
                </a-button>
                <a-button v-else type="outline" status="danger" class="rounded-lg px-2"
                  @click="handleUnshareFromSquare">
                  <template #icon>
                    <icon-close />
                  </template>
                  取消共享
                </a-button>
                <a-button v-if="published_config?.is_public" class="rounded-lg px-2"
                  @click="router.push('/store/public-apps')">
                  <template #icon>
                    <icon-eye />
                  </template>
                  查看广场
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
                  <div class="text-gray-700 font-semibold">微信公众号（订阅号、服务号）</div>
                  <div class="text-gray-500">接入微信公众号，自动回复用户消息，助理高效私域运营。</div>
                </div>
              </div>
            </td>
            <td class="py-3 px-4 w-1/12">
              <a-tag v-if="wechat_config?.status !== 'configured'" color="gray" bordered>
                <template #icon>
                  <icon-minus-circle />
                </template>
                未配置
              </a-tag>
              <a-tag v-else color="blue" bordered>
                <template #icon>
                  <icon-check-circle-fill />
                </template>
                已配置
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
                  立即配置
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
        <div class="text-lg font-bold text-gray-700">微信公众号配置</div>
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
                服务器ip
                <div class="text-red-700">*</div>
              </div>
            </div>
            <div class="text-gray-500">{{ wechat_config?.ip }}</div>
          </div>
          <!-- 服务器地址 -->
          <div class="flex flex-col gap-2">
            <div class="flex flex-col">
              <div class="flex items-center gap-1 text-gray-700">
                服务器地址(URL)
                <div class="text-red-700">*</div>
              </div>
            </div>
            <div class="text-gray-500">{{ wechat_config?.url }}</div>
          </div>
          <!-- 开发者ID(AppID) -->
          <div class="flex flex-col gap-2">
            <div class="flex items-center gap-1 text-gray-700">
              开发者ID(AppID) - 可选
            </div>
            <a-input v-model:model-value="wechatConfigForm.wechat_app_id" placeholder="请填写微信开发者ID" />
          </div>
          <!-- 开发者秘钥(AppSecret) -->
          <div class="flex flex-col gap-2">
            <div class="flex items-center gap-1 text-gray-700">
              开发者秘钥(AppSecret) - 可选
            </div>
            <a-input v-model:model-value="wechatConfigForm.wechat_app_secret" placeholder="请填写微信开发者秘钥" />
          </div>
          <!-- 令牌(Token) -->
          <div class="flex flex-col gap-2">
            <div class="flex items-center gap-1 text-gray-700">
              令牌(Token) 随机生成
            </div>
            <a-input v-model:model-value="wechatConfigForm.wechat_token" placeholder="请填写微信公众号令牌" />
          </div>
        </div>
      </div>
      <!-- 底部按钮 -->
      <div class="flex items-center justify-between">
        <div class=""></div>
        <a-space :size="16">
          <a-button class="rounded-lg" @click="handleCancelWechatConfigModal">取消</a-button>
          <a-button :loading="updateWechatConfigLoading" type="primary" class="rounded-lg"
            @click="handleSubmitWechatConfigModal">
            保存
          </a-button>
        </a-space>
      </div>
    </a-modal>
    <!-- 共享到广场模态窗 -->
    <a-modal :visible="shareToSquareModalVisible" hide-title :footer="false" modal-class="rounded-xl w-[500px]"
      @cancel="handleCancelShareToSquareModal">
      <!-- 顶部标题 -->
      <div class="flex items-center justify-between mb-4">
        <div class="text-lg font-bold text-gray-700">共享到应用广场</div>
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
            选择应用分类
            <div class="text-red-700">*</div>
          </div>
          <a-select v-model="shareCategory" placeholder="请选择应用分类" class="w-full">
            <a-option v-for="cat in categories" :key="cat.value" :value="cat.value" :label="cat.label" />
          </a-select>
          <div class="text-xs text-gray-500 mt-2">
            共享后，您的应用将出现在应用广场，其他用户可以查看和Fork使用。
          </div>
        </div>
      </div>
      <!-- 底部按钮 -->
      <div class="flex items-center justify-end gap-3 mt-4">
        <a-button class="rounded-lg" @click="handleCancelShareToSquareModal">取消</a-button>
        <a-button type="primary" class="rounded-lg" @click="handleSubmitShareToSquare">
          确认共享
        </a-button>
      </div>
    </a-modal>
  </div>
</template>

<style scoped></style>
