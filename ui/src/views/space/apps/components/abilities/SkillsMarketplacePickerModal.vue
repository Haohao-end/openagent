<script setup lang="ts">
import { computed, onMounted, ref, watch, type PropType } from 'vue'
import { Message } from '@arco-design/web-vue'
import { apiPrefix } from '@/config'
import { getErrorMessage } from '@/utils/error'
import { getSkillCategories, getSkillsWithPage } from '@/services/skill'
import type { SkillBinding, SkillCategory, SkillPackage } from '@/models/skill'
import { useI18n } from 'vue-i18n'
import { getStoreCategoryDisplayName } from '@/utils/store-display'

type PaginatorState = {
  total_page: number
  total_record: number
  current_page: number
  page_size: number
}

const PAGE_SIZE = 50

const props = defineProps({
  visible: { type: Boolean, default: false },
  selected_bindings: {
    type: Array as PropType<SkillBinding[]>,
    default: () => [],
  },
})

const { t, locale } = useI18n()
const emits = defineEmits(['update:visible', 'select'])

const loading = ref(false)
const categories = ref<SkillCategory[]>([])
const skills = ref<SkillPackage[]>([])
const selectedCategory = ref('all')
const searchWord = ref('')
const paginator = ref<PaginatorState>({
  total_page: 0,
  total_record: 0,
  current_page: 0,
  page_size: PAGE_SIZE,
})
let latestSkillsRequest = 0

const hideModal = () => emits('update:visible', false)

const selectedSkillIdSet = computed(() => {
  const set = new Set<string>()
  ;(props.selected_bindings || []).forEach((binding) => {
    const skillId = String(binding.skill_id || binding.id || '').trim()
    if (skillId) {
      set.add(skillId)
    }
  })
  return set
})

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

const isSelectedSkill = (skill: SkillPackage) => {
  return selectedSkillIdSet.value.has(String(skill.id || '').trim())
}

const getCategoryLabel = (category: string) => {
  return getStoreCategoryDisplayName(category, locale.value as 'zh-CN' | 'en-US')
}

const getExecutorLabel = (executorType: string) => {
  const normalized = String(executorType || '').trim()
  if (normalized === 'scf') return t('store.skills.executorTypes.scf')
  if (normalized === 'tool') return t('store.skills.executorTypes.tool')
  if (normalized === 'prompt') return t('store.skills.executorTypes.prompt')
  return normalized
}

const loadCategories = async () => {
  try {
    const res = await getSkillCategories()
    categories.value = res.data.categories || []
  } catch (_error: unknown) {
    categories.value = []
  }
}

const loadSkills = async (reset = false) => {
  if (loading.value && !reset) return
  if (!reset && paginator.value.current_page > 0 && paginator.value.current_page >= paginator.value.total_page) {
    return
  }

  const nextPage = reset ? 1 : paginator.value.current_page + 1 || 1
  const requestId = ++latestSkillsRequest
  loading.value = true
  try {
    if (reset) {
      skills.value = []
      paginator.value = {
        total_page: 0,
        total_record: 0,
        current_page: 0,
        page_size: PAGE_SIZE,
      }
    }

    const res = await getSkillsWithPage({
      current_page: nextPage,
      page_size: PAGE_SIZE,
      search_word: searchWord.value.trim(),
      category: selectedCategory.value === 'all' ? '' : selectedCategory.value,
    })
    if (requestId !== latestSkillsRequest) return
    skills.value = reset ? (res.data.list || []) : [...skills.value, ...(res.data.list || [])]
    paginator.value = res.data.paginator || {
      total_page: nextPage,
      total_record: skills.value.length,
      current_page: nextPage,
      page_size: PAGE_SIZE,
    }
  } catch (error: unknown) {
    if (requestId === latestSkillsRequest) {
      Message.error(getErrorMessage(error, t('appStudio.abilities.skills.loadMarketplaceFailed')))
    }
  } finally {
    if (requestId === latestSkillsRequest) loading.value = false
  }
}

const handleSearch = async () => {
  await loadSkills(true)
}

const handleCategoryChange = async (category: string) => {
  selectedCategory.value = category
  await loadSkills(true)
}

const handleSelect = (skill: SkillPackage) => {
  if (isSelectedSkill(skill)) return
  emits('select', skill)
}

const handleScroll = (event: Event) => {
  const { scrollTop, scrollHeight, clientHeight } = event.target as HTMLElement
  if (scrollTop + clientHeight < scrollHeight - 10) return
  if (loading.value || paginator.value.current_page >= paginator.value.total_page) return
  void loadSkills()
}

watch(
  () => props.visible,
  async (visible) => {
    if (!visible) return
    await loadCategories()
    await loadSkills(true)
  },
  { immediate: true },
)

onMounted(async () => {
  await loadCategories()
})
</script>

<template>
  <a-modal
    :visible="props.visible"
    :footer="false"
    hide-title
    :width="980"
    class="tools-modal"
    modal-class="right-4 app-tools-modal-shell"
    @cancel="hideModal"
  >
    <div class="flex w-full h-full flex-col md:flex-row">
      <div
        class="flex flex-col flex-shrink-0 bg-gray-50 w-full md:w-56 lg:w-64 h-full px-3 py-4 overflow-auto scrollbar-w-none"
      >
        <div class="text-gray-900 font-bold text-lg mb-2">{{ t('appStudio.abilities.skills.addTitle') }}</div>
        <div class="text-xs text-gray-500 mb-4">{{ t('appStudio.abilities.skills.addDescription') }}</div>
        <div class="flex flex-col gap-1 mb-4">
          <div
            data-testid="skills-category-all"
            :class="`rounded-lg h-8 leading-8 px-3 flex items-center gap-2 cursor-pointer hover:bg-white hover:text-blue-700 ${selectedCategory === 'all' ? 'text-blue-700 bg-white' : 'text-gray-700'}`"
            @click="handleCategoryChange('all')"
          >
            <icon-apps />
            {{ t('appStudio.abilities.skills.all') }}
          </div>
          <div
            v-for="item in categories"
            :key="item.id"
            :data-testid="`skills-category-${item.id}`"
            :class="`rounded-lg h-8 leading-8 px-3 flex items-center gap-2 cursor-pointer hover:bg-white hover:text-blue-700 ${selectedCategory === item.id ? 'text-blue-700 bg-white' : 'text-gray-700'}`"
            @click="handleCategoryChange(item.id)"
          >
            <icon-apps />
            {{ getCategoryLabel(item.id || item.name) }}
          </div>
        </div>
        <div class="text-xs text-gray-500 leading-5">
          {{ t('appStudio.abilities.skills.publishedOnly') }}
        </div>
      </div>

      <div class="flex-1 p-4 min-w-0 flex flex-col overflow-hidden">
        <div class="w-full flex items-center justify-between gap-2 mb-7">
          <div class="text-lg font-bold text-gray-700">{{ t('appStudio.abilities.skills.marketplaceTitle') }}</div>
          <a-input-search
            v-model="searchWord"
            :placeholder="t('appStudio.abilities.skills.searchPlaceholder')"
            class="w-full sm:w-[280px] bg-white rounded-lg border-gray-300"
            @search="handleSearch"
          />
        </div>

        <a-spin :loading="loading" class="block flex-1 min-w-0 overflow-hidden">
          <div data-testid="skills-binding-list" class="block app-modal-list-scroll scrollbar-w-none" @scroll="handleScroll">
            <div class="flex flex-col gap-2 pr-1">
              <div
                v-for="skill in skills"
                :key="skill.id"
                :class="`flex items-start justify-between gap-3 px-3 py-3 rounded-lg border cursor-pointer hover:bg-blue-50 hover:border-blue-700 ${isSelectedSkill(skill) ? 'bg-blue-50 border-blue-700' : 'bg-white border-gray-200'}`"
              >
                <div class="flex items-start gap-3 min-w-0 flex-1">
                  <a-avatar :size="40" shape="square" class="bg-gray-100 flex-shrink-0">
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
                    <div class="flex items-center gap-2 min-w-0 flex-wrap">
                      <div class="text-sm font-semibold text-gray-900 truncate">{{ skill.label }}</div>
                      <a-tag size="small" color="arcoblue">{{ getCategoryLabel(skill.category) }}</a-tag>
                      <a-tag size="small" color="orangered">{{ getExecutorLabel(skill.executor_type) }}</a-tag>
                    </div>
                    <div class="text-xs text-gray-500 truncate">
                      {{ skill.source_key }}
                      <template v-if="skill.tool_count > 0">
                        · {{ t('appStudio.abilities.readonly.toolCount', { count: skill.tool_count }) }}
                      </template>
                    </div>
                    <div class="text-sm text-gray-600 line-clamp-2">
                      {{ skill.description || t('appStudio.abilities.skills.noDescription') }}
                    </div>
                  </div>
                </div>

                <div class="flex flex-col items-end gap-2 flex-shrink-0">
                  <a-button
                    type="primary"
                    size="small"
                    :disabled="isSelectedSkill(skill)"
                    @click.stop="handleSelect(skill)"
                  >
                    {{
                      isSelectedSkill(skill)
                        ? t('appStudio.abilities.skills.added')
                        : t('appStudio.abilities.skills.addToApp')
                    }}
                  </a-button>
                </div>
              </div>

              <a-empty
                v-if="skills.length === 0"
                :description="t('appStudio.abilities.skills.noAvailable')"
                class="py-20"
              />

              <div v-if="paginator.total_page >= 2" class="w-full">
                <div v-if="loading" class="text-center py-4">
                  <a-space>
                    <a-spin />
                    <div class="text-gray-400">{{ t('appStudio.list.loading') }}</div>
                  </a-space>
                </div>
                <div v-else-if="paginator.current_page >= paginator.total_page" class="text-center py-4">
                  <div class="text-gray-400">{{ t('appStudio.list.loadedAll') }}</div>
                </div>
              </div>
            </div>
          </div>
        </a-spin>
      </div>
    </div>
  </a-modal>
</template>

<style scoped>
.line-clamp-1 {
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
