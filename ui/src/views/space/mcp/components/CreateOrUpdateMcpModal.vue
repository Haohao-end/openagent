<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { type FileItem, Form, Message, type ValidatedError } from '@arco-design/web-vue'
import { useI18n } from 'vue-i18n'
import IconUploadGenerator from '@/components/IconUploadGenerator.vue'
import { useUploadImage } from '@/hooks/use-upload-file'
import { getErrorMessage } from '@/utils/error'
import { getStoreCategoryDisplayName } from '@/utils/store-display'
import { getMcpCategories, getMcpProvider, createMcpProvider, updateMcpProvider, generateMcpIconPreview, regenerateMcpIcon } from '@/services/mcp'
import { mcpSchemaAssistantChat } from '@/services/ai'
import type { McpCategory } from '@/models/mcp'

type HeaderItem = { key: string; value: string }

type McpForm = {
  fileList: FileItem[]
  icon: string
  name: string
  description: string
  category: string
  transport: string
  url: string
  command: string
  headers_text: string
  tool_names_text: string
  args_text: string
  env_text: string
  timeout_seconds: number
}

const props = defineProps({
  mcp_provider_id: { type: String, default: '', required: false },
  visible: { type: Boolean, required: true },
  callback: { type: Function, required: false },
})

const emits = defineEmits(['update:visible', 'update:mcp_provider_id'])
const { t, locale } = useI18n()

const categories = ref<McpCategory[]>([])
const formRef = ref<InstanceType<typeof Form>>()
const loadingProvider = ref(false)
const submitLoading = ref(false)
const generateLoading = ref(false)
const aiQuestion = ref('')
const aiAnswer = ref('')
const aiLoading = ref(false)
const { image_url, handleUploadImage } = useUploadImage()

const defaultForm = (): McpForm => ({
  fileList: [],
  icon: '',
  name: '',
  description: '',
  category: 'other',
  transport: 'streamable_http',
  url: '',
  command: '',
  headers_text: '[]',
  tool_names_text: '',
  args_text: '',
  env_text: '{}',
  timeout_seconds: 30,
})

const form = ref<McpForm>(defaultForm())
let latestProviderRequest = 0
let latestAiRequest = 0

const isEditMode = computed(() => Boolean(props.mcp_provider_id))
const getCategoryLabel = (value: string) =>
  getStoreCategoryDisplayName(value, locale.value as 'zh-CN' | 'en-US')

const hideModal = () => emits('update:visible', false)

const loadCategories = async (requestId: number) => {
  try {
    const res = await getMcpCategories()
    if (requestId === latestProviderRequest) categories.value = res.data.categories || []
  } catch (_error: unknown) {
    if (requestId === latestProviderRequest) categories.value = []
  }
}

const parseJsonArray = (text: string) => {
  const normalized = String(text || '').trim()
  if (!normalized) return []
  const parsed = JSON.parse(normalized)
  if (!Array.isArray(parsed)) {
    throw new Error(t('space.mcp.arrayExpected'))
  }
  return parsed
}

const parseJsonObject = (text: string) => {
  const normalized = String(text || '').trim()
  if (!normalized) return {}
  const parsed = JSON.parse(normalized)
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error(t('space.mcp.objectExpected'))
  }
  return parsed as Record<string, string>
}

const extractJsonObject = (content: string) => {
  const fenceMatch = content.match(/```(?:json)?\s*([\s\S]*?)```/i)
  const normalized = (fenceMatch?.[1] ?? content).trim()
  const firstBrace = normalized.indexOf('{')
  const lastBrace = normalized.lastIndexOf('}')
  if (firstBrace !== -1 && lastBrace > firstBrace) {
    return normalized.slice(firstBrace, lastBrace + 1)
  }
  return normalized
}

const applyMcpPayload = (payload: Record<string, any>) => {
  const headers = Array.isArray(payload.headers) ? payload.headers : []
  const toolNames = Array.isArray(payload.tool_names) ? payload.tool_names : []
  const args = Array.isArray(payload.args) ? payload.args : []
  const env = payload.env && typeof payload.env === 'object' && !Array.isArray(payload.env) ? payload.env : {}

  form.value.name = String(payload.name || '').trim()
  form.value.description = String(payload.description || '').trim()
  form.value.category = String(payload.category || 'other').trim() || 'other'
  form.value.transport = String(payload.transport || 'streamable_http').trim() || 'streamable_http'
  form.value.url = String(payload.url || '').trim()
  form.value.command = String(payload.command || '').trim()
  form.value.headers_text = JSON.stringify(headers, null, 2)
  form.value.tool_names_text = toolNames.map((item) => String(item).trim()).filter(Boolean).join(', ')
  form.value.args_text = args.map((item) => String(item).trim()).filter(Boolean).join(', ')
  form.value.env_text = JSON.stringify(env, null, 2)
  form.value.timeout_seconds = Number(payload.timeout_seconds || 30)
  form.value.icon = String(payload.icon || form.value.icon || '')
  if (form.value.icon) {
    form.value.fileList = [{ uid: '1', name: t('space.mcp.iconPlaceholder'), url: form.value.icon }]
  }
}

const loadProvider = async (providerId: string) => {
  if (!providerId) {
    form.value = defaultForm()
    return
  }

  loadingProvider.value = true
  const requestId = ++latestProviderRequest
  try {
    const res = await getMcpProvider(providerId)
    if (requestId === latestProviderRequest) applyMcpPayload(res.data)
  } catch (error: unknown) {
    if (requestId === latestProviderRequest) Message.error(getErrorMessage(error, t('space.mcp.detailLoadFailed')))
  } finally {
    if (requestId === latestProviderRequest) loadingProvider.value = false
  }
}

const handleUploadIcon = async (file: File) => {
  await handleUploadImage(file)
  form.value.icon = image_url.value
  form.value.fileList = [{ uid: '1', name: t('space.mcp.iconPlaceholder'), url: image_url.value }]
  Message.success(t('space.mcp.iconUploadSuccess'))
}

const handleGenerateIcon = async () => {
  if (!form.value.name || form.value.name.trim() === '') {
    Message.warning(t('space.mcp.nameRequired'))
    return
  }

  try {
    generateLoading.value = true
    if (isEditMode.value) {
      const providerId = props.mcp_provider_id
      const res = await regenerateMcpIcon(providerId)
      if (res.data.icon) {
        form.value.icon = res.data.icon
        form.value.fileList = [{ uid: '1', name: t('space.mcp.iconPlaceholder'), url: res.data.icon }]
        Message.success(t('space.mcp.iconGenerateSuccess'))
      }
    } else {
      const res = await generateMcpIconPreview(form.value.name, form.value.description)
      if (res.data.icon) {
        form.value.icon = res.data.icon
        form.value.fileList = [{ uid: '1', name: t('space.mcp.iconPlaceholder'), url: res.data.icon }]
        Message.success(t('space.mcp.iconGenerateSuccess'))
      }
    }
  } catch (error: unknown) {
    Message.error(getErrorMessage(error, t('space.mcp.iconGenerateFailed')))
  } finally {
    generateLoading.value = false
  }
}

const handleGenerateByAI = async () => {
  const question = aiQuestion.value.trim()
  if (!question) {
    Message.warning(t('space.mcp.aiDescriptionRequired'))
    return
  }

  aiLoading.value = true
  aiAnswer.value = ''
  const requestId = ++latestAiRequest
  try {
    await mcpSchemaAssistantChat(question, (eventResponse) => {
      if (requestId !== latestAiRequest) return
      const content = String(eventResponse?.data?.content ?? '')
      if (!content) return
      aiAnswer.value += content
    })

    if (requestId !== latestAiRequest) return
    const jsonText = extractJsonObject(aiAnswer.value)
    const payload = JSON.parse(jsonText)
    applyMcpPayload(payload)
    Message.success(t('space.mcp.aiConfigSuccess'))
  } catch (error: unknown) {
    if (requestId === latestAiRequest) Message.error(getErrorMessage(error, t('space.mcp.aiConfigFailed')))
  } finally {
    if (requestId === latestAiRequest) aiLoading.value = false
  }
}

const handleSubmit = async ({ errors }: { errors: Record<string, ValidatedError> | undefined }) => {
  if (errors) return

  let headers: HeaderItem[] = []
  let env: Record<string, string> = {}
  try {
    headers = parseJsonArray(form.value.headers_text)
      .map((item) => ({
        key: String(item?.key || '').trim(),
        value: String(item?.value || '').trim(),
      }))
      .filter((item) => item.key)
    env = parseJsonObject(form.value.env_text)
  } catch (error: unknown) {
    Message.warning(t('space.mcp.jsonError', { message: (error as Error).message }))
    return
  }

  const toolNames = String(form.value.tool_names_text || '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
  const args = String(form.value.args_text || '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)

  const payload = {
    name: form.value.name.trim(),
    description: form.value.description.trim(),
    category: form.value.category,
    transport: form.value.transport,
    url: String(form.value.url || '').trim(),
    command: String(form.value.command || '').trim(),
    headers,
    tool_names: toolNames,
    args,
    env,
    timeout_seconds: Number(form.value.timeout_seconds || 30),
    icon: form.value.icon,
  }

  if (payload.transport === 'stdio' && !payload.command) {
    Message.warning(t('space.mcp.stdioCommandRequired'))
    return
  }
  if (['http', 'sse', 'streamable_http', 'streamable-http'].includes(payload.transport) && !payload.url) {
    Message.warning(t('space.mcp.urlRequired'))
    return
  }

  submitLoading.value = true
  try {
    if (isEditMode.value) {
      await updateMcpProvider(props.mcp_provider_id, payload)
      Message.success(t('space.mcp.updateSuccess'))
    } else {
      await createMcpProvider(payload)
      Message.success(t('space.mcp.createSuccess'))
    }
    emits('update:visible', false)
    emits('update:mcp_provider_id', '')
    props.callback && props.callback()
  } catch (error: unknown) {
    Message.error(getErrorMessage(error, t('space.mcp.saveFailed')))
  } finally {
    submitLoading.value = false
  }
}

watch(
  () => [props.visible, props.mcp_provider_id] as const,
  async ([visible, providerId]) => {
    const requestId = ++latestProviderRequest
    latestAiRequest += 1
    loadingProvider.value = false
    aiLoading.value = false
    formRef.value?.resetFields()
    form.value = defaultForm()
    aiQuestion.value = ''
    aiAnswer.value = ''
    if (!visible) {
      emits('update:mcp_provider_id', '')
      return
    }

    await loadCategories(requestId)
    if (requestId !== latestProviderRequest) return
    if (providerId) await loadProvider(providerId)
  },
)
onUnmounted(() => {
  latestProviderRequest += 1
  latestAiRequest += 1
  loadingProvider.value = false
  aiLoading.value = false
})
</script>

<template>
  <a-modal
    :visible="props.visible"
    hide-title
    :footer="false"
    :width="1080"
    class="tools-modal mcp-create-modal"
    modal-class="mcp-create-modal-shell"
    @cancel="hideModal"
  >
    <a-spin :loading="loadingProvider" class="block h-full w-full">
      <div class="flex h-full w-full flex-col overflow-hidden lg:flex-row">
        <aside
          class="flex flex-col gap-4 border-b border-gray-200 bg-gray-50 p-4 lg:w-[330px] lg:border-b-0 lg:border-r lg:overflow-y-auto scrollbar-w-none"
        >
          <div class="flex items-start justify-between gap-3">
            <div>
              <div class="text-xl font-bold text-gray-800">
                {{ isEditMode ? t('space.mcp.updateTitle') : t('space.mcp.createTitle') }}
              </div>
              <div class="mt-1 text-xs leading-5 text-gray-500">
                {{ t('space.mcp.modalDescription') }}
              </div>
            </div>
            <a-button type="text" class="!text-gray-500 hover:!text-gray-700" size="small" @click="hideModal">
              <template #icon>
                <icon-close :size="20" />
              </template>
            </a-button>
          </div>

          <div class="mb-0">
            <IconUploadGenerator
              :name="form.name"
              :description="form.description"
              :icon="form.icon"
              :file-list="form.fileList"
              :loading="generateLoading"
              :placeholder="t('space.mcp.iconPlaceholder')"
              :on-upload="handleUploadIcon"
              :on-generate="handleGenerateIcon"
              @update:icon="(val) => (form.icon = val)"
              @update:fileList="(val) => (form.fileList = val)"
            />
          </div>

          <div class="rounded-lg border border-gray-200 bg-white p-4">
            <div class="flex items-center justify-between gap-2 mb-3">
              <div class="text-sm font-semibold text-gray-800">{{ t('space.mcp.aiTitle') }}</div>
              <a-button type="primary" size="small" :loading="aiLoading" @click="handleGenerateByAI">
                {{ t('space.mcp.aiButton') }}
              </a-button>
            </div>
            <a-textarea
              v-model="aiQuestion"
              :auto-size="{ minRows: 4, maxRows: 6 }"
              :placeholder="t('space.mcp.aiPlaceholder')"
            />
          </div>

          <div class="rounded-lg border border-blue-100 bg-blue-50 p-3 text-xs leading-5 text-blue-800">
            <div class="font-semibold text-blue-900 mb-1">{{ t('space.mcp.fillHintTitle') }}</div>
            <div>{{ t('space.mcp.fillHint') }}</div>
          </div>
        </aside>

        <section class="flex-1 min-w-0 bg-white p-4 lg:overflow-y-auto scrollbar-w-none">
          <a-form ref="formRef" :model="form" layout="vertical" @submit="handleSubmit">
            <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <a-form-item
                field="name"
                :label="t('space.mcp.nameLabel')"
                asterisk-position="end"
                class="lg:col-span-2"
                :rules="[{ required: true, message: t('space.mcp.nameRequired') }]"
              >
                <a-input v-model:model-value="form.name" :placeholder="t('space.mcp.namePlaceholder')" />
              </a-form-item>

              <a-form-item
                field="description"
                :label="t('space.mcp.descriptionLabel')"
                asterisk-position="end"
                class="lg:col-span-2"
                :rules="[{ required: true, message: t('space.mcp.descriptionRequired') }]"
              >
                <a-textarea
                  v-model:model-value="form.description"
                  :auto-size="{ minRows: 3, maxRows: 4 }"
                  :placeholder="t('space.mcp.descriptionPlaceholder')"
                />
              </a-form-item>

              <a-form-item field="category" :label="t('space.mcp.categoryLabel')">
                <a-select v-model:model-value="form.category" :placeholder="t('space.mcp.categoryPlaceholder')">
                  <a-option v-for="category in categories" :key="category.id" :value="category.id">
                    {{ getCategoryLabel(category.id || category.name) }}
                  </a-option>
                </a-select>
              </a-form-item>

              <a-form-item field="transport" :label="t('space.mcp.transportLabel')">
                <a-select v-model:model-value="form.transport" :placeholder="t('space.mcp.transportPlaceholder')">
                  <a-option value="streamable_http">streamable_http</a-option>
                  <a-option value="http">http</a-option>
                  <a-option value="sse">sse</a-option>
                  <a-option value="stdio">stdio</a-option>
                </a-select>
              </a-form-item>

              <a-form-item field="timeout_seconds" :label="t('space.mcp.timeoutLabel')">
                <a-input-number v-model:model-value="form.timeout_seconds" :min="1" :max="600" />
              </a-form-item>

              <div class="hidden rounded-lg border border-dashed border-gray-200 bg-gray-50 p-4 text-xs leading-5 text-gray-500 lg:block">
                <div class="font-semibold text-gray-800 mb-1">{{ t('space.mcp.advancedHintTitle') }}</div>
                <div>{{ t('space.mcp.advancedHint') }}</div>
              </div>

              <a-form-item field="url" :label="t('space.mcp.urlLabel')" class="lg:col-span-2">
                <a-input v-model:model-value="form.url" :placeholder="t('space.mcp.urlPlaceholder')" />
              </a-form-item>

              <a-form-item field="command" :label="t('space.mcp.commandLabel')" class="lg:col-span-2">
                <a-input v-model:model-value="form.command" :placeholder="t('space.mcp.commandPlaceholder')" />
              </a-form-item>

              <a-form-item field="tool_names_text" :label="t('space.mcp.toolNamesLabel')">
                <a-input v-model:model-value="form.tool_names_text" :placeholder="t('space.mcp.toolNamesPlaceholder')" />
              </a-form-item>

              <a-form-item field="args_text" :label="t('space.mcp.argsLabel')">
                <a-input v-model:model-value="form.args_text" :placeholder="t('space.mcp.argsPlaceholder')" />
              </a-form-item>

              <a-form-item field="headers_text" :label="t('space.mcp.headersLabel')" class="lg:col-span-2">
                <a-textarea
                  v-model:model-value="form.headers_text"
                  :auto-size="{ minRows: 3, maxRows: 5 }"
                  :placeholder="t('space.mcp.headersPlaceholder')"
                />
              </a-form-item>

              <a-form-item field="env_text" :label="t('space.mcp.envLabel')" class="lg:col-span-2">
                <a-textarea
                  v-model:model-value="form.env_text"
                  :auto-size="{ minRows: 3, maxRows: 5 }"
                  :placeholder="t('space.mcp.envPlaceholder')"
                />
              </a-form-item>
            </div>

            <div class="flex items-center justify-end gap-3 pt-4">
              <a-button html-type="button" size="large" class="rounded-lg px-6" @click="hideModal">{{ t('common.actions.cancel') }}</a-button>
              <a-button
                :loading="submitLoading"
                type="primary"
                html-type="submit"
                size="large"
                class="rounded-lg px-6"
              >
                {{ t('common.actions.save') }}
              </a-button>
            </div>
          </a-form>
        </section>
      </div>
    </a-spin>
  </a-modal>
</template>

<style>
.mcp-create-modal-shell {
  height: calc(100dvh - 32px);
  max-height: calc(100dvh - 32px);
  width: min(96vw, 1080px);
}

.mcp-create-modal .arco-modal-wrapper {
  @apply text-right;
}

.mcp-create-modal .arco-modal-body {
  @apply h-full w-full rounded-xl p-0 overflow-hidden;
}

@supports not (height: 100dvh) {
  .mcp-create-modal-shell {
    height: calc(100vh - 32px);
    max-height: calc(100vh - 32px);
  }
}
</style>
