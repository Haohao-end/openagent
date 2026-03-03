<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch, inject } from 'vue'
import { Message, type ValidatedError } from '@arco-design/web-vue'
import { cloneDeep, debounce } from 'lodash'

type StartInputField = {
  name: string
  type: string
  description: string
  required: boolean
}

type StartNodeForm = {
  id: string
  type: string
  title: string
  description: string
  inputs: StartInputField[]
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
const form = ref<StartNodeForm>({
  id: '',
  type: '',
  title: '',
  description: '',
  inputs: [],
})
const isSyncingForm = ref(false)

// 注入只读状态
const isReadonly = inject<boolean>('isReadonly', false)

const debounceAutoSave = debounce(() => {
  // 只读模式下不自动保存
  if (isReadonly) return
  void onSubmit({ errors: undefined })
}, 800)

// 2.定义添加字段函数
const addFormInputField = () => {
  form.value?.inputs.push({ name: '', type: 'string', description: '', required: true })
  Message.success('新增输入字段成功')
}

// 3.定义删除字段函数
const removeFormInputField = (idx: number) => {
  form.value?.inputs?.splice(idx, 1)
}

// 4.定义表单提交函数
const onSubmit = async ({ errors }: { errors: Record<string, ValidatedError> | undefined }) => {
  // 4.1 检查表单是否出现错误，如果出现错误则直接结束
  if (errors) return

  // 4.2 深度拷贝图草稿配置
  const cloneNode = cloneDeep(props.node)

  // 4.3 数据校验通过，通过事件触发数据更新
  emits('updateNode', {
    id: cloneNode.id,
    title: form.value.title,
    description: form.value.description,
    inputs: cloneDeep(form.value.inputs),
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
    form.value = {
      id: newNode.id,
      type: newNode.type,
      title: newNode.data.title,
      description: newNode.data.description,
      inputs: [...cloneDeep(newNode.data.inputs)],
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
  <div
    v-if="props.visible"
    id="start-node-info"
    class="absolute top-0 right-0 bottom-0 w-[400px] border-l z-50 bg-white overflow-scroll scrollbar-w-none p-3"
  >
    <!-- 只读模式提示横幅 -->
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
        <a-avatar :size="30" shape="square" class="bg-blue-700 rounded-lg flex-shrink-0">
          <icon-home />
        </a-avatar>
        <a-input
          v-model:model-value="form.title"
          :disabled="isReadonly"
          placeholder="请输入标题"
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
      :disabled="isReadonly"
      class="rounded-lg text-gray-700 !text-xs"
      placeholder="输入描述..."
    />
    <!-- 分隔符 -->
    <a-divider class="my-2" />
    <!-- 输入数据容器 -->
    <div class="">
      <!-- 容器header -->
      <div class="flex items-center justify-between mb-2">
        <!-- 左侧标题 -->
        <div class="flex items-center gap-2 text-gray-700 font-semibold">
          <div class="">输入参数</div>
          <a-tooltip
            content="定义组件运行时的输入参数，大模型调用该组件时，将根据此信息抽取输入参数"
          >
            <icon-question-circle />
          </a-tooltip>
        </div>
        <!-- 右侧新增字段按钮 -->
        <a-button
          v-if="!isReadonly"
          type="text"
          size="mini"
          class="!text-gray-700"
          @click="() => addFormInputField()"
        >
          <template #icon>
            <icon-plus />
          </template>
        </a-button>
      </div>
      <!-- 输入数据列表容器 -->
      <div class="flex flex-col gap-2">
        <!-- 输入数据表单 -->
        <a-form :model="form" :disabled="isReadonly" size="mini" auto-label-width>
          <div class="flex flex-col gap-2">
            <!-- 有数据UI -->
            <div v-for="(input, idx) in form.inputs" :key="idx" class="bg-gray-50 rounded-lg p-3">
              <!-- 变量标题 -->
              <div class="flex items-center justify-between mb-2">
                <!-- 标题 -->
                <div class="flex items-center gap-2 flex-1">
                  <icon-paste :size="16" />
                  <div class="text-gray-700 font-semibold line-clamp-1 break-all">
                    {{ input.name }}
                  </div>
                </div>
                <!-- 删除按钮 -->
                <a-button
                  v-if="!isReadonly"
                  size="mini"
                  type="text"
                  class="!text-gray-700 flex-shrink-0"
                  @click="() => removeFormInputField(idx)"
                >
                  <template #icon>
                    <icon-close />
                  </template>
                </a-button>
              </div>
              <!-- 变量字段 -->
              <a-form-item
                :field="`inputs[${idx}].name`"
                label="参数名称"
                required
                asterisk-position="end"
              >
                <a-input v-model="input.name" size="small" placeholder="请输入变量名称" />
              </a-form-item>
              <a-form-item
                :field="`inputs[${idx}].type`"
                label="变量类型"
                required
                asterisk-position="end"
              >
                <a-select size="mini" v-model="input.type">
                  <a-option value="string">STRING</a-option>
                  <a-option value="int">INT</a-option>
                  <a-option value="float">FLOAT</a-option>
                  <a-option value="boolean">BOOLEAN</a-option>
                </a-select>
              </a-form-item>
              <a-form-item
                :field="`inputs[${idx}].description`"
                label="参数描述"
                required
                asterisk-position="end"
              >
                <a-textarea
                  :auto-size="{ minRows: 3, maxRows: 3 }"
                  v-model="input.description"
                  size="small"
                  placeholder="请准确描述该参数锁代表的含义，这将帮助大模型更好理解用户意图。"
                />
              </a-form-item>
              <a-form-item
                :field="`inputs[${idx}].required`"
                label="是否必填"
                required
                asterisk-position="end"
              >
                <a-switch size="small" v-model="input.required" />
              </a-form-item>
            </div>
            <!-- 没数据UI -->
            <a-empty v-if="form?.inputs.length <= 0" class="my-4">该节点暂无输入数据</a-empty>
          </div>
        </a-form>
      </div>
    </div>
  </div>
</template>

<style>
#start-node-info {
  .arco-textarea {
    @apply !text-xs;
  }
}
</style>
