<script setup lang="ts">
import { computed, onMounted, type PropType, ref } from 'vue'
import { type GetDraftAppConfigResponse } from '@/models/app'
import { useUpdateDraftAppConfig } from '@/hooks/use-app'
import { useGetApiTool, useGetApiToolProvidersWithPage } from '@/hooks/use-tool'
import { useGetBuiltinTool, useGetBuiltinTools, useGetCategories } from '@/hooks/use-builtin-tool'
import { apiPrefix, typeMap } from '@/config'
import { Message } from '@arco-design/web-vue'
type ToolProvider = {
  id: string
  name: string
  label: string
  icon: string
  description: string
}

type ToolMeta = {
  id: string
  name: string
  label: string
  description: string
  params: Record<string, unknown>
}

type ToolSelection = {
  type: string
  provider: ToolProvider
  tool: ToolMeta
}

type ToolInputItem = {
  name: string
  type: string
  required?: boolean
  description?: string
}

type ToolParamItem = {
  name: string
  label?: string
  required?: boolean
  type: string
  default?: unknown
  options?: Array<{ label: string; value: string | number | boolean }>
  min?: number
  max?: number
}

type ToolInfoState = {
  type: string
  provider: ToolProvider
  tool: {
    id: string
    name: string
    label: string
    description: string
    inputs: ToolInputItem[]
    params: ToolParamItem[]
  }
}

const defaultToolInfo: ToolInfoState = {
  type: '',
  provider: {
    id: '',
    name: '',
    label: '',
    icon: '',
    description: '',
  },
  tool: {
    id: '',
    name: '',
    label: '',
    description: '',
    inputs: [],
    params: [],
  },
}

// 1.定义自定义组件所需数据
const props = defineProps({
  app_id: { type: String, default: '', required: true },
  tools: {
    type: Array as PropType<GetDraftAppConfigResponse['data']['tools']>,
    default: () => [],
    required: true,
  },
})
const emits = defineEmits(['update:tools'])
const { loading: updateDraftAppConfigLoading, handleUpdateDraftAppConfig } =
  useUpdateDraftAppConfig()
const { loading: getApiToolLoading, api_tool, loadApiTool } = useGetApiTool()
const {
  loading: getApiToolProvidersLoading,
  paginator,
  api_tool_providers,
  loadApiToolProviders,
} = useGetApiToolProvidersWithPage()
const { loading: getBuiltinToolLoading, builtin_tool, loadBuiltinTool } = useGetBuiltinTool()
const { categories, loadCategories } = useGetCategories()
const { builtin_tools, loadBuiltinTools } = useGetBuiltinTools()
const toolInfoModalVisible = ref(false)
const toolInfoNavType = ref('info')
const toolInfo = ref<ToolInfoState>(defaultToolInfo)
const toolInfoIdx = ref(-1)
const toolInfoSettingForm = ref<Record<string, unknown>>({})
const toolsModalVisible = ref(false)
const toolsActivateType = ref('api_tool')
const toolsActivateCategory = ref('all')
const computedBuiltinTools = computed(() => {
  if (toolsActivateCategory.value === 'all') return builtin_tools.value
  return builtin_tools.value.filter(
    (item: { category: string }) => item.category === toolsActivateCategory.value,
  )
})

// 统一处理图标地址，兼容绝对地址、相对地址以及 /api 路径
const normalizeIconUrl = (icon: string = '') => {
  if (!icon) return ''
  if (icon.startsWith('data:') || /^https?:\/\//.test(icon)) return icon
  const fallbackOrigin = globalThis.location?.origin ?? 'http://localhost'
  const apiUrl = new URL(apiPrefix, fallbackOrigin)
  const basePath = apiUrl.pathname.replace(/\/+$/, '')
  let path = icon.startsWith('/') ? icon : `/${icon}`

  // 本地开发常见：后端实际无 /api 前缀，但返回了 /api/xxx
  if (path.startsWith('/api/') && !basePath.startsWith('/api')) {
    path = path.replace(/^\/api/, '')
  }

  if (basePath && basePath !== '/' && !path.startsWith(`${basePath}/`)) {
    if (path.startsWith('/api/')) {
      path = path.replace(/^\/api/, '')
    }
    return `${apiUrl.origin}${basePath}${path}`
  }

  return `${apiUrl.origin}${path}`
}

// 2.定义显示工具设置模态窗
const handleShowToolInfoModal = async (idx: number) => {
  // 2.1 获取当前选中的工具
  if (idx === -1) return
  toolInfoIdx.value = idx
  const tool = props.tools[idx]

  // 2.2 检测不同的工具类型调用不同API接口
  if (tool.type === 'builtin_tool') {
    await loadBuiltinTool(tool.provider.name, tool.tool.name)
    toolInfo.value = {
      type: 'builtin_tool',
      provider: {
        id: builtin_tool.value.provider.name,
        icon: `${apiPrefix}/builtin-tools/${builtin_tool.value.provider.name}/icon`,
        name: builtin_tool.value.provider.name,
        label: builtin_tool.value.provider.label,
        description: builtin_tool.value.provider.description,
      },
      tool: {
        id: builtin_tool.value.name,
        name: builtin_tool.value.name,
        label: builtin_tool.value.label,
        description: builtin_tool.value.description,
        inputs: builtin_tool.value.inputs,
        params: builtin_tool.value.params,
      },
    }
  } else {
    await loadApiTool(tool.provider.id, tool.tool.name)
    toolInfo.value = {
      type: 'api_tool',
      provider: {
        id: api_tool.value.provider.id,
        icon: api_tool.value.provider.icon,
        name: api_tool.value.provider.name,
        label: api_tool.value.provider.name,
        description: api_tool.value.provider.description,
      },
      tool: {
        id: api_tool.value.name,
        name: api_tool.value.name,
        label: api_tool.value.name,
        description: api_tool.value.description,
        inputs: api_tool.value.inputs,
        params: [],
      },
    }
  }

  // 2.3 更新工具设置表单，从草稿中获取配置，如果没有则设置默认值
  const params = tool.tool.params
  toolInfo.value.tool.params.forEach((param: { name: string; default?: unknown }) => {
    toolInfoSettingForm.value[param.name] = params[param.name] ?? param.default
  })

  // 2.3 显示模态窗
  toolInfoModalVisible.value = true
}

// 3.定义关闭工具设置模态窗
const handleCancelToolInfoModal = () => {
  toolInfoIdx.value = -1
  toolInfoModalVisible.value = false
  toolInfoNavType.value = 'info'
}

// 4.定义提交工具设置模态窗
const handleSubmitToolInfo = async () => {
  // 4.1 获取当前工具信息
  const tool = props.tools[toolInfoIdx.value]
  if (tool.type === 'api_tool') {
    // 4.2 自定义工具则直接关闭模态窗
    handleCancelToolInfoModal()
    return
  }

  // 4.3 更新草稿配置
  const newTools = [...props.tools]
  newTools[toolInfoIdx.value]['tool']['params'] = toolInfoSettingForm.value
  await handleUpdateDraftAppConfig(props.app_id, {
    tools: newTools.map((item) => {
      return {
        type: item.type,
        params: item['tool']['params'],
        provider_id: item['provider']['id'],
        tool_id: item['tool']['name'],
      }
    }),
  })

  // 4.4 更新成功触发同步事件
  emits('update:tools', newTools)

  // 4.5 关闭模态窗
  handleCancelToolInfoModal()
}

// 5.删除工具处理器
const handleDeleteTool = async (idx: number) => {
  // 5.1 提取props中的数据
  const newTools = [...props.tools]

  // 5.2 剔除数据
  newTools.splice(idx, 1)

  // 5.3 更新提交表单
  await handleUpdateDraftAppConfig(props.app_id, {
    tools: newTools.map((item) => {
      return {
        type: item.type,
        params: item['tool']['params'],
        provider_id: item['provider']['id'],
        tool_id: item['tool']['name'],
      }
    }),
  })

  // 5.4 触发时间更新props
  emits('update:tools', newTools)
}

// 6.定义显示工具列表模态窗
const handleShowToolsModal = async () => {
  // 6.1 显示模态窗
  toolsModalVisible.value = true

  // 6.2 调用API接口获取响应
  await loadApiToolProviders(true)
  await loadBuiltinTools()
}

// 7.滚动加载api工具列表
const handleScroll = async (event: UIEvent) => {
  // 1.获取滚动距离、可滚动的最大距离、客户端/浏览器窗口的高度
  const { scrollTop, scrollHeight, clientHeight } = event.target as HTMLElement

  // 2.判断是否滑动到底部
  if (scrollTop + clientHeight >= scrollHeight - 10) {
    if (getApiToolProvidersLoading.value) {
      return
    }
    await loadApiToolProviders()
  }
}

// 8.定义添加关联扩展处理器
const handleSelectTool = async (provider_idx: number, tool_idx: number) => {
  // 8.1 根据不同的类型获取特定的工具信息
  let selectTool: ToolSelection
  if (toolsActivateType.value === 'api_tool') {
    const apiToolProvider = api_tool_providers.value[provider_idx]
    const apiTool = apiToolProvider['tools'][tool_idx]
    selectTool = {
      type: 'api_tool',
      provider: {
        id: apiToolProvider.id,
        name: apiToolProvider.name,
        label: apiToolProvider.name,
        icon: apiToolProvider.icon,
        description: apiToolProvider.description,
      },
      tool: {
        id: apiTool.name,
        name: apiTool.name,
        label: apiTool.name,
        description: apiTool.description,
        params: {},
      },
    }
  } else {
    const builtinToolProvider = computedBuiltinTools.value[provider_idx]
    const builtinTool = builtinToolProvider['tools'][tool_idx]
    const params = builtinTool['params']
    selectTool = {
      type: 'builtin_tool',
      provider: {
        id: builtinToolProvider.name,
        name: builtinToolProvider.name,
        label: builtinToolProvider.label,
        icon: `${apiPrefix}/builtin-tools/${builtinToolProvider.name}/icon`,
        description: builtinToolProvider.description,
      },
      tool: {
        id: builtinTool.name,
        name: builtinTool.name,
        label: builtinTool.label,
        description: builtinTool.description,
        params: params.reduce((newObj: Record<string, unknown>, item: { name: string; default: unknown }) => {
          newObj[item.name] = item.default
          return newObj
        }, {} as Record<string, unknown>),
      },
    }
  }

  // 8.3 检测是删除还是新增
  if (
    props.tools.some((item) => {
      return item.provider.id === selectTool.provider.id && item.tool.name === selectTool.tool.name
    })
  ) {
    // 8.4 删除关联的工具，筛选数据后更新
    const newTools = [...props.tools].filter((item) => {
      return item.provider.id !== selectTool.provider.id && item.tool.name !== selectTool.tool.name
    })
    await handleUpdateDraftAppConfig(props.app_id, {
      tools: newTools.map((item) => {
        return {
          type: item.type,
          params: item.tool.params,
          provider_id: item.provider.id,
          tool_id: item.tool.name,
        }
      }),
    })

    // 8.5 双向更新数据，不关闭模态窗
    emits('update:tools', newTools)
    return
  } else {
    // 8.6 新增数据，检测关联插件数是否大于等于5
    if (props.tools.length >= 5) {
      Message.warning('一个Agent应用最多关联5个扩展插件')
      return
    }

    // 8.7 添加数据后同步草稿配置
    const newTools = [...props.tools]
    newTools.push(selectTool)
    await handleUpdateDraftAppConfig(props.app_id, {
      tools: newTools.map((item) => {
        return {
          type: item.type,
          params: item.tool.params,
          provider_id: item.provider.id,
          tool_id: item.tool.name,
        }
      }),
    })

    // 8.8 双向更新数据，不关闭模态窗
    emits('update:tools', newTools)
  }
}

// 9.定义是否关联工具判断函数
const isToolSelected = (
  provider: { name: string },
  tool: { name: string },
) => {
  return props.tools.some(
    (item) => item.provider.name === provider.name && item.tool.name === tool.name,
  )
}

onMounted(() => {
  // 加载内置工具分类
  loadCategories()
})
</script>

<template>
  <div class="">
    <!-- 折叠面板 -->
    <a-collapse-item key="tools" class="app-ability-item">
      <template #header>
        <div class="text-gray-700 font-bold">扩展插件</div>
      </template>
      <template #extra>
        <a-button size="mini" type="text" class="!text-gray-700" @click.stop="handleShowToolsModal">
          <template #icon>
            <icon-plus />
          </template>
        </a-button>
      </template>
      <div v-if="props.tools.length > 0" class="flex flex-col gap-1">
        <div
          v-for="(tool, idx) in props.tools"
          :key="idx"
          class="flex items-center justify-between bg-white p-3 rounded-lg cursor-pointer hover:shadow-sm group"
        >
          <!-- 左侧工具信息 -->
          <div class="flex items-center gap-2 min-w-0">
            <!-- 图标 -->
            <a-avatar
              :size="36"
              shape="square"
              class="rounded flex-shrink-0"
              :image-url="normalizeIconUrl(tool.provider.icon)"
            />
            <!-- 名称与描述信息 -->
            <div class="flex flex-col gap-1 h-9 min-w-0">
              <div class="text-gray-700 font-bold leading-[18px] line-clamp-1 min-w-0">
                {{ tool.provider.label }} / {{ tool.tool.label }}
              </div>
              <div class="text-gray-500 text-xs line-clamp-1 min-w-0">
                {{ tool.tool.description }}
              </div>
            </div>
          </div>
          <!-- 右侧按钮 -->
          <div class="hidden group-hover:flex items-center gap-1 flex-shrink-0 ml-2">
            <a-button
              :loading="getApiToolLoading || getBuiltinToolLoading"
              size="mini"
              type="text"
              class="!text-gray-700 rounded"
              @click="async () => await handleShowToolInfoModal(idx)"
            >
              <template #icon>
                <icon-settings />
              </template>
            </a-button>
            <a-button
              :loading="updateDraftAppConfigLoading"
              size="mini"
              type="text"
              class="!text-red-700 rounded"
              @click="async () => await handleDeleteTool(idx)"
            >
              <template #icon>
                <icon-delete />
              </template>
            </a-button>
          </div>
        </div>
      </div>
      <div v-else class="text-xs text-gray-500 leading-[22px]">
        插件能够让智能体调用外部
        API，例如搜索信息、浏览网页、生成图片等，扩展智能体的能力和使用场景。
      </div>
    </a-collapse-item>
    <!-- 工具设置模态窗 -->
    <a-modal
      :visible="toolInfoModalVisible"
      hide-title
      :footer="false"
      class="tool-setting-modal"
      modal-class="right-4 app-side-modal-shell"
      @cancel="handleCancelToolInfoModal"
    >
      <!-- 顶部标题&关闭按钮 -->
      <div class="flex items-center justify-between mb-6">
        <!-- 左侧标题&导航 -->
        <div class="flex items-center">
          <!-- 工具信息 -->
          <div class="flex items-center gap-2">
            <a-avatar :size="24" shape="circle" :image-url="normalizeIconUrl(toolInfo?.provider?.icon)" />
            <div class="text-gray-700 font-bold max-w-[140px] sm:max-w-[200px] line-clamp-1 min-w-0">
              {{ toolInfo?.tool?.label }}
            </div>
          </div>
          <!-- 分隔符 -->
          <div class="mx-4 text-gray-400">
            <icon-oblique-line :size="12" />
          </div>
          <!-- 导航菜单 -->
          <div class="flex items-center gap-6">
            <div
              :class="`text-gray-700 pt-1 cursor-pointer border-blue-700 hover:border-b-4 hover:font-bold transition-all ${toolInfoNavType === 'info' ? 'font-bold border-b-4' : ''}`"
              @click="toolInfoNavType = 'info'"
            >
              信息
            </div>
            <div
              v-if="toolInfo.type === 'builtin_tool' && toolInfo?.tool?.params?.length > 0"
              :class="`text-gray-700 pt-1 cursor-pointer border-blue-700 hover:border-b-4 hover:font-bold transition-all ${toolInfoNavType === 'setting' ? 'font-bold border-b-4' : ''}`"
              @click="toolInfoNavType = 'setting'"
            >
              设置
            </div>
          </div>
        </div>
        <!-- 右侧关闭按钮 -->
        <a-button size="mini" type="text" class="!text-gray-700" @click="handleCancelToolInfoModal">
          <template #icon>
            <icon-close />
          </template>
        </a-button>
      </div>
      <!-- 信息容器 -->
      <div
        v-if="toolInfoNavType === 'info'"
        class="app-modal-section-scroll pb-4"
      >
        <!-- 工具描述 -->
        <div class="text-gray-70 font-bold mb-1">工具描述</div>
        <div class="text-gray-500 text-xs">{{ toolInfo?.tool?.description }}</div>
        <!-- 工具参数 -->
        <div v-if="toolInfo?.tool?.inputs?.length > 0" class="">
          <!-- 分隔符 -->
          <div class="flex items-center gap-2 my-4">
            <div class="text-xs font-bold text-gray-500">参数</div>
            <hr class="flex-1" />
          </div>
          <!-- 参数列表 -->
          <div class="flex flex-col gap-4">
            <div
              v-for="input in toolInfo?.tool?.inputs"
              :key="input.name"
              class="flex flex-col gap-2"
            >
              <!-- 上半部分 -->
              <div class="flex items-center gap-2 text-xs">
                <div class="text-gray-900 font-bold">{{ input.name }}</div>
                <div class="text-gray-500">{{ typeMap[input.type] }}</div>
                <div v-if="input.required" class="text-red-700">必填</div>
              </div>
              <!-- 参数描述信息 -->
              <div class="text-xs text-gray-500">{{ input.description }}</div>
            </div>
          </div>
        </div>
      </div>
      <!-- 设置容器 -->
      <div
        v-if="toolInfoNavType === 'setting'"
        class="app-modal-section-scroll pb-4"
      >
        <a-form v-model:model="toolInfoSettingForm" layout="vertical" class="">
          <a-form-item
            v-for="param in toolInfo?.tool?.params"
            :key="param.name"
            :field="param.name"
          >
            <template #label>
              <div class="flex items-center gap-1">
                <div class="text-gray-700">{{ param.label }}</div>
                <div v-if="param.required" class="text-red-700">*</div>
                <a-tooltip :content="param.label">
                  <icon-info-circle />
                </a-tooltip>
              </div>
            </template>
            <a-select
              v-if="param.type === 'select'"
              :default-value="param.default"
              v-model:model-value="toolInfoSettingForm[param.name]"
              placeholder="请输入参数值"
              :options="param.options"
            />
            <a-input
              v-if="param.type === 'string'"
              placeholder="请输入参数值"
              v-model:model-value="toolInfoSettingForm[param.name]"
              :default-value="param.default"
            />
            <a-input-number
              v-if="param.type === 'number'"
              placeholder="请输入参数值"
              v-model:model-value="toolInfoSettingForm[param.name]"
              :default-value="param.default"
              :min="param.min"
              :max="param.max"
            />
            <a-radio-group
              v-if="param.type === 'boolean'"
              v-model:model-value="toolInfoSettingForm[param.name]"
              :default-value="param.default"
            >
              <a-radio :value="true">开启</a-radio>
              <a-radio :value="false">关闭</a-radio>
            </a-radio-group>
          </a-form-item>
        </a-form>
      </div>
      <!-- 底部按钮 -->
      <div class="flex items-center justify-between">
        <div class=""></div>
        <a-space :size="12">
          <a-button class="rounded-lg" @click="handleCancelToolInfoModal">取消</a-button>
          <a-button
            :loading="updateDraftAppConfigLoading"
            type="primary"
            class="rounded-lg"
            @click="handleSubmitToolInfo"
          >
            保存
          </a-button>
        </a-space>
      </div>
    </a-modal>
    <!-- 选择工具模态窗 -->
    <a-modal
      v-model:visible="toolsModalVisible"
      hide-title
      :footer="false"
      class="tools-modal"
      modal-class="right-4 app-tools-modal-shell"
    >
      <div class="flex w-full h-full flex-col md:flex-row">
        <!-- 左侧导航菜单 -->
        <div
          class="flex flex-col flex-shrink-0 bg-gray-50 w-full md:w-56 lg:w-64 h-full px-3 py-4 overflow-auto scrollbar-w-none"
        >
          <!-- 标题 -->
          <div class="text-gray-900 font-bold text-lg mb-4">关联插件</div>
          <!-- 添加插件按钮 -->
          <router-link :to="{ name: 'space-tools-list', query: { create_type: 'tool' } }">
            <a-button long type="primary" class="rounded-lg mb-5">创建自定义插件</a-button>
          </router-link>
          <!-- 工具类别导航 -->
          <div class="flex flex-col gap-1 mb-4">
            <div
              :class="`rounded-lg h-8 leading-8 px-3 flex items-center gap-2 cursor-pointer hover:bg-white hover:text-blue-700 ${toolsActivateType === 'api_tool' ? 'text-blue-700 bg-white' : 'text-gray-700'}`"
              @click="toolsActivateType = 'api_tool'"
            >
              <icon-code />
              自定义插件
            </div>
            <div
              :class="`rounded-lg h-8 leading-8 px-3 flex items-center gap-2 cursor-pointer hover:bg-white hover:text-blue-700 ${toolsActivateType === 'builtin_tool' ? 'text-blue-700 bg-white' : 'text-gray-700'}`"
              @click="toolsActivateType = 'builtin_tool'"
            >
              <icon-translate />
              内置插件
            </div>
          </div>
          <!-- 内置工具分类 -->
          <div v-if="toolsActivateType === 'builtin_tool'" class="">
            <!-- 分类标题 -->
            <div class="text-xs text-gray-500 mb-3">类别</div>
            <!-- 分类列表 -->
            <div class="flex flex-col gap-1">
              <!-- 所有类别 -->
              <div
                :class="`rounded-lg h-8 leading-8 px-3 flex items-center gap-2 cursor-pointer hover:bg-white hover:text-blue-700 ${toolsActivateCategory === 'all' ? 'text-blue-700 bg-white' : 'text-gray-700'}`"
                @click="toolsActivateCategory = 'all'"
              >
                <icon-apps />
                全部
              </div>
              <div
                v-for="category in categories"
                :key="category.name"
                :class="`rounded-lg h-8 leading-8 px-3 flex items-center gap-2 cursor-pointer hover:bg-white hover:text-blue-700 ${toolsActivateCategory === category.category ? 'text-blue-700 bg-white' : ' text-gray-700'}`"
                @click="toolsActivateCategory = category.category"
              >
                <icon-apps />
                {{ category.name }}
              </div>
            </div>
          </div>
        </div>
        <!-- 右侧工具列表 -->
        <div class="flex-1 p-4">
          <!-- 标题与关闭按钮 -->
          <div class="w-full flex items-center justify-between gap-2 mb-7">
            <div class="text-lg font-bold text-gray-700">
              {{ toolsActivateType === 'api_tool' ? '自定义插件' : '内置插件' }}
            </div>
            <a-button size="mini" type="text" class="!text-gray-700 ml-6">
              <template #icon>
                <icon-close />
              </template>
            </a-button>
          </div>
          <!-- 内置工具列表 -->
          <div
            v-if="toolsActivateType === 'builtin_tool'"
            class="app-modal-list-scroll"
          >
            <div
              v-for="(builtin_tool, builtin_tool_idx) in computedBuiltinTools"
              :key="builtin_tool.name"
              class="flex flex-col gap-3 mb-3"
            >
              <!-- 提供者信息 -->
              <div class="text-gray-900">{{ builtin_tool.label }}</div>
              <!-- 工具列表 -->
              <div class="flex flex-col gap-1">
                <div
                  v-for="(tool, tool_idx) in builtin_tool.tools"
                  :key="tool.name"
                  :class="`flex items-center justify-between px-2 h-8 rounded-lg cursor-pointer hover:bg-gray-50 group ${isToolSelected(builtin_tool, tool) ? 'bg-blue-50 border border-blue-700' : ''}`"
                >
                  <!-- 工具信息 -->
                  <div class="flex items-center gap-2">
                    <a-avatar
                      :size="20"
                      shape="circle"
                      :image-url="`${apiPrefix}/builtin-tools/${builtin_tool.name}/icon`"
                    />
                    <div class="text-gray-900">{{ tool.label }}</div>
                  </div>
                  <!-- 添加按钮 -->
                  <a-button
                    size="mini"
                    class="hidden group-hover:block rounded px-1.5 flex-shrink-0"
                    @click="async () => await handleSelectTool(builtin_tool_idx, tool_idx)"
                  >
                    <template #icon>
                      <icon-plus />
                    </template>
                    {{ isToolSelected(builtin_tool, tool) ? '删除' : '添加' }}
                  </a-button>
                </div>
              </div>
            </div>
            <div v-if="computedBuiltinTools.length === 0" class="">
              <a-empty
                description="没有可用的内置插件"
                class="h-[400px] flex flex-col items-center justify-center"
              />
            </div>
          </div>
          <!-- 自定义插件列表 -->
          <div v-if="toolsActivateType === 'api_tool'">
            <a-spin
              :loading="getApiToolProvidersLoading"
              class="block app-modal-list-scroll"
              @scroll="handleScroll"
            >
              <div
                v-for="(api_tool_provider, api_tool_provider_idx) in api_tool_providers"
                :key="api_tool_provider.id"
                class="flex flex-col gap-3 mb-3"
              >
                <!-- 提供者信息 -->
                <div class="text-gray-900">{{ api_tool_provider.name }}</div>
                <!-- 工具列表 -->
                <div class="flex flex-col gap-1">
                  <div
                    v-for="(tool, tool_idx) in api_tool_provider.tools"
                    :key="tool.name"
                    :class="`flex items-center justify-between px-2 h-8 rounded-lg cursor-pointer hover:bg-gray-50 group ${isToolSelected(api_tool_provider, tool) ? 'bg-blue-50 border border-blue-700' : ''}`"
                  >
                    <!-- 工具信息 -->
                    <div class="flex items-center gap-2">
                      <a-avatar
                        :size="20"
                        shape="circle"
                        :image-url="normalizeIconUrl(api_tool_provider.icon)"
                      />
                      <div class="text-gray-900">{{ tool.name }}</div>
                    </div>
                    <!-- 添加按钮 -->
                    <a-button
                      size="mini"
                      class="hidden group-hover:block rounded px-1.5 flex-shrink-0"
                      @click="
                        async () => await handleSelectTool(Number(api_tool_provider_idx), tool_idx)
                      "
                    >
                      <template #icon>
                        <icon-plus />
                      </template>
                      {{ isToolSelected(api_tool_provider, tool) ? '删除' : '添加' }}
                    </a-button>
                  </div>
                </div>
              </div>
              <div v-if="api_tool_providers.length === 0" class="">
                <a-empty
                  description="没有可用的API插件"
                  class="h-[400px] flex flex-col items-center justify-center"
                />
              </div>
              <!-- 加载器 -->
              <a-row v-if="paginator.total_page >= 2">
                <!-- 加载数据中 -->
                <a-col
                  v-if="getApiToolProvidersLoading"
                  :span="24"
                  class="!text-center"
                >
                  <a-space class="my-4">
                    <a-spin />
                    <div class="text-gray-400">加载中</div>
                  </a-space>
                </a-col>
                <!-- 数据加载完成 -->
                <a-col v-else-if="paginator.current_page > paginator.total_page" :span="24" class="!text-center">
                  <div class="text-gray-400 my-4">数据已加载完成</div>
                </a-col>
              </a-row>
            </a-spin>
          </div>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<style>
.app-side-modal-shell {
  height: calc(100dvh - 32px);
  max-height: calc(100dvh - 32px);
  width: min(96vw, 640px);
}

.app-tools-modal-shell {
  height: calc(100dvh - 32px);
  max-height: calc(100dvh - 32px);
  width: min(96vw, 980px);
}

.app-modal-section-scroll {
  max-height: calc(100dvh - 170px);
  overflow: auto;
}

.app-modal-list-scroll {
  height: calc(100dvh - 130px);
  overflow: auto;
}

.tool-setting-modal {
  .arco-modal-wrapper {
    @apply text-right;
  }

  .arco-modal-body {
    @apply h-full w-full rounded-lg;
  }
}

.tools-modal {
  .arco-modal-wrapper {
    @apply text-right;
  }

  .arco-modal-body {
    @apply h-full w-full rounded-lg p-0;
  }
}

@supports not (height: 100dvh) {
  .app-side-modal-shell {
    height: calc(100vh - 32px);
    max-height: calc(100vh - 32px);
  }

  .app-tools-modal-shell {
    height: calc(100vh - 32px);
    max-height: calc(100vh - 32px);
  }

  .app-modal-section-scroll {
    max-height: calc(100vh - 170px);
  }

  .app-modal-list-scroll {
    height: calc(100vh - 130px);
  }
}
</style>
