<script setup lang="ts">
import { computed, nextTick, onUnmounted, type PropType, ref, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import { cloneDeep, isEqual } from 'lodash'
import { apiPrefix } from '@/config'
import { useMarkdownRenderer } from '@/hooks/use-markdown-renderer'
import { useUpdateDraftAppConfig } from '@/hooks/use-app'
import type { SkillBinding, SkillPackage } from '@/models/skill'
import { getSkill } from '@/services/skill'
import { useI18n } from 'vue-i18n'
import { getStoreCategoryDisplayName } from '@/utils/store-display'
import 'github-markdown-css'
import SkillsMarketplacePickerModal from './SkillsMarketplacePickerModal.vue'

type SkillBindingForm = SkillBinding

const defaultBinding = (): SkillBindingForm => ({
  id: '',
  skill_id: '',
  source_key: '',
  name: '',
  label: '',
  icon: '',
  description: '',
  readme: '',
  category: '',
  tags: [],
  capabilities: {},
  executor_type: 'scf',
  tool_count: 0,
  tools: [],
  created_at: 0,
  updated_at: 0,
})

const props = defineProps({
  app_id: { type: String, default: '', required: true },
  skills: {
    type: Array as PropType<SkillBinding[]>,
    default: () => [],
    required: true,
  },
})

const { t, locale } = useI18n()
const emits = defineEmits(['update:skills'])
const { handleUpdateDraftAppConfig } = useUpdateDraftAppConfig()
const skillsModalVisible = ref(false)
const isSkillsInit = ref(false)
const activateSkills = ref<SkillBindingForm[]>([])
const originSkills = ref<SkillBindingForm[]>([])
const showMarketplacePickerModal = ref(false)
const skillDetailLoading = ref(false)
const skillDetail = ref<SkillPackage | null>(null)
let latestSkillDetailRequest = 0
const { renderMarkdown } = useMarkdownRenderer()
const skillDetailMarkdown = computed(() =>
  renderMarkdown(
    skillDetail.value?.readme || skillDetail.value?.description || t('appStudio.abilities.skills.noDescription'),
  ),
)

const avatarPalettes = [
  ['#334155', '#0f172a'],
  ['#0369a1', '#1d4ed8'],
  ['#047857', '#0f766e'],
  ['#c2410c', '#d97706'],
  ['#be123c', '#e11d48'],
  ['#0f766e', '#14b8a6'],
]

const getCategoryLabel = (category: string) => {
  return getStoreCategoryDisplayName(category, locale.value === 'en-US' ? 'en-US' : 'zh-CN')
}

const getExecutorLabel = (value: string) => {
  const normalized = String(value || '').trim()
  if (normalized === 'scf') return t('store.skills.executorTypes.scf')
  if (normalized === 'tool') return t('store.skills.executorTypes.tool')
  if (normalized === 'prompt') return t('store.skills.executorTypes.prompt')
  return normalized
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

const stripBindingForm = (binding: SkillBindingForm): SkillBinding => {
  return {
    ...binding,
    skill_id: String(binding.skill_id || binding.id || '').trim(),
  }
}

const normalizeBindingToForm = (binding: SkillBinding): SkillBindingForm => {
  return {
    ...defaultBinding(),
    ...binding,
    skill_id: String(binding.skill_id || binding.id || '').trim(),
  }
}

const normalizeSkillBindingsToForm = (bindings: SkillBinding[] = []): SkillBindingForm[] => {
  return bindings.map((binding) => normalizeBindingToForm(binding))
}

const openDetailModal = async (idx: number) => {
  const binding = activateSkills.value[idx]
  if (!binding) return

  const requestId = ++latestSkillDetailRequest
  skillsModalVisible.value = true
  skillDetailLoading.value = true

  try {
    const res = await getSkill(binding.skill_id || binding.id)
    if (requestId !== latestSkillDetailRequest) return
    skillDetail.value = res.data
  } catch (error: unknown) {
    if (requestId === latestSkillDetailRequest) {
      Message.error(error instanceof Error ? error.message : t('appStudio.abilities.skills.detailLoadFailed'))
      skillsModalVisible.value = false
    }
  } finally {
    if (requestId === latestSkillDetailRequest) skillDetailLoading.value = false
  }
}

const openMarketplacePicker = () => {
  showMarketplacePickerModal.value = true
}

const handleCloseSkillsModal = () => {
  latestSkillDetailRequest += 1
  skillsModalVisible.value = false
  skillDetail.value = null
  skillDetailLoading.value = false
}

onUnmounted(() => {
  latestSkillDetailRequest += 1
})

const persistSkills = async (newSkills: SkillBindingForm[]) => {
  await handleUpdateDraftAppConfig(props.app_id, {
    skills: newSkills.map((item) => stripBindingForm(item)),
  })

  activateSkills.value = cloneDeep(newSkills)
  originSkills.value = cloneDeep(newSkills)
  isSkillsInit.value = true
  await nextTick()
  emits('update:skills', cloneDeep(newSkills.map((item) => stripBindingForm(item))))
}

const handleDeleteSkill = async (idx: number) => {
  const newSkills = [...activateSkills.value]
  newSkills.splice(idx, 1)
  await persistSkills(newSkills)
}

const handleSelectMarketplaceSkill = async (skill: SkillPackage) => {
  const skillId = String(skill.id || '').trim()
  if (!skillId) return

  const duplicate = activateSkills.value.some((item) => String(item.skill_id || item.id || '').trim() === skillId)
  if (duplicate) {
    Message.warning(t('appStudio.abilities.skills.duplicateWarning'))
    return
  }

  const nextSkill = normalizeBindingToForm({
    ...skill,
    skill_id: skillId,
  })

  await persistSkills([...activateSkills.value, nextSkill])
  Message.success(t('appStudio.abilities.skills.addedSuccess'))
}

watch(
  () => props.skills,
  (newValue) => {
    const initData = normalizeSkillBindingsToForm(newValue || [])
    if (!isSkillsInit.value || !isEqual(initData, originSkills.value)) {
      activateSkills.value = cloneDeep(initData)
      originSkills.value = cloneDeep(initData)
      isSkillsInit.value = true
    }
  },
  { immediate: true, deep: true },
)
</script>

<template>
  <a-collapse-item key="skills" class="app-ability-item">
    <template #header>
      <div class="text-gray-700 font-bold">{{ t('appStudio.abilities.skills.title') }}</div>
    </template>
    <template #extra>
      <a-button size="mini" type="text" class="!text-gray-700" @click.stop="openMarketplacePicker">
        <template #icon>
          <icon-plus />
        </template>
      </a-button>
    </template>

    <div v-if="activateSkills.length > 0" class="flex flex-col gap-2">
      <div
        v-for="(skill, idx) in activateSkills"
        :key="`${skill.skill_id || skill.id}-${idx}`"
        class="flex items-start justify-between gap-3 bg-white p-3 rounded-lg cursor-pointer hover:shadow-sm group"
        @click="openDetailModal(idx)"
      >
        <div class="flex items-start gap-3 min-w-0 flex-1">
          <a-avatar :size="36" shape="square" class="rounded flex-shrink-0 bg-gray-100">
            <img
              v-if="skill.icon"
              :src="normalizeIconUrl(skill.icon)"
              :alt="skill.label"
              class="w-full h-full object-cover"
            />
            <span v-else class="text-gray-700 font-semibold">
              {{ (skill.label || skill.name || 'S')[0] }}
            </span>
          </a-avatar>
          <div class="flex flex-col flex-1 min-w-0 gap-1">
            <div class="flex items-center gap-2 min-w-0">
              <div class="text-gray-700 font-bold truncate">{{ skill.label }}</div>
            </div>
            <div class="text-xs text-gray-500 truncate">
              {{ skill.source_key }}
              <template v-if="skill.tool_count > 0">
                · {{ t('appStudio.abilities.readonly.toolCount', { count: skill.tool_count }) }}
              </template>
              · {{ getExecutorLabel(skill.executor_type) }}
            </div>
            <div class="text-xs text-gray-400 truncate">
              {{ skill.description || t('appStudio.abilities.skills.noDescription') }}
            </div>
          </div>
        </div>
        <a-button
          size="mini"
          type="text"
          class="hidden group-hover:block flex-shrink-0 ml-2 !text-red-700 rounded"
          @click.stop="handleDeleteSkill(idx)"
        >
          <template #icon>
            <icon-delete />
          </template>
        </a-button>
      </div>
    </div>
    <div v-else class="text-xs text-gray-500 leading-[22px]">
      {{ t('appStudio.abilities.skills.empty') }}
    </div>
  </a-collapse-item>

  <a-modal
    :visible="skillsModalVisible"
    hide-title
    :footer="false"
    :width="560"
    modal-class="h-[calc(100vh-32px)] right-4"
    @cancel="handleCloseSkillsModal"
  >
    <div class="flex items-center justify-between mb-6">
      <div class="text-lg font-bold text-gray-700">
        {{ skillDetail ? skillDetail.label : t('appStudio.abilities.skills.detailTitle') }}
      </div>
      <a-button type="text" class="!text-gray-700" size="small" @click="handleCloseSkillsModal">
        <template #icon>
          <icon-close />
        </template>
      </a-button>
    </div>

    <a-spin :loading="skillDetailLoading" class="block h-[calc(100vh-180px)] overflow-hidden">
      <div class="h-[calc(100vh-180px)] overflow-scroll scrollbar-w-none">
        <div v-if="skillDetail" class="space-y-3">
          <div class="rounded-lg bg-gray-50 p-3">
            <div class="flex items-center gap-3 mb-2">
              <a-avatar :size="36" shape="square" class="bg-white">
                <img
                  v-if="skillDetail.icon"
                  :src="normalizeIconUrl(skillDetail.icon)"
                  :alt="skillDetail.label"
                  class="w-full h-full object-cover"
                />
                <span v-else class="text-gray-700 font-semibold">
                  {{ (skillDetail.label || skillDetail.name || 'S')[0] }}
                </span>
              </a-avatar>
              <div class="min-w-0">
                <div class="font-semibold text-gray-800 truncate">{{ skillDetail.label }}</div>
                <div class="text-xs text-gray-500 truncate">{{ skillDetail.source_key }} · {{ getCategoryLabel(skillDetail.category) }}</div>
              </div>
            </div>
            <div class="markdown-body skill-markdown max-h-56 overflow-auto" v-html="skillDetailMarkdown" />
          </div>

          <div class="grid grid-cols-2 gap-3">
            <div class="rounded-lg bg-white p-3">
              <div class="text-xs text-gray-500 mb-1">{{ t('appStudio.abilities.skills.executor') }}</div>
              <div class="text-sm text-gray-800">{{ getExecutorLabel(skillDetail.executor_type) }}</div>
            </div>
            <div class="rounded-lg bg-white p-3">
              <div class="text-xs text-gray-500 mb-1">{{ t('appStudio.abilities.skills.toolCount') }}</div>
              <div class="text-sm text-gray-800">{{ skillDetail.tool_count }}</div>
            </div>
          </div>

          <div v-if="skillDetail.tools.length > 0">
            <div class="text-sm font-bold text-gray-700 mb-2">
              {{ t('appStudio.abilities.skills.includedTools') }}
            </div>
            <div class="space-y-2">
              <a-card
                v-for="tool in skillDetail.tools"
                :key="tool.name"
                class="rounded-lg"
                :body-style="{ padding: '12px' }"
              >
                <div class="font-semibold text-gray-900">{{ tool.label }}</div>
                <div class="text-xs text-gray-500 mt-1">{{ tool.description }}</div>
              </a-card>
            </div>
          </div>

          <div class="flex items-center justify-end gap-2 pt-2">
            <a-button type="primary" @click="handleCloseSkillsModal">
              {{ t('common.actions.close') }}
            </a-button>
          </div>
        </div>
        <a-tag v-else color="arcoblue">{{ t('appStudio.abilities.skills.loadingDetail') }}</a-tag>
      </div>
    </a-spin>
  </a-modal>

  <skills-marketplace-picker-modal
    v-model:visible="showMarketplacePickerModal"
    :selected_bindings="activateSkills"
    @select="handleSelectMarketplaceSkill"
  />
</template>

<style scoped>
.scrollbar-w-none {
  scrollbar-width: none;
  -ms-overflow-style: none;
}

.scrollbar-w-none::-webkit-scrollbar {
  display: none;
}

.skill-markdown :deep(h1),
.skill-markdown :deep(h2),
.skill-markdown :deep(h3),
.skill-markdown :deep(h4),
.skill-markdown :deep(h5),
.skill-markdown :deep(h6) {
  margin-top: 1rem;
}

.skill-markdown :deep(p):first-child {
  margin-top: 0;
}

.skill-markdown :deep(ul),
.skill-markdown :deep(ol) {
  padding-left: 1.25rem;
}
</style>
