<script setup lang="ts">
import { getReferencedVariables } from '@/utils/helper'
import { validatePythonSyntax } from '@/utils/python-validator'
import { type ValidatedError, Message } from '@arco-design/web-vue'
import { useVueFlow } from '@vue-flow/core'
import { cloneDeep, debounce } from 'lodash'
import { computed, defineAsyncComponent, nextTick, onBeforeUnmount, ref, watch, inject } from 'vue'

type NodeInputField = {
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

type CodeFormInputField = {
  name: string
  type: string
  ref: string
  content?: unknown
}

type CodeNodeForm = {
  id: string
  type: string
  title: string
  description: string
  code: string
  inputs: CodeFormInputField[]
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
const FullscreenCodeEditor = defineAsyncComponent(
  () => import('@/components/FullscreenCodeEditor.vue'),
)
const { nodes, edges } = useVueFlow()
const form = ref<CodeNodeForm>({
  id: '',
  type: '',
  title: '',
  description: '',
  code: '',
  inputs: [],
  outputs: [],
})
const isSyncingForm = ref(false)

// 注入只读状态
const isReadonly = inject<boolean>('isReadonly', false)
const fullscreenEditorVisible = ref(false)
const debounceAutoSave = debounce(() => {
  // 只读模式下不自动保存
  if (isReadonly) return
  void onSubmit({ errors: undefined })
}, 800)

// 2.定义输入变量引用选项
const inputRefOptions = computed(() => {
  return getReferencedVariables(cloneDeep(nodes.value), cloneDeep(edges.value), props.node.id)
})

// 2.定义添加表单字段函数
const addFormInputField = () => {
  form.value?.inputs.push({ name: '', type: 'string', content: '', ref: '' })
  Message.success('新增输入字段成功')
}

// 3.定义移除表单字段函数
const removeFormInputField = (idx: number) => {
  form.value?.inputs?.splice(idx, 1)
}

// 4.定义表单添加输出变量函数
const addFormOutputField = () => {
  form.value?.outputs.push({
    name: '',
    description: '',
    required: true,
    type: 'string',
    value: {
      type: 'generated',
      content: '',
    },
    meta: {},
  })
  Message.success('新增输出字段成功')
}

// 5.定义表单移除输出变量函数
const removeFormOutputField = (idx: number) => {
  form.value?.outputs.splice(idx, 1)
}

// 7.打开全屏编辑器
const openFullscreenEditor = () => {
  // 只读模式下不允许编辑
  if (isReadonly) return
  fullscreenEditorVisible.value = true
}

// 8.定义代码编辑器的 placeholder
const codePlaceholder = `# 在此编写 Python 代码
# 示例：
def main(params):
    # 从输入参数中获取变量
    x = int(params.get('x', 0))
    y = int(params.get('y', 0))

    # 执行业务逻辑
    result = x + y

    # 返回结果（参数名需与输出参数一致）
    return {
        'output': result
    }`

const codeValidation = computed(() => {
  return validatePythonSyntax(form.value.code || '')
})

// 9.计算错误数量
const errorCount = computed(() => {
  return codeValidation.value.errors.filter((e) => e.severity === 8).length
})

// 10.计算代码是否有效
const isCodeValid = computed(() => {
  return codeValidation.value.isValid
})

// 11.计算代码预览（前10行）
const codePreview = computed(() => {
  if (!form.value.code) return codePlaceholder
  const lines = form.value.code.split('\n')
  if (lines.length <= 10) return form.value.code
  return lines.slice(0, 10).join('\n') + '\n...'
})

// 4.定义表单提交函数
const onSubmit = async ({ errors }: { errors: Record<string, ValidatedError> | undefined }) => {
  // 4.1 检查表单是否出现错误，如果出现错误则直接结束
  if (errors) return

  // 4.2 深度拷贝表单数据内容
  const cloneInputs = cloneDeep(form.value.inputs)

  // 4.3 数据校验通过，通过事件触发数据更新
  emits('updateNode', {
    id: props.node.id,
    title: form.value.title,
    description: form.value.description,
    code: form.value.code,
    inputs: cloneInputs.map((input: CodeFormInputField) => {
      return {
        name: input.name,
        description: '',
        required: true,
        type: input.type === 'ref' ? 'string' : input.type,
        value: {
          type: input.type === 'ref' ? 'ref' : 'literal',
          content:
            input.type === 'ref'
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

// 5.监听数据，将数据映射到表单模型上
watch(
  () => props.node?.id,
  () => {
    const newNode = props.node
    if (!newNode?.id) return
    isSyncingForm.value = true
    debounceAutoSave.flush()
    debounceAutoSave.cancel()
    const cloneInputs = cloneDeep(newNode.data.inputs)
    form.value = {
      id: newNode.id,
      type: newNode.type,
      title: newNode.data.title,
      description: newNode.data.description,
      code: newNode.data.code,
      inputs: cloneInputs.map((input: NodeInputField) => {
        // 5.1 计算引用的变量值信息
        const ref =
          input.value.type === 'ref'
            ? `${input.value.content.ref_node_id}/${input.value.content.ref_var_name}`
            : ''
        // 5.2 判断引用的变量值信息是否存在
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
          type: input.value.type === 'literal' ? input.type : 'ref', // 数据类型(涵盖ref/string/int/float/boolean
          content: input.value.type === 'literal' ? input.value.content : '', // 变量值内容
          ref: input.value.type === 'ref' && refExists ? ref : '', // 变量引用信息，存储引用节点id+引用变量名
        }
      }),
      outputs: cloneDeep(newNode.data.outputs),
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
</script>

<template>
  <div v-if="props.visible" id="llm-node-info"
    class="absolute top-0 right-0 bottom-0 w-[400px] border-l z-50 bg-white overflow-scroll scrollbar-w-none p-3">    <!-- 只读模式提示横幅 -->
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
        <a-avatar :size="30" shape="square" class="bg-cyan-500 rounded-lg flex-shrink-0">
          <icon-code />
        </a-avatar>
        <a-input v-model:model-value="form.title" :disabled="isReadonly" placeholder="请输入标题"
          class="!bg-white text-gray-700 font-semibold px-2" />
      </div>
      <!-- 右侧关闭按钮 -->
      <a-button type="text" size="mini" class="!text-gray700 flex-shrink-0"
        @click="() => emits('update:visible', false)">
        <template #icon>
          <icon-close />
        </template>
      </a-button>
    </div>
    <!-- 描述信息 -->
    <a-textarea :auto-size="{ minRows: 3, maxRows: 5 }" v-model="form.description" :disabled="isReadonly"
      class="rounded-lg text-gray-700 !text-xs" placeholder="输入描述..." />
    <!-- 分隔符 -->
    <a-divider class="my-2" />
    <!-- 表单信息 -->
    <a-form size="mini" :model="form" :disabled="isReadonly" layout="vertical">
      <!-- 输入参数 -->
      <div class="flex flex-col gap-2">
        <!-- 标题&操作按钮 -->
        <div class="flex items-center justify-between">
          <!-- 左侧标题 -->
          <div class="flex items-center gap-2 text-gray-700 font-semibold">
            <div class="">输入参数</div>
            <a-tooltip content="代码运行的输入变量。代码中可以直接引用此处添加的变量。">
              <icon-question-circle />
            </a-tooltip>
          </div>
          <!-- 右侧新增字段按钮 -->
          <a-button v-if="!isReadonly" type="text" size="mini" class="!text-gray-700" @click="() => addFormInputField()">
            <template #icon>
              <icon-plus />
            </template>
          </a-button>
        </div>
        <!-- 字段名 -->
        <div class="flex items-center gap-1 text-xs text-gray-500 mb-2">
          <div class="w-[20%]">参数名</div>
          <div class="w-[25%]">类型</div>
          <div class="w-[47%]">值</div>
          <div class="w-[8%]"></div>
        </div>
        <!-- 循环遍历字段列表 -->
        <div v-for="(input, idx) in form?.inputs" :key="idx" class="flex items-center gap-1">
          <div class="w-[20%] flex-shrink-0">
            <a-input v-model="input.name" size="mini" placeholder="请输入参数名" class="!px-2" />
          </div>
          <div class="w-[25%] flex-shrink-0">
            <a-select size="mini" v-model="input.type" class="px-2" :options="[
              { label: '引用', value: 'ref' },
              { label: 'STRING', value: 'string' },
              { label: 'INT', value: 'int' },
              { label: 'FLOAT', value: 'float' },
              { label: 'BOOLEAN', value: 'boolean' },
            ]" />
          </div>
          <div class="w-[47%] flex-shrink-0 flex items-center gap-1">
            <a-input v-if="input.type !== 'ref'" size="mini" v-model="input.content" placeholder="请输入参数值" />
            <a-select v-else placeholder="请选择引用变量" size="mini" tag-nowrap v-model="input.ref"
              :options="inputRefOptions" />
          </div>
          <div class="w-[8%] text-right">
            <icon-minus-circle v-if="!isReadonly" class="text-gray-500 hover:text-gray-700 cursor-pointer flex-shrink-0"
              @click="() => removeFormInputField(idx as number)" />
          </div>
        </div>
        <!-- 空数据状态 -->
        <a-empty v-if="form?.inputs.length <= 0" class="my-4">该节点暂无输入数据</a-empty>
      </div>
      <a-divider class="my-4" />
      <!-- 代码 -->
      <div class="flex flex-col gap-3">
        <!-- 标题 -->
        <div class="flex items-center gap-2 text-gray-700 font-semibold">
          <div class="">代码预览</div>
          <a-tooltip content="点击代码区域编辑代码">
            <icon-question-circle />
          </a-tooltip>
        </div>

        <!-- 代码预览区域 -->
        <div
          class="group relative cursor-pointer overflow-hidden rounded-lg border border-gray-300 bg-[#282c34] transition-all hover:border-blue-500 hover:shadow-md"
          @click="openFullscreenEditor"
        >
          <div class="flex items-center justify-between border-b border-gray-700 bg-gray-800 px-3 py-2">
            <div class="flex items-center gap-2">
              <icon-code :size="16" />
              <span class="text-xs text-gray-500">Python</span>
            </div>
            <div class="flex items-center gap-2">
              <a-tag v-show="!isCodeValid" size="small" color="red">
                <template #icon>
                  <icon-exclamation-circle />
                </template>
                {{ errorCount }} 个错误
              </a-tag>
              <a-tag v-show="isCodeValid" size="small" color="green">
                <template #icon>
                  <icon-check-circle />
                </template>
                正常
              </a-tag>
            </div>
          </div>
          <pre class="m-0 max-h-[240px] overflow-hidden p-4 font-mono text-sm leading-[1.6] text-gray-300"><code>{{ codePreview }}</code></pre>
          <div class="absolute inset-0 flex flex-col items-center justify-center bg-black/0 text-white opacity-0 transition-all duration-200 group-hover:bg-black/60 group-hover:opacity-100">
            <icon-expand :size="32" />
            <div class="text-sm mt-2">点击编辑代码</div>
          </div>
        </div>

        <!-- 代码编辑器提示 -->
        <a-alert type="info" class="text-xs">
          <template #icon>
            <icon-info-circle />
          </template>
          <div class="space-y-1">
            <div>• 函数名必须为 <code class="bg-blue-100 px-1 rounded">main(params)</code></div>
            <div>• 使用输入参数中的变量构建逻辑，通过 <code class="bg-blue-100 px-1 rounded">return</code> 返回字典对象</div>
            <div>• 返回的参数名和类型需与下方"输出参数"保持一致</div>
          </div>
        </a-alert>
      </div>
      <a-divider class="my-4" />

      <!-- 全屏代码编辑器 -->
      <fullscreen-code-editor
        v-model:visible="fullscreenEditorVisible"
        v-model="form.code"
        :title="`编辑代码 - ${form.title}`"
      />
      <!-- 输出参数 -->
      <div class="flex flex-col gap-2">
        <!-- 标题&操作按钮 -->
        <div class="flex items-center justify-between">
          <!-- 左侧标题 -->
          <div class="flex items-center gap-2 text-gray-700 font-semibold">
            <div class="">输出参数</div>
            <a-tooltip content="代码运行后的输出变量。此处的变量名、变量类型必须与代码中 return 结果一致。">
              <icon-question-circle />
            </a-tooltip>
          </div>
          <!-- 右侧新增字段按钮 -->
          <a-button type="text" size="mini" class="!text-gray-700" @click="() => addFormOutputField()">
            <template #icon>
              <icon-plus />
            </template>
          </a-button>
        </div>
        <!-- 字段名 -->
        <div class="flex items-center gap-1 text-xs text-gray-500 mb-2">
          <div class="w-[46%]">参数名</div>
          <div class="w-[46%]">类型</div>
          <div class="w-[8%]"></div>
        </div>
        <!-- 循环遍历字段列表 -->
        <div v-for="(output, idx) in form?.outputs" :key="idx" class="flex items-center gap-1">
          <div class="w-[46%] flex-shrink-0">
            <a-input v-model="output.name" size="mini" placeholder="请输入参数名" class="!px-2" />
          </div>
          <div class="w-[46%] flex-shrink-0">
            <a-select size="mini" v-model="output.type" class="px-2" :options="[
              { label: 'STRING', value: 'string' },
              { label: 'INT', value: 'int' },
              { label: 'FLOAT', value: 'float' },
              { label: 'BOOLEAN', value: 'boolean' },
            ]" />
          </div>
          <div class="w-[8%] text-right">
            <icon-minus-circle class="text-gray-500 hover:text-gray-700 cursor-pointer flex-shrink-0"
              @click="() => removeFormOutputField(idx as number)" />
          </div>
        </div>
        <!-- 空数据状态 -->
        <a-empty v-if="form?.outputs?.length <= 0" class="my-4">该节点暂无输出数据</a-empty>
      </div>
    </a-form>
  </div>
</template>

<style>
#llm-node-info {
  .arco-select-option-content {
    @apply !text-xs;
  }
}
</style>
