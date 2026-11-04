<script setup lang="ts">
import { nextTick, type PropType, ref, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import { cloneDeep, isEqual } from 'lodash'
import { apiPrefix } from '@/config'
import { useUpdateDraftAppConfig } from '@/hooks/use-app'
import type { AgentBinding, AgentBindingRequest } from '@/models/app'
import { useI18n } from 'vue-i18n'
import AgentBindingsMarketplacePickerModal from './AgentBindingsMarketplacePickerModal.vue'

type AgentBindingForm = AgentBinding

type AgentBindingTarget = {
  app_id: string
  name: string
  icon: string
  description: string
  source_scope: 'public' | 'own'
  invoke_mode: 'a2a' | 'tool'
  is_public: boolean
  status: string
}

const defaultBinding = (): AgentBindingForm => ({
  app_id: '',
  invoke_mode: 'tool',
  name: '',
  icon: '',
  description: '',
  source_scope: 'own',
  is_public: false,
  status: '',
  tool_name: '',
})

const props = defineProps({
  app_id: { type: String, default: '', required: true },
  agent_bindings: {
    type: Array as PropType<AgentBinding[]>,
    default: () => [],
    required: true,
  },
})

const { t } = useI18n()
const emits = defineEmits(['update:agent_bindings'])
const { handleUpdateDraftAppConfig } = useUpdateDraftAppConfig()
const showMarketplacePickerModal = ref(false)
const isAgentBindingsInit = ref(false)
const activateAgentBindings = ref<AgentBindingForm[]>([])
const originAgentBindings = ref<AgentBindingForm[]>([])

const stripBindingForm = (_binding: AgentBindingForm): AgentBindingRequest => {
  return {
    app_id: String(_binding.app_id || '').trim(),
  }
}

const normalizeBindingToForm = (binding: AgentBinding): AgentBindingForm => {
  return {
    ...defaultBinding(),
    ...binding,
    app_id: String(binding.app_id || '').trim(),
    invoke_mode: binding.invoke_mode || 'tool',
    source_scope: binding.source_scope || 'own',
  }
}

const normalizeAgentBindingsToForm = (bindings: AgentBinding[] = []): AgentBindingForm[] => {
  return bindings.map((binding) => normalizeBindingToForm(binding))
}

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

const syncLocalBindings = (newBindings: AgentBindingForm[]) => {
  const normalized = cloneDeep(newBindings)
  originAgentBindings.value = normalized
  activateAgentBindings.value = cloneDeep(normalized)
  isAgentBindingsInit.value = true
}

const openMarketplacePicker = () => {
  showMarketplacePickerModal.value = true
}

const persistAgentBindings = async (newBindings: AgentBindingForm[]) => {
  await handleUpdateDraftAppConfig(props.app_id, {
    agent_bindings: newBindings.map((binding) => stripBindingForm(binding)),
  })

  syncLocalBindings(newBindings)
  await nextTick()
  emits('update:agent_bindings', cloneDeep(newBindings))
}

const handleDeleteBinding = async (idx: number) => {
  const newBindings = [...activateAgentBindings.value]
  newBindings.splice(idx, 1)
  await persistAgentBindings(newBindings)
}

const saveMarketplaceAgentBinding = async (binding: AgentBindingTarget) => {
  const appId = String(binding.app_id || '').trim()
  if (!appId) return

  const duplicate = activateAgentBindings.value.some((item) => String(item.app_id || '').trim() === appId)
  if (duplicate) {
    Message.warning(t('appStudio.abilities.agents.duplicateWarning'))
    return
  }

  const nextBinding = normalizeBindingToForm({
    app_id: appId,
    name: binding.name,
    icon: binding.icon,
    description: binding.description,
    source_scope: binding.source_scope,
    invoke_mode: binding.invoke_mode,
    is_public: binding.is_public,
    status: binding.status,
  })

  await persistAgentBindings([...activateAgentBindings.value, nextBinding])
  Message.success(t('appStudio.abilities.agents.addedSuccess'))
}

let marketplaceAgentSaveQueue: Promise<void> = Promise.resolve()
const handleSelectMarketplaceBinding = (binding: AgentBindingTarget) => {
  const queuedSave = marketplaceAgentSaveQueue.then(() => saveMarketplaceAgentBinding(binding))
  marketplaceAgentSaveQueue = queuedSave.catch(() => {})
  return queuedSave
}

watch(
  () => props.agent_bindings,
  (newValue) => {
    const initData = normalizeAgentBindingsToForm(newValue || [])
    if (!isAgentBindingsInit.value || !isEqual(initData, originAgentBindings.value)) {
      activateAgentBindings.value = cloneDeep(initData)
      originAgentBindings.value = cloneDeep(initData)
      isAgentBindingsInit.value = true
    }
  },
  { immediate: true, deep: true },
)
</script>

<template>
  <a-collapse-item key="agent_bindings" class="app-ability-item w-full min-w-0">
    <template #header>
      <div class="text-gray-700 font-bold">{{ t('appStudio.abilities.agents.title') }}</div>
    </template>
    <template #extra>
      <a-button size="mini" type="text" class="!text-gray-700" @click.stop="openMarketplacePicker">
        <template #icon>
          <icon-plus />
        </template>
      </a-button>
    </template>

    <div v-if="activateAgentBindings.length > 0" class="flex flex-col gap-2 min-w-0">
      <div
        v-for="(binding, idx) in activateAgentBindings"
        :key="`${binding.app_id}-${idx}`"
        class="flex items-start justify-between gap-3 bg-white p-3 rounded-lg group min-w-0 w-full"
      >
        <div class="flex items-start gap-3 min-w-0 flex-1">
          <a-avatar :size="36" shape="square" class="rounded flex-shrink-0 bg-gray-100">
            <img
              v-if="binding.icon"
              :src="normalizeIconUrl(binding.icon)"
              :alt="binding.name"
              class="w-full h-full object-cover"
            />
            <span v-else class="text-gray-700 font-semibold">
              {{ (binding.name || 'A')[0] }}
            </span>
          </a-avatar>
          <div class="flex flex-col flex-1 min-w-0 gap-1">
            <div class="flex items-center gap-2 min-w-0">
              <div class="text-gray-700 font-bold truncate">{{ binding.name }}</div>
              <a-tag size="small" :color="binding.invoke_mode === 'a2a' ? 'arcoblue' : 'orange'">
                {{ binding.invoke_mode === 'a2a' ? 'A2A' : 'Tool' }}
              </a-tag>
            </div>
            <div class="text-xs text-gray-500 truncate">
              {{ binding.source_scope === 'public' ? t('appStudio.abilities.sourcePublic') : t('appStudio.abilities.sourceOwn') }}
              <template v-if="binding.is_public"> · {{ t('appStudio.abilities.publicApp') }}</template>
              <template v-else> · {{ t('appStudio.abilities.privateApp') }}</template>
            </div>
            <div class="text-xs text-gray-400 truncate">
              {{ binding.description || t('appStudio.abilities.emptyDescription') }}
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
      {{ t('appStudio.abilities.agents.empty') }}
    </div>
  </a-collapse-item>

  <agent-bindings-marketplace-picker-modal
    v-model:visible="showMarketplacePickerModal"
    :selected_bindings="activateAgentBindings"
    :current_app_id="props.app_id"
    @select="handleSelectMarketplaceBinding"
  />
</template>
