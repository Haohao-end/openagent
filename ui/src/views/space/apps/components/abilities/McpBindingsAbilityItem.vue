<script setup lang="ts">
import { computed, nextTick, type PropType, ref, watch } from 'vue'
import { useUpdateDraftAppConfig } from '@/hooks/use-app'
import { cloneDeep, isEqual } from 'lodash'
import { Message } from '@arco-design/web-vue'
import { apiPrefix } from '@/config'
import type { McpBinding, McpToolSnapshot } from '@/models/app'
import { useI18n } from 'vue-i18n'
import McpMarketplacePickerModal from './McpMarketplacePickerModal.vue'
import { resolveMcpBindingStatus } from './mcp-status'

type McpBindingForm = McpBinding & {
  headers_text: string
  tool_names_text: string
  args_text: string
  env_text: string
}

const defaultForm = (): McpBindingForm => ({
  name: '',
  description: '',
  transport: 'streamable_http',
  url: '',
  command: '',
  enabled: true,
  headers: [],
  tool_names: [],
  timeout_seconds: 30,
  args: [],
  env: {},
  headers_text: '[]',
  tool_names_text: '',
  args_text: '',
  env_text: '{}',
})

const props = defineProps({
  app_id: { type: String, default: '', required: true },
  mcp_bindings: {
    type: Array as PropType<McpBinding[]>,
    default: () => [],
    required: true,
  },
  mcp_tool_snapshots: {
    type: Array as PropType<McpToolSnapshot[]>,
    default: () => [],
  },
})
const { t } = useI18n()
const emits = defineEmits(['update:mcp_bindings', 'reload-draft-app-config'])
const { handleUpdateDraftAppConfig } = useUpdateDraftAppConfig()
const mcpBindingsModalVisible = ref(false)
const isSavingMcpBinding = ref(false)
const isMcpBindingsInit = ref(false)
const activateMcpBindings = ref<McpBindingForm[]>([])
const originMcpBindings = ref<McpBindingForm[]>([])
const editingIndex = ref<number>(-1)
const bindingForm = ref<McpBindingForm>(defaultForm())
const showMarketplacePickerModal = ref(false)
const hasLocalMcpBindingChanges = computed(() => !isEqual(activateMcpBindings.value, originMcpBindings.value))

const stripBindingForm = (binding: McpBindingForm): McpBinding => {
  const { headers_text, tool_names_text, args_text, env_text, ...rest } = binding
  return rest
}

const normalizeBindingToForm = (binding: McpBinding): McpBindingForm => {
  return {
    ...defaultForm(),
    ...binding,
    headers_text: JSON.stringify(binding.headers ?? [], null, 2),
    tool_names_text: (binding.tool_names ?? []).join(', '),
    args_text: (binding.args ?? []).join(', '),
    env_text: JSON.stringify(binding.env ?? {}, null, 2),
  }
}

const buildBindingIdentity = (binding: Pick<McpBinding, 'provider_key' | 'transport' | 'url' | 'command' | 'name'>) => {
  if (String(binding.provider_key || '').trim()) {
    return `provider_key:${String(binding.provider_key || '').trim()}`
  }
  return `${String(binding.transport || '').trim()}:${String(binding.url || binding.command || '').trim()}:${String(binding.name || '').trim()}`
}

const buildBindingSignatures = (binding: Pick<McpBinding, 'provider_key' | 'transport' | 'url' | 'command' | 'name'>) => {
  const signatures = [buildBindingIdentity(binding)]
  const providerKey = String(binding.provider_key || '').trim()
  if (providerKey) {
    signatures.push(`provider_key:${providerKey}`)
  }
  const transport = String(binding.transport || '').trim()
  const identity = `${transport}:${String(binding.url || binding.command || '').trim()}:${String(binding.name || '').trim()}`
  signatures.push(identity)
  return signatures
}

const isSameBinding = (
  left: Pick<McpBinding, 'provider_key' | 'transport' | 'url' | 'command' | 'name'>,
  right: Pick<McpBinding, 'provider_key' | 'transport' | 'url' | 'command' | 'name'>,
) => {
  const rightSignatures = new Set(buildBindingSignatures(right))
  return buildBindingSignatures(left).some((signature) => rightSignatures.has(signature))
}

const closeMcpBindingsModal = () => {
  mcpBindingsModalVisible.value = false
  editingIndex.value = -1
  bindingForm.value = defaultForm()
}

const syncLocalBindings = (newBindings: McpBindingForm[]) => {
  const normalized = cloneDeep(newBindings)
  originMcpBindings.value = normalized
  activateMcpBindings.value = cloneDeep(normalized)
  isMcpBindingsInit.value = true
}

const getBindingStatus = (binding: McpBindingForm) => resolveMcpBindingStatus(binding, props.mcp_tool_snapshots || [])

const normalizeIconUrl = (icon: string = '') => {
  if (!icon) return ''
  if (icon.startsWith('data:') || /^https?:\/\//.test(icon)) return icon
  const fallbackOrigin = globalThis.location?.origin ?? 'http://localhost'
  const apiUrl = new URL(apiPrefix, fallbackOrigin)
  const basePath = apiUrl.pathname.replace(/\/+$/, '')
  let path = icon.startsWith('/') ? icon : `/${icon}`

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

const avatarPalettes = [
  ['#334155', '#0f172a'],
  ['#0369a1', '#1d4ed8'],
  ['#047857', '#0f766e'],
  ['#c2410c', '#d97706'],
  ['#be123c', '#e11d48'],
  ['#0f766e', '#14b8a6'],
]

const hashString = (value: string) => {
  let hash = 0
  for (let i = 0; i < value.length; i += 1) {
    hash = (hash * 33 + value.charCodeAt(i)) >>> 0
  }
  return hash
}

const getBindingAvatarText = (binding: Pick<McpBinding, 'label' | 'name' | 'provider_key'>) => {
  const source = (binding.label || binding.name || binding.provider_key || 'M').trim()
  const latinParts = source.match(/[A-Za-z0-9]+/g)
  if (latinParts && latinParts.length > 0) {
    return latinParts
      .slice(0, 2)
      .map((item) => item[0]?.toUpperCase())
      .join('')
  }

  const chineseParts = source.match(/[\u4e00-\u9fff]/g)
  if (chineseParts && chineseParts.length > 0) {
    return chineseParts.slice(0, 2).join('')
  }

  return source.slice(0, 2).toUpperCase()
}

const getBindingAvatarStyle = (binding: Pick<McpBinding, 'provider_key' | 'category' | 'label'>) => {
  const palette = avatarPalettes[hashString(`${String(binding.provider_key || '').trim()}:${String(binding.category || '').trim()}:${String(binding.label || '').trim()}`) % avatarPalettes.length]
  return {
    background: `linear-gradient(135deg, ${palette[0]} 0%, ${palette[1]} 100%)`,
    boxShadow: 'inset 0 1px 0 rgba(255, 255, 255, 0.15)',
  }
}

const openEditModal = (idx: number) => {
  const binding = activateMcpBindings.value[idx]
  if (!binding) return
  editingIndex.value = idx
  bindingForm.value = normalizeBindingToForm(binding)
  mcpBindingsModalVisible.value = true
}

const openMarketplacePicker = () => {
  showMarketplacePickerModal.value = true
}

const handleCancelMcpBindingsModal = () => {
  if (isSavingMcpBinding.value) return
  closeMcpBindingsModal()
}

const parseJsonArray = (text: string) => {
  const normalized = String(text || '').trim()
  if (!normalized) return []
  const parsed = JSON.parse(normalized)
  if (!Array.isArray(parsed)) {
    throw new Error(t('appStudio.abilities.mcp.arrayExpected'))
  }
  return parsed
}

const parseJsonObject = (text: string) => {
  const normalized = String(text || '').trim()
  if (!normalized) return {}
  const parsed = JSON.parse(normalized)
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error(t('appStudio.abilities.mcp.objectExpected'))
  }
  return parsed as Record<string, string>
}

const handleSubmitBinding = async () => {
  if (isSavingMcpBinding.value) return
  const form = bindingForm.value
  if (!form.name.trim()) {
    Message.warning(t('appStudio.abilities.mcp.nameRequired'))
    return
  }
  if (!form.description.trim()) {
    Message.warning(t('appStudio.abilities.mcp.descriptionRequired'))
    return
  }

  const transport = String(form.transport || 'streamable_http').trim()
  if (['http', 'sse', 'streamable_http', 'streamable-http'].includes(transport)) {
    if (!String(form.url || '').trim()) {
      Message.warning(t('appStudio.abilities.mcp.urlRequired'))
      return
    }
  }
  if (transport === 'stdio' && !String(form.command || '').trim()) {
    Message.warning(t('appStudio.abilities.mcp.commandRequired'))
    return
  }

  let headers: Array<{ key: string; value: string }> = []
  let env: Record<string, string> = {}
  try {
    headers = parseJsonArray(form.headers_text).map((item) => ({
      key: String(item?.key || '').trim(),
      value: String(item?.value || '').trim(),
    })).filter((item) => item.key)
    env = parseJsonObject(form.env_text)
  } catch (error) {
    Message.warning(
      t('appStudio.abilities.mcp.advancedJsonError', { message: (error as Error).message }),
    )
    return
  }

  const toolNames = String(form.tool_names_text || '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
  const args = String(form.args_text || '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)

  const nextBinding: McpBindingForm = {
    ...defaultForm(),
    ...form,
    name: form.name.trim(),
    description: form.description.trim(),
    transport,
    url: String(form.url || '').trim(),
    command: String(form.command || '').trim(),
    enabled: Boolean(form.enabled),
    headers,
    tool_names: toolNames,
    timeout_seconds: Number(form.timeout_seconds || 30),
    args,
    env,
    headers_text: JSON.stringify(headers, null, 2),
    tool_names_text: toolNames.join(', '),
    args_text: args.join(', '),
    env_text: JSON.stringify(env, null, 2),
  }

  const newBindings = [...activateMcpBindings.value]
  if (editingIndex.value === -1) {
    if (newBindings.length >= 5) {
      Message.warning(t('appStudio.abilities.mcp.maxReached'))
      return
    }
    newBindings.push(nextBinding)
  } else {
    newBindings.splice(editingIndex.value, 1, nextBinding)
  }

  isSavingMcpBinding.value = true
  try {
    await handleUpdateDraftAppConfig(props.app_id, {
      mcp_bindings: newBindings.map((item) => stripBindingForm(item)),
    })

    syncLocalBindings(newBindings)
    await nextTick()
    emits('update:mcp_bindings', cloneDeep(newBindings.map((item) => stripBindingForm(item))))
    emits('reload-draft-app-config')
    closeMcpBindingsModal()
  } finally {
    isSavingMcpBinding.value = false
  }
}

const handleDeleteBinding = async (idx: number) => {
  const newBindings = [...activateMcpBindings.value]
  newBindings.splice(idx, 1)

  await handleUpdateDraftAppConfig(props.app_id, {
    mcp_bindings: newBindings.map((item) => stripBindingForm(item)),
  })

  syncLocalBindings(newBindings)
  emits('update:mcp_bindings', cloneDeep(newBindings.map((item) => stripBindingForm(item))))
  emits('reload-draft-app-config')
}

const saveMarketplaceBinding = async (binding: McpBinding) => {
  const nextBinding = normalizeBindingToForm(binding)
  const duplicate = activateMcpBindings.value.some((item) => isSameBinding(item, nextBinding))
  if (duplicate) {
    Message.warning(t('appStudio.abilities.mcp.duplicateWarning'))
    return
  }

  if (activateMcpBindings.value.length >= 5) {
    Message.warning(t('appStudio.abilities.mcp.maxReached'))
    return
  }

  const newBindings = [...activateMcpBindings.value, nextBinding]
  await handleUpdateDraftAppConfig(props.app_id, {
    mcp_bindings: newBindings.map((item) => stripBindingForm(item)),
  })

  syncLocalBindings(newBindings)
  await nextTick()
  emits('update:mcp_bindings', cloneDeep(newBindings.map((item) => stripBindingForm(item))))
  emits('reload-draft-app-config')
  Message.success(t('appStudio.abilities.mcp.addedSuccess'))
  showMarketplacePickerModal.value = false
}

let marketplaceBindingSaveQueue: Promise<void> = Promise.resolve()
const handleSelectMarketplaceBinding = (binding: McpBinding) => {
  const queuedSave = marketplaceBindingSaveQueue.then(() => saveMarketplaceBinding(binding))
  marketplaceBindingSaveQueue = queuedSave.catch(() => {})
  return queuedSave
}

watch(
  () => props.mcp_bindings,
  (newValue) => {
    const initData = (newValue || []).map((binding) => normalizeBindingToForm(binding))
    if (!isMcpBindingsInit.value || !hasLocalMcpBindingChanges.value) {
      activateMcpBindings.value = cloneDeep(initData)
      originMcpBindings.value = cloneDeep(initData)
      isMcpBindingsInit.value = true
    }
  },
  { immediate: true, deep: true },
)
</script>

<template>
  <a-collapse-item key="mcp_bindings" class="app-ability-item">
    <template #header>
      <div class="text-gray-700 font-bold">{{ t('appStudio.abilities.mcp.title') }}</div>
    </template>
    <template #extra>
      <a-button size="mini" type="text" class="!text-gray-700" @click.stop="openMarketplacePicker">
        <template #icon>
          <icon-plus />
        </template>
      </a-button>
    </template>

    <div v-if="activateMcpBindings.length > 0" class="flex flex-col gap-2">
      <div
        v-for="(binding, idx) in activateMcpBindings"
        :key="`${binding.name}-${idx}`"
        class="flex items-start justify-between gap-3 bg-white p-3 rounded-lg cursor-pointer hover:shadow-sm group"
        @click="openEditModal(idx)"
      >
        <div class="flex items-start gap-3 min-w-0 flex-1">
          <a-avatar
            :size="34"
            shape="square"
            class="shrink-0 overflow-hidden"
            :style="binding.icon ? { backgroundColor: '#f3f4f6' } : getBindingAvatarStyle(binding)"
          >
            <img
              v-if="binding.icon"
              :src="normalizeIconUrl(binding.icon)"
              :alt="binding.label || binding.name"
              class="w-full h-full object-cover"
            />
            <span v-else class="text-white font-semibold text-[12px] tracking-wide">
              {{ getBindingAvatarText(binding) }}
            </span>
          </a-avatar>
          <div class="flex flex-col gap-1 min-w-0 flex-1">
            <div class="flex items-center gap-2 min-w-0">
              <div class="text-gray-700 font-bold truncate">{{ binding.name }}</div>
              <div class="flex items-center gap-1 flex-shrink-0">
                <a-tag size="small" :color="getBindingStatus(binding).color">
                  {{ getBindingStatus(binding).label }}
                </a-tag>
                <a-tooltip
                  v-if="getBindingStatus(binding).show_help && getBindingStatus(binding).tooltip"
                  :content="getBindingStatus(binding).tooltip"
                  position="top"
                >
                  <icon-question-circle class="text-gray-400 text-sm" />
                </a-tooltip>
              </div>
              <a-tag size="small" color="arcoblue">{{ binding.transport }}</a-tag>
            </div>
            <div class="text-xs text-gray-500 truncate">{{ binding.description }}</div>
            <div class="text-xs text-gray-400 truncate">
              {{ binding.url || binding.command || t('appStudio.abilities.mcp.addressUnset') }}
            </div>
          </div>
        </div>
        <a-button
          size="mini"
          type="text"
          class="hidden group-hover:block flex-shrink-0 ml-2 !text-red-700 rounded"
          @click.stop="handleDeleteBinding(idx)"
        >
          <template #icon>
            <icon-delete />
          </template>
        </a-button>
      </div>
    </div>
    <div v-else class="text-xs text-gray-500 leading-[22px]">
      {{ t('appStudio.abilities.mcp.empty') }}
    </div>
  </a-collapse-item>

  <a-modal
    :visible="mcpBindingsModalVisible"
    hide-title
    :footer="false"
    :width="520"
    modal-class="h-[calc(100vh-32px)] right-4"
    @cancel="handleCancelMcpBindingsModal"
  >
    <div class="flex items-center justify-between mb-6">
      <div class="text-lg font-bold text-gray-700">
        {{
          editingIndex === -1
            ? t('appStudio.abilities.mcp.addModalTitle')
            : t('appStudio.abilities.mcp.editModalTitle')
        }}
      </div>
      <a-button type="text" class="!text-gray-700" size="small" :disabled="isSavingMcpBinding" @click="handleCancelMcpBindingsModal">
        <template #icon>
          <icon-close />
        </template>
      </a-button>
    </div>

    <div class="h-[calc(100vh-180px)] overflow-scroll scrollbar-w-none">
      <div class="space-y-3">
        <a-input v-model="bindingForm.name" :placeholder="t('appStudio.abilities.mcp.namePlaceholder')" />
        <a-textarea
          v-model="bindingForm.description"
          :auto-size="{ minRows: 2, maxRows: 4 }"
          :placeholder="t('appStudio.abilities.mcp.descriptionPlaceholder')"
        />
        <div class="grid grid-cols-2 gap-3">
          <a-select v-model="bindingForm.transport" placeholder="Transport">
            <a-option value="streamable_http">streamable_http</a-option>
            <a-option value="http">http</a-option>
            <a-option value="sse">sse</a-option>
            <a-option value="stdio">stdio</a-option>
          </a-select>
          <a-input-number
            v-model="bindingForm.timeout_seconds"
            :min="1"
            :max="600"
            :placeholder="t('appStudio.abilities.mcp.timeoutPlaceholder')"
          />
        </div>
        <a-input v-model="bindingForm.url" :placeholder="t('appStudio.abilities.mcp.urlPlaceholder')" />
        <a-input
          v-model="bindingForm.command"
          :placeholder="t('appStudio.abilities.mcp.commandPlaceholder')"
        />
        <a-switch v-model="bindingForm.enabled">
          <template #checked>{{ t('appStudio.abilities.mcp.enabledChecked') }}</template>
          <template #unchecked>{{ t('appStudio.abilities.mcp.enabledUnchecked') }}</template>
        </a-switch>
        <a-input
          v-model="bindingForm.tool_names_text"
          :placeholder="t('appStudio.abilities.mcp.toolNamesPlaceholder')"
        />
        <a-input
          v-model="bindingForm.args_text"
          :placeholder="t('appStudio.abilities.mcp.argsPlaceholder')"
        />
        <a-textarea
          v-model="bindingForm.headers_text"
          :auto-size="{ minRows: 3, maxRows: 8 }"
          :placeholder="t('appStudio.abilities.mcp.headersPlaceholder')"
        />
        <a-textarea
          v-model="bindingForm.env_text"
          :auto-size="{ minRows: 3, maxRows: 8 }"
          :placeholder="t('appStudio.abilities.mcp.envPlaceholder')"
        />
        <div class="flex justify-end gap-2 pt-2">
          <a-button :disabled="isSavingMcpBinding" @click="handleCancelMcpBindingsModal">{{ t('common.actions.cancel') }}</a-button>
          <a-button type="primary" :loading="isSavingMcpBinding" @click="handleSubmitBinding">{{ t('common.actions.save') }}</a-button>
        </div>
      </div>
    </div>
  </a-modal>

  <mcp-marketplace-picker-modal
    v-model:visible="showMarketplacePickerModal"
    :selected_bindings="activateMcpBindings"
    @select="handleSelectMarketplaceBinding"
  />
</template>

<style scoped>
</style>
