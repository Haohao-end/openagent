<script setup lang="ts">
import { onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { type FileItem, type Form, Message } from '@arco-design/web-vue'
import { useCreateDocuments, useGetDocumentsStatus } from '@/hooks/use-dataset'
import { useUploadFile } from '@/hooks/use-upload-file'
import { unescapeString } from '@/utils/helper'
import type { CreateDocumentsRequest, GetDocumentsStatusResponse } from '@/models/dataset'

type DocumentProcessType = 'automatic' | 'custom'

type CustomRuleForm = {
  separators: string[]
  chunk_size: number
  chunk_overlap: number
  pre_process_rules: string[]
}

type CreateDocumentsForm = {
  file_list: FileItem[]
  process_type: DocumentProcessType
  rule: CustomRuleForm
}

type CreateDocumentsPayload = {
  upload_file_ids: string[]
  process_type: DocumentProcessType
  rule?: CreateDocumentsRequest['rule']
}

type UploadCustomRequestOption = {
  fileItem: FileItem
  onSuccess: (response?: unknown) => void
  onError: (error?: Error) => void
}

type UploadFileResponsePayload = {
  id?: string
}

// 1.定义页面逻辑基础数据，涵盖定时器、路由、当前步骤书、表单信息等
let timer: ReturnType<typeof setInterval> | null = null
let batch = ''
let fetchCount = 0
const route = useRoute()
const {
  loading: createDocumentsLoading,
  create_documents_result,
  handleCreateDocuments,
} = useCreateDocuments()
const { upload_file, handleUploadFile } = useUploadFile()
const { documents_status_result, loadDocumentsStatus } = useGetDocumentsStatus()
const currentStep = ref(1)
const createDocumentsForm = ref<CreateDocumentsForm>({
  file_list: [],
  process_type: 'automatic',
  rule: {
    separators: ['\\n'],
    chunk_size: 500,
    chunk_overlap: 50,
    pre_process_rules: [],
  },
})
const customRuleFormRef = ref<InstanceType<typeof Form>>()
const documents = ref<GetDocumentsStatusResponse['data']>([])

const getUploadFileId = (fileItem: FileItem): string => {
  const response = fileItem.response as UploadFileResponsePayload | undefined
  const id = response?.id
  return id ? String(id) : ''
}

// 2.定义下一步处理函数
const nextStep = async () => {
  // 2.1 判断下当前所处的步骤并执行不同的操作
  if (currentStep.value === 1) {
    // 2.2 检查是否已经上传了文件，如果没上传则不允许点击下一步
    if (createDocumentsForm.value.file_list.length === 0) {
      Message.error('请上传需要添加到知识库的文件')
      return
    }

    // 2.3 检查所有文件是否全部上传完成
    const isUploaded = createDocumentsForm.value.file_list.every(
      (fileItem) => getUploadFileId(fileItem) !== '',
    )
    if (!isUploaded) {
      Message.warning('文件正在上传中，请稍等')
      return
    }

    // 2.4 进入下一步
    currentStep.value++
  } else {
    // 2.5 当前处于第2页，需要根据不同的处理类型执行不同的操作
    if (createDocumentsForm.value.process_type === 'custom') {
      // 2.6 校验表单数据监测是否出错
      const errors = await customRuleFormRef.value?.validate()
      if (errors) return
    }

    // 2.7 如果校验成功或者是自动规则，则执行下一步
    try {
      // 2.8 将加载状态设置为true，并将表单数据转换成api接口数据
      const req: CreateDocumentsPayload = {
        upload_file_ids: createDocumentsForm.value.file_list.map(
          (fileItem) => getUploadFileId(fileItem),
        ),
        process_type: createDocumentsForm.value.process_type,
      }

      // 2.9 如果处理类型为自定义，则需要添加上自定义规则
      if (createDocumentsForm.value.process_type === 'custom') {
        req.rule = {
          pre_process_rules: [
            {
              id: 'remove_extra_space',
              enabled:
                createDocumentsForm.value.rule.pre_process_rules.includes('remove_extra_space'),
            },
            {
              id: 'remove_url_and_email',
              enabled:
                createDocumentsForm.value.rule.pre_process_rules.includes('remove_url_and_email'),
            },
          ],
          segment: {
            separators: createDocumentsForm.value.rule.separators.map((separator) =>
              unescapeString(separator),
            ),
            chunk_size: createDocumentsForm.value.rule.chunk_size,
            chunk_overlap: createDocumentsForm.value.rule.chunk_overlap,
          },
        }
      }

      // 2.10 发起请求并获取数据
      await handleCreateDocuments(String(route.params?.dataset_id), req as CreateDocumentsRequest)
      batch = create_documents_result.value.batch

      // 2.11 先调用一次获取文档状态，然后创建定时器
      await fetchDocumentsStatus()
      startTimer()

      // 2.12 创建文档预处理成功，当前步骤数+1
      currentStep.value++
    } finally {
      createDocumentsLoading.value = false
    }
  }
}

// 3.定义获取文档状态数据函数
const fetchDocumentsStatus = async () => {
  // 3.1 调用接口获取文档状态数据
  fetchCount++
  await loadDocumentsStatus(String(route.params?.dataset_id), batch)

  // 3.2 同步文档状态信息
  documents.value = documents_status_result.value as unknown as GetDocumentsStatusResponse['data']

  // 3.3 如果请求次数超过限制，则停止
  if (fetchCount >= 30) stopTimer()

  // 3.4 如果文档全部都处理完成（涵盖处理完成+错误），则停止
  const isCompleted = documents_status_result.value.every(
    (document) => document.status === 'completed' || document.status === 'error',
  )
  if (isCompleted) stopTimer()
}

// 4.定义开始定时器函数
const startTimer = () => {
  stopTimer()
  timer = setInterval(fetchDocumentsStatus, 5000)
}

// 5.停止定时器函数
const stopTimer = () => {
  if (timer !== null) {
    clearInterval(timer)
    timer = null
  }
}

// 6.页面卸载时同步卸载定时器
onUnmounted(() => stopTimer())
</script>

<template>
  <div class="p-6">
    <!-- 回退按钮与标题 -->
    <div class="flex items-center mb-6 gap-4">
      <!-- 左侧回退按钮 -->
      <router-link
        :to="{
          name: 'space-datasets-documents-list',
          params: { dataset_id: route.params?.dataset_id as string },
        }"
      >
        <a-button size="mini" type="text" class="!text-gray-700">
          <template #icon>
            <icon-left />
          </template>
        </a-button>
      </router-link>
      <div class="text-lg font-bold text-gray-700">添加文件</div>
    </div>
    <!-- 步骤条 -->
    <div class="w-[520px] mx-auto">
      <a-steps :current="currentStep">
        <a-step>上传</a-step>
        <a-step>分段设置</a-step>
        <a-step>数据处理</a-step>
      </a-steps>
    </div>
    <!-- 步骤条页面 -->
    <div class="min-h-[calc(100vh-160px)] p-[48px]">
      <!-- 上传页面 -->
      <div v-if="currentStep === 1" class="">
        <!-- 上传文件按钮 -->
        <a-upload
          v-model:file-list="createDocumentsForm.file_list"
          draggable
          accept=".doc,.docx,.pdf,.txt,.md,.markdown"
          :limit="10"
          multiple
          tip="支持PDF、TXT、DOC、DOCX、MD，最多可上传10个文件，每个文件的大小不超过10MB"
          :custom-request="
            (option: UploadCustomRequestOption) => {
              // 1.提取选项中的文件选项以及成功回调
              const { fileItem, onSuccess, onError } = option

              const uploadTask = async () => {
                try {
                  if (!fileItem.file) {
                    onError(new Error('无效文件'))
                    return
                  }
                  console.log('[Upload] Starting upload for file:', fileItem.file.name)
                  const response = await handleUploadFile(fileItem.file as File)
                  console.log('[Upload] Upload completed, response:', response)

                  // 从响应的 data 字段中获取文件ID
                  const fileId = response?.data?.id
                  if (!fileId) {
                    console.error('[Upload] No file ID in response:', response)
                    onError(new Error('上传失败: 未获得文件ID'))
                    return
                  }
                  console.log('[Upload] File ID:', fileId)
                  onSuccess({ id: fileId })
                } catch (error: unknown) {
                  console.error('[Upload] Error:', error)
                  onError(error instanceof Error ? error : new Error('上传失败'))
                }
              }

              // 2.调用api接口上传文件并添加数据
              uploadTask()

              return { abort: () => {} }
            }
          "
        />
      </div>
      <!-- 分段设置页面 -->
      <div v-else-if="currentStep === 2" class="">
        <!-- 自动分段与清洗 -->
        <div
          :class="`px-5 py-4 bg-white rounded-lg border cursor-pointer mb-4 hover:border-blue-700 ${createDocumentsForm.process_type === 'automatic' ? 'border-blue-700' : ''}`"
          @click="createDocumentsForm.process_type = 'automatic'"
        >
          <div class="font-bold text-gray-700 mb-2">自动分段与清洗</div>
          <div class="text-gray-500">自动分段与预处理规则</div>
        </div>
        <!-- 自定义 -->
        <div
          :class="`px-5 py-4 bg-white rounded-lg border cursor-pointer hover:border-blue-700 ${createDocumentsForm.process_type === 'custom' ? 'border-blue-700' : ''}`"
          @click="createDocumentsForm.process_type = 'custom'"
        >
          <div class="font-bold text-gray-700 mb-2">自定义</div>
          <div class="text-gray-500">自定义分段规则、分段长度与预处理规则</div>
          <!-- 自定义表单 -->
          <div v-if="createDocumentsForm.process_type === 'custom'" class="">
            <a-divider />
            <!-- 表单选项 -->
            <a-form :model="createDocumentsForm.rule" ref="customRuleFormRef" layout="vertical">
              <a-form-item
                field="separators"
                label="分段标识符"
                required
                asterisk-position="end"
                :rules="[{ required: true, message: '分段标识符不能为空' }]"
              >
                <a-input-tag
                  v-model:model-value="createDocumentsForm.rule.separators"
                  placeholder="请输入分段标识符，按下Enter结束"
                />
              </a-form-item>
              <a-form-item
                field="chunk_size"
                label="分段最大长度"
                required
                asterisk-position="end"
                :rules="[{ required: true, message: '分段最大长度不能为空' }]"
              >
                <a-input-number
                  v-model:model-value="createDocumentsForm.rule.chunk_size"
                  :min="100"
                  :max="1000"
                  :step="1"
                  :default-value="500"
                  placeholder="请输入100-1000的数字"
                />
              </a-form-item>
              <a-form-item
                field="chunk_overlap"
                label="块重叠数"
                required
                asterisk-position="end"
                :rules="[{ required: true, message: '块重叠大小不能为空' }]"
              >
                <a-input-number
                  v-model:model-value="createDocumentsForm.rule.chunk_overlap"
                  :min="0"
                  :max="500"
                  :step="1"
                  :default-value="50"
                  placeholder="请输入0-500的数字"
                />
              </a-form-item>
              <a-form-item field="pre_process_rules" label="文本预处理规则">
                <a-checkbox-group
                  v-model:model-value="createDocumentsForm.rule.pre_process_rules"
                  direction="vertical"
                >
                  <a-checkbox value="remove_extra_space">
                    替换掉连续的空格、换行符和制表符
                  </a-checkbox>
                  <a-checkbox value="remove_url_and_email">删除所有 URL 和电子邮件</a-checkbox>
                </a-checkbox-group>
              </a-form-item>
            </a-form>
          </div>
        </div>
      </div>
      <!-- 数据处理页面 -->
      <div v-else class="">
        <!-- 数据处理状态提示 -->
        <div class="text-gray-900 mb-4 text-base">服务器正在处理中</div>
        <!-- 处理中的文档列表 -->
        <div class="flex flex-col gap-2">
          <div
            v-for="document in documents"
            :key="document.id"
            class="flex items-center justify-between px-4 py-3 bg-white rounded-lg border"
          >
            <!-- 左侧文件信息 -->
            <div class="flex items-center gap-2.5">
              <a-avatar shape="square" class="bg-blue-700" :size="32">
                <icon-file />
              </a-avatar>
              <div class="">
                <div class="text-gray-700">{{ document.name }}</div>
                <div class="text-gray-500">{{ (document.size / 1024).toFixed(2) }}kb</div>
              </div>
            </div>
            <!-- 处理的百分比 -->
            <div v-if="document.segment_count === 0" class="text-gray-500">0.00%</div>
            <div v-else-if="document.status === 'error'" class="">处理出错</div>
            <div v-else-if="document.status === 'completed'" class="">处理完成</div>
            <div v-else class="text-gray-500">
              {{ ((document.completed_segment_count / document.segment_count) * 100).toFixed(2) }}%
            </div>
          </div>
        </div>
      </div>
    </div>
    <!-- 按钮：涵盖上一步和下一步 -->
    <div class="flex items-center justify-between px-[48px]">
      <div class=""></div>
      <div class="flex items-center gap-2">
        <a-button
          v-if="currentStep === 2"
          class="rounded-lg"
          @click="
            () => {
              if (currentStep > 1) currentStep--
            }
          "
        >
          上一步
        </a-button>
        <a-button
          :loading="createDocumentsLoading"
          v-if="currentStep <= 2"
          type="primary"
          class="rounded-lg"
          @click="nextStep"
        >
          下一步
        </a-button>
        <!-- 数据处理页面显示的内容 -->
        <div v-if="currentStep === 3" class="flex items-center gap-2">
          <div class="text-gray-500">点击确认不影响数据处理，处理完毕后可进行引用</div>
          <router-link
            :to="{
              name: 'space-datasets-documents-list',
              params: { dataset_id: route.params?.dataset_id as string },
            }"
          >
            <a-button type="primary" class="rounded-lg">确定</a-button>
          </router-link>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped></style>
