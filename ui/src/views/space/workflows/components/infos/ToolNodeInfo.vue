<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch, inject } from 'vue'
import { useVueFlow } from '@vue-flow/core'
import { cloneDeep, debounce } from 'lodash'
import { getReferencedVariables } from '@/utils/helper'
import { apiPrefix } from '@/config'
import { useGetBuiltinTool, useGetBuiltinTools, useGetCategories } from '@/hooks/use-builtin-tool'
import { useGetApiToolProvidersWithPage } from '@/hooks/use-tool'
import type { ValidatedError } from '@arco-design/web-vue'

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

type ToolNodeInputField = {
  name: string
  type: string
  value: {
    type: string
    content: {
      ref_node_id: string
      ref_var_name: string
    }
  }
}

type ToolFormInputField = {
  name: string
  type: string
  value_type: string
  content?: unknown
  ref: string
}

type ToolParam = {
  key: string
  value: unknown
}

type ToolNodeForm = {
  id: string
  type: string
  title: string
  description: string
  tool: ToolSelection
  params: ToolParam[]
  inputs: ToolFormInputField[]
  outputs: Array<Record<string, unknown>>
}

// 1.定义自定义组件所需数据
const props = defineProps({
  visible: { type: Boolean, required: true, default: false },
  node: {
    type: Object,
    required: true,
    default: () => {
      return {}
    },
  },
  loading: { type: Boolean, required: true, default: false },
})
const emits = defineEmits(['update:visible', 'updateNode'])
const { nodes, edges } = useVueFlow()
const {
  loading: getApiToolProvidersLoading,
  paginator,
  api_tool_providers,
  loadApiToolProviders,
} = useGetApiToolProvidersWithPage()
const { builtin_tool, loadBuiltinTool } = useGetBuiltinTool()
const { builtin_tools, loadBuiltinTools } = useGetBuiltinTools()
const { categories, loadCategories } = useGetCategories()
const form = ref<ToolNodeForm>({
  id: '',
  type: '',
  title: '',
  description: '',
  tool: {
    type: 'api_tool',
    provider: { id: '', name: '', label: '', icon: '', description: '' },
    tool: { id: '', name: '', label: '', description: '', params: {} },
  },
  params: [],
  inputs: [],
  outputs: [],
})
const isSyncingForm = ref(false)

// 注入只读状态
const isReadonly = inject<boolean>('isReadonly', false)
const debounceAutoSave = debounce(() => {
  // 只读模式下不自动保存
  if (isReadonly) return
  void onSubmit({ errors: undefined })
}, 800)
const toolsModalVisible = ref(false)
const toolsActivateType = ref('api_tool')
const toolsActivateCategory = ref('all')
const computedBuiltinTools = computed(() => {
  if (toolsActivateCategory.value === 'all') return builtin_tools.value
  return builtin_tools.value.filter((item: { category: string }) => item.category === toolsActivateCategory.value)
})
const pythonTypeMap: Record<string, string> = {
  str: 'string',
  int: 'int',
  float: 'float',
  bool: 'boolean',
}
const defaultToolMeta: ToolSelection = {
  type: 'api_tool',
  provider: { id: '', name: '', label: '', icon: '', description: '' },
  tool: { id: '', name: '', label: '', description: '', params: {} },
}

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

// 2.定义节点可引用的变量选项
const inputRefOptions = computed(() => {
  return getReferencedVariables(cloneDeep(nodes.value), cloneDeep(edges.value), props.node.id)
})

// 3.定义显示工具列表模态窗
const handleShowToolsModal = async () => {
  // 3.1 显示模态窗
  toolsModalVisible.value = true

  // 3.2 调用API接口获取响应
  await loadApiToolProviders(true)
  await loadBuiltinTools()
}

// 4.定义移除绑定工具的函数
const removeBindTool = () => {
  form.value.tool = defaultToolMeta
  form.value.params = []
  form.value.inputs = []
}

// 5.定义是否关联工具判断函数
const isToolSelected = (provider: ToolProvider, tool: ToolMeta) => {
  return (
    form.value.tool?.provider?.name === provider.name && form.value.tool?.tool.name === tool.name
  )
}

// 6.定义工具选择处理器
const handleSelectTool = async (provider_idx: number, tool_idx: number) => {
  // 6.1 根据不同的工具类型执行不同的操作
  let selectTool: ToolSelection
  if (toolsActivateType.value === 'api_tool') {
    // 6.2 获取api工具提供者+工具本身，并更新selectTool
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
    // 6.3 获取内置工具提供者+内置工具，并提取选择工具
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
        }, {}),
      },
    }
  }

  // 6.4 检测是删除还是新增
  if (
    form.value?.tool?.provider?.id === selectTool.provider.id &&
    form.value?.tool?.tool?.name === selectTool.tool.name
  ) {
    // 6.5 删除关联工具
    form.value.tool = defaultToolMeta
    form.value.inputs = []
    form.value.params = []
  } else {
    // 6.6 新增数据，并调用API接口获取工具详情信息
    form.value.tool = selectTool

    // 6.7 根据不同的工具类型调用API接口获取工具的输入
    if (selectTool.type === 'builtin_tool') {
      // 6.8 调用hooks获取内置工具信息，并提取inputs+params
      await loadBuiltinTool(selectTool.provider.name, selectTool.tool.name)
      const inputs = builtin_tool.value.inputs
      const params = builtin_tool.value.params

      // 6.9 更新inputs+params
      form.value.inputs = inputs.map((item: { name: string; type: string }) => {
        return {
          name: item.name,
          type: pythonTypeMap[item.type] || 'string',
          value_type: 'ref', // 工具调用参数默认设置为引用
          content: '',
          ref: '',
        }
      })
      form.value.params = params.map((param: { name: string; default: unknown }) => {
        return { key: param.name, value: param.default }
      })
    } else {
      // 6.10 自定义插件直接使用列表数据中的inputs，无需再次调用API
      const apiToolProvider = api_tool_providers.value[provider_idx]
      const apiTool = apiToolProvider['tools'][tool_idx]
      const inputs = apiTool.inputs || []

      // 6.11 更新inputs+params
      form.value.inputs = inputs.map((item: { name: string; type: string }) => {
        return {
          name: item.name,
          type: pythonTypeMap[item.type] || 'string',
          value_type: 'ref', // 工具调用参数默认设置为引用
          content: '',
          ref: '',
        }
      })
      form.value.params = []
    }
  }
}

// 7.滚动加载api工具列表
const handleScroll = async (event: UIEvent) => {
  // 7.1 获取滚动距离、可滚动的最大距离、客户端/浏览器窗口的高度
  const { scrollTop, scrollHeight, clientHeight } = event.target as HTMLElement

  // 7.2 判断是否滑动到底部
  if (scrollTop + clientHeight >= scrollHeight - 10) {
    if (getApiToolProvidersLoading.value) {
      return
    }
    await loadApiToolProviders()
  }
}

// 7.3 定义表单提交函数
const onSubmit = async ({ errors }: { errors: Record<string, ValidatedError> | undefined }) => {
  // 7.4 检查表单是否出现错误，如果出现错误则直接结束
  if (errors) return

  // 7.5 深度拷贝表单数据内容
  const cloneInputs = cloneDeep(form.value.inputs)
  const cloneParams = cloneDeep(form.value.params)
  const params: Record<string, unknown> = {}
  cloneParams.forEach((param: ToolParam) => {
    params[param.key] = param.value
  })

  // 7.6 数据校验通过，通过事件触发数据更新
  emits('updateNode', {
    id: props.node.id,
    title: form.value.title,
    description: form.value.description,
    tool_type: form.value.tool?.type,
    provider_id: form.value.tool?.provider.id,
    tool_id: form.value.tool?.tool.name,
    meta: cloneDeep(form.value.tool),
    params: params, // 将列表转换成字典
    inputs: cloneInputs.map((input: ToolFormInputField) => {
      return {
        name: input.name,
        description: '',
        required: true,
        type: input.value_type === 'ref' ? 'string' : input.type,
        value: {
          type: input.value_type === 'ref' ? 'ref' : 'literal',
          content:
            input.value_type === 'ref'
              ? {
                  ref_node_id: input.ref.split('/')[0] || '',
                  ref_var_name: input.ref.split('/')[1] || '',
                }
              : input.content,
        },
        meta: {},
      }
    }),
    outputs: cloneDeep(form.value.outputs),
  })
}

// 8.监听数据，将数据映射到表单模型上
watch(
  () => props.node?.id,
  () => {
    const newNode = props.node
    if (!newNode?.id) return
    isSyncingForm.value = true
    debounceAutoSave.flush()
    debounceAutoSave.cancel()
    const cloneInputs = cloneDeep(newNode.data.inputs)
    const cloneParams = cloneDeep(newNode.data.params) as Record<string, unknown>
    form.value = {
      id: newNode.id,
      type: newNode.type,
      title: newNode.data.title,
      description: newNode.data.description,
      tool: (cloneDeep(newNode.data.meta) as ToolSelection) ?? defaultToolMeta,
      params: Object.entries(cloneParams).map(([key, value]) => ({
        key: key,
        value: value,
      })), // 将字典转换成列表
      inputs: cloneInputs.map((input: ToolNodeInputField) => {
        // 8.1 计算引用的变量值信息
        const ref =
          input.value.type === 'ref'
            ? `${input.value.content.ref_node_id}/${input.value.content.ref_var_name}`
            : ''

        // 8.2 判断引用的变量值信息是否存在，如果不存在则设置为空
        let refExists = false
        if (input.value.type === 'ref') {
          for (const inputRefOption of inputRefOptions.value) {
            for (const option of inputRefOption.options) {
              if (option.value === ref) {
                refExists = true
                break
              }
            }
          }
        }
        return {
          name: input.name, // 变量名
          type: input.type,
          value_type: input.value.type === 'literal' ? input.type : 'ref', // 数据类型(涵盖ref/string/int/float/boolean
          content: input.value.type === 'literal' ? input.value.content : '', // 变量值内容
          ref: input.value.type === 'ref' && refExists ? ref : '', // 变量引用信息，存储引用节点id+引用变量名
        }
      }),
      outputs: [{ name: 'text', type: 'string', value: { type: 'generated', content: '' } }],
    }
    nextTick(() => {
      isSyncingForm.value = false
    })
  },
  { immediate: true },
)

watch(
  form,
  () => {
    if (isSyncingForm.value) return
    debounceAutoSave()
  },
  { deep: true },
)

onBeforeUnmount(() => {
  debounceAutoSave.flush()
  debounceAutoSave.cancel()
})

onMounted(() => {
  // 加载内置工具分类
  loadCategories()
})
</script>

<template>
  <div
    id="tool-node-info"
    class="absolute top-0 right-0 bottom-0 w-[400px] border-l z-50 bg-white overflow-scroll scrollbar-w-none p-3"
  >    <!-- 只读模式提示横幅 -->
    <div v-if="isReadonly" class="mb-3 p-3 bg-orange-50 border border-orange-200 rounded-lg">
      <div class="flex items-center gap-2 text-orange-700">
        <icon-lock class="flex-shrink-0" />
        <span class="text-sm font-medium">预览模式：所有配置仅供查看，无法修改</span>
      </div>
    </div>


    <!-- 顶部标题信息 -->
    <div class="flex items-center justify-between gap-3 mb-2">
      <!-- 左侧标题 -->
      <div class="flex items-center gap-1 flex-1">
        <a-avatar :size="30" shape="square" class="bg-orange-500 rounded-lg flex-shrink-0">
          <icon-tool />
        </a-avatar>
        <a-input
          v-model:model-value="form.title"
          :disabled="isReadonly" placeholder="请输入标题"
          class="!bg-white text-gray-700 font-semibold px-2"
        />
      </div>
      <!-- 右侧关闭按钮 -->
      <a-button
        type="text"
        size="mini"
        class="!text-gray700 flex-shrink-0"
        @click="() => emits('update:visible', false)"
      >
        <template #icon>
          <icon-close />
        </template>
      </a-button>
    </div>
    <!-- 描述信息 -->
    <a-textarea
      :auto-size="{ minRows: 3, maxRows: 5 }"
      v-model="form.description"
      :disabled="isReadonly" class="rounded-lg text-gray-700 !text-xs"
      placeholder="输入描述..."
    />
    <!-- 分隔符 -->
    <a-divider class="my-2" />
    <!-- 表单信息 -->
    <a-form size="mini" :model="form" :disabled="isReadonly" layout="vertical">
      <!-- 绑定插件 -->
      <div class="flex flex-col gap-2">
        <!-- 标题&操作按钮 -->
        <div class="flex items-center justify-between">
          <!-- 左侧标题 -->
          <div class="flex items-center gap-2 text-gray-700 font-semibold">
            <div class="">绑定插件</div>
            <a-tooltip content="为工具节点绑定指定的扩展插件，支持插件广场以及自定义API插件。">
              <icon-question-circle />
            </a-tooltip>
          </div>
          <!-- 右侧绑定工具按钮 -->
          <a-button v-if="!isReadonly" type="text" size="mini" class="!text-gray-700" @click="handleShowToolsModal">
            <template #icon>
              <icon-plus />
            </template>
          </a-button>
        </div>
        <div v-if="form.tool?.provider?.id && form.tool?.tool?.name" class="flex flex-col gap-1">
          <div
            class="flex items-center justify-between bg-white p-3 rounded-lg cursor-pointer hover:shadow-sm group border"
          >
            <!-- 左侧工具信息 -->
            <div class="flex items-center gap-2">
              <!-- 图标 -->
              <a-avatar
                :size="36"
                shape="square"
                class="rounded flex-shrink-0"
                :image-url="normalizeIconUrl(form?.tool?.provider?.icon)"
              />
              <!-- 名称与描述信息 -->
              <div class="flex flex-col flex-1 gap-1 h-9">
                <div class="text-gray-700 font-bold leading-[18px] line-clamp-1 break-all">
                  {{ form?.tool?.provider?.label }}/{{ form?.tool?.tool?.name }}
                </div>
                <div class="text-gray-500 text-xs line-clamp-1 break-all">
                  {{ form?.tool?.tool?.description }}
                </div>
              </div>
            </div>
            <!-- 右侧删除按钮 -->
            <a-button
              v-if="!isReadonly"
              size="mini"
              type="text"
              class="hidden group-hover:block flex-shrink-0 ml-2 !text-red-700 rounded"
              @click="() => removeBindTool()"
            >
              <template #icon>
                <icon-delete />
              </template>
            </a-button>
          </div>
        </div>
        <div v-else class="text-xs text-gray-500 leading-[22px]">
          插件能够让工作流调用外部API，例如搜索信息、浏览网页、生成图片等，扩展工作流的能力和使用场景。
        </div>
      </div>
      <a-divider class="my-4" />
      <!-- 输入参数 -->
      <div class="flex flex-col gap-2">
        <!-- 标题&操作按钮 -->
        <div class="flex items-center justify-between">
          <!-- 左侧标题 -->
          <div class="flex items-center gap-2 text-gray-700 font-semibold">
            <div class="">输入数据</div>
            <a-tooltip
              content="输入给大模型的参数，可在下方提示词中引用。所有输入参数会被转为string输入。"
            >
              <icon-question-circle />
            </a-tooltip>
          </div>
        </div>
        <!-- 字段名 -->
        <div class="flex items-center gap-1 text-xs text-gray-500 mb-2">
          <div class="w-[30%]">参数名</div>
          <div class="w-[25%]">类型</div>
          <div class="w-[45%]">值</div>
        </div>
        <!-- 循环遍历字段列表 -->
        <div v-for="(input, idx) in form?.inputs" :key="idx" class="flex items-center gap-1">
          <div class="w-[30%] flex-shrink-0">
            <div class="flex items-center gap-1 text-xs text-gray-500">
              <div class="">{{ input.name }}</div>
              <div class="text-gray-500 bg-gray-200 px-1 py-0.5 rounded">{{ input.type }}</div>
            </div>
          </div>
          <div class="w-[25%] flex-shrink-0">
            <a-select
              size="mini"
              v-model="input.value_type"
              class="px-2"
              :options="[
                { label: '引用', value: 'ref' },
                { label: '直接输入', value: 'literal' },
              ]"
            />
          </div>
          <div class="w-[45%] flex-shrink-0 flex items-center gap-1">
            <a-input
              v-if="input.value_type !== 'ref'"
              size="mini"
              v-model="input.content"
              placeholder="请输入参数值"
            />
            <a-select
              v-else
              placeholder="请选择引用变量"
              size="mini"
              tag-nowrap
              v-model="input.ref"
              :options="inputRefOptions"
            />
          </div>
        </div>
        <!-- 空数据状态 -->
        <a-empty v-if="form?.inputs.length <= 0" class="my-4">该节点暂无输入数据</a-empty>
      </div>
      <a-divider class="my-4" />
      <!-- PARAMS参数 -->
      <div class="flex flex-col gap-2">
        <!-- 标题&操作按钮 -->
        <div class="flex items-center justify-between">
          <!-- 左侧标题 -->
          <div class="flex items-center gap-2 text-gray-700 font-semibold">
            <div class="">PARAMS参数</div>
            <a-tooltip content="内置工具使用的PARAMS参数，用于初始化内置工具。">
              <icon-question-circle />
            </a-tooltip>
          </div>
        </div>
        <!-- 字段名 -->
        <div
          v-if="form?.params?.length > 0"
          class="flex items-center gap-1 text-xs text-gray-500 mb-2"
        >
          <div class="w-[20%]">参数名</div>
          <div class="w-[80%]">值</div>
        </div>
        <!-- 循环遍历字段列表 -->
        <div v-for="(param, idx) in form?.params" :key="idx" class="flex items-center gap-1">
          <div class="w-[20%] flex-shrink-0">
            <div class="flex items-center gap-1 text-xs text-gray-500">
              <div class="">{{ param.key }}</div>
            </div>
          </div>
          <div class="w-[80%] flex-shrink-0">
            <a-input size="mini" v-model="param.value" placeholder="请输入参数值" />
          </div>
        </div>
        <!-- 空数据状态 -->
        <a-empty v-if="form?.params.length <= 0" class="my-4">该工具暂无PARAMS数据</a-empty>
      </div>
      <a-divider class="my-4" />
      <!-- 输出参数 -->
      <div class="flex flex-col gap-2">
        <!-- 输出标题 -->
        <div class="font-semibold text-gray-700">输出数据</div>
        <!-- 字段标题 -->
        <div class="text-gray-500 text-xs">参数名</div>
        <!-- 输出参数列表 -->
        <div v-for="(output, idx) in form?.outputs" :key="idx" class="flex flex-col gap-2">
          <div class="flex items-center gap-2">
            <div class="text-gray-700">{{ output.name }}</div>
            <div class="text-gray-500 text-xs bg-gray-200 px-1 py-0.5 rounded">
              {{ output.type }}
            </div>
          </div>
        </div>
      </div>
    </a-form>
    <!-- 选择工具模态窗 -->
    <a-modal
      v-model:visible="toolsModalVisible"
      hide-title
      :footer="false"
      class="tools-modal"
      modal-class="right-4 h-[calc(100vh-32px)]"
    >
      <div class="flex w-full h-full">
        <!-- 左侧导航菜单 -->
        <div
          class="flex flex-col flex-shrink-0 bg-gray-50 w-[200px] h-full px-3 py-4 overflow-scroll scrollbar-w-none"
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
            <a-button
              size="mini"
              type="text"
              class="!text-gray-700 ml-6"
              @click="() => (toolsModalVisible = false)"
            >
              <template #icon>
                <icon-close />
              </template>
            </a-button>
          </div>
          <!-- 内置工具列表 -->
          <div
            v-if="toolsActivateType === 'builtin_tool'"
            class="h-[calc(100vh-130px)] overflow-scroll scrollbar-w-none"
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
                    @click="() => handleSelectTool(builtin_tool_idx, tool_idx)"
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
              class="block h-[calc(100vh-130px)] overflow-scroll scrollbar-w-none"
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
                      @click="() => handleSelectTool(Number(api_tool_provider_idx), tool_idx)"
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
.tool-setting-modal {
  .arco-modal-wrapper {
    @apply text-right;
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
</style>
