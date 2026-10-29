<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Message } from '@arco-design/web-vue'
import { apiPrefix } from '@/config'
import CardGridSkeleton from '@/components/skeletons/CardGridSkeleton.vue'
import ResourceCardDescription from '@/components/ResourceCardDescription.vue'
import { useMarkdownRenderer } from '@/hooks/use-markdown-renderer'
import { getErrorMessage } from '@/utils/error'
import 'github-markdown-css'
import { getSkillCategories, getSkill, getSkillsWithPage } from '@/services/skill'
import type { SkillCategory, SkillPackage } from '@/models/skill'
import { getSkillCategoryDisplayName } from '@/utils/store-display'

const { t, locale } = useI18n()
const loading = ref(false)
const categories = ref<SkillCategory[]>([])
const skills = ref<SkillPackage[]>([])
const selectedCategory = ref('all')
const searchWord = ref('')
const page = ref(1)
const pageSize = ref(20)
const hasMore = ref(true)
let latestSkillsRequest = 0
const showDetailVisible = ref(false)
const detailLoading = ref(false)
const activeSkill = ref<SkillPackage | null>(null)
let latestSkillDetailRequest = 0
const { renderMarkdown } = useMarkdownRenderer()
const avatarPalettes = [
  ['#334155', '#0f172a'],
  ['#0369a1', '#1d4ed8'],
  ['#047857', '#0f766e'],
  ['#c2410c', '#d97706'],
  ['#be123c', '#e11d48'],
  ['#0f766e', '#14b8a6'],
]

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

const loadCategories = async () => {
  try {
    const res = await getSkillCategories()
    categories.value = res.data.categories || []
  } catch (_error: unknown) {
    categories.value = []
  }
}

const loadSkills = async (force = false) => {
  if (loading.value && !force) return
  if (!hasMore.value && page.value > 1) return

  const requestId = ++latestSkillsRequest
  const requestPage = page.value
  loading.value = true
  try {
    const res = await getSkillsWithPage({
      current_page: requestPage,
      page_size: pageSize.value,
      search_word: searchWord.value.trim(),
      category: selectedCategory.value === 'all' ? '' : selectedCategory.value,
    })
    if (requestId !== latestSkillsRequest) return
    const list = res.data.list || []
    if (requestPage === 1) {
      skills.value = list
    } else {
      skills.value.push(...list)
    }
    hasMore.value = requestPage < res.data.paginator.total_page
  } catch (error: unknown) {
    if (requestId === latestSkillsRequest) {
      if (requestPage > 1) page.value = requestPage - 1
      Message.error(getErrorMessage(error, t('store.skills.loadFailed')))
    }
  } finally {
    if (requestId === latestSkillsRequest) loading.value = false
  }
}

const refreshSkills = async () => {
  page.value = 1
  hasMore.value = true
  await loadSkills(true)
}

const handleCategoryChange = async (category: string) => {
  selectedCategory.value = category
  await refreshSkills()
}

const handleSearch = async () => {
  await refreshSkills()
}

const handleScroll = (event: Event) => {
  const target = event.target as HTMLElement | null
  if (!target) return
  const { scrollTop, scrollHeight, clientHeight } = target
  if (scrollTop + clientHeight >= scrollHeight - 10) {
    if (loading.value || !hasMore.value) return
    page.value += 1
    void loadSkills()
  }
}

const loadSkillDetail = async (skillId: string) => {
  const requestId = ++latestSkillDetailRequest
  detailLoading.value = true
  showDetailVisible.value = true
  try {
    const res = await getSkill(skillId)
    if (requestId !== latestSkillDetailRequest) return
    activeSkill.value = res.data
  } catch (error: unknown) {
    if (requestId === latestSkillDetailRequest) {
      Message.error(getErrorMessage(error, t('store.skills.detailLoadFailed')))
      showDetailVisible.value = false
    }
  } finally {
    if (requestId === latestSkillDetailRequest) detailLoading.value = false
  }
}

const handleCardClick = async (skill: SkillPackage) => {
  await loadSkillDetail(skill.id)
}

const hashString = (value: string) => {
  let hash = 0
  for (let i = 0; i < value.length; i += 1) {
    hash = (hash * 33 + value.charCodeAt(i)) >>> 0
  }
  return hash
}

const getSkillAvatarText = (skill: SkillPackage) => {
  const source = (skill.label || skill.name || skill.source_key || 'SK').trim()
  const latinParts = source.match(/[A-Za-z0-9]+/g)
  if (latinParts && latinParts.length > 0) {
    return latinParts
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase())
      .join('')
  }

  const chineseParts = source.match(/[\u4e00-\u9fff]/g)
  if (chineseParts && chineseParts.length > 0) {
    return chineseParts.slice(0, 2).join('')
  }

  return source.slice(0, 2).toUpperCase()
}

const getSkillAvatarStyle = (skill: SkillPackage) => {
  const palette = avatarPalettes[hashString(`${skill.category}:${skill.source_key}:${skill.label}`) % avatarPalettes.length]
  return {
    background: `linear-gradient(135deg, ${palette[0]} 0%, ${palette[1]} 100%)`,
    boxShadow: 'inset 0 1px 0 rgba(255, 255, 255, 0.15)',
  }
}

const detailMarkdown = computed(() =>
  renderMarkdown(activeSkill.value?.readme || activeSkill.value?.description || t('store.skills.noBody')),
)

const getCategoryLabel = (category: string) => {
  return getSkillCategoryDisplayName(category, locale.value as 'zh-CN' | 'en-US')
}

const getExecutorTypeLabel = (value: string) => {
  const normalized = String(value || '').trim()
  if (!normalized) return ''

  if (normalized === 'scf') return t('store.skills.executorTypes.scf')
  if (normalized === 'tool') return t('store.skills.executorTypes.tool')
  if (normalized === 'prompt') return t('store.skills.executorTypes.prompt')
  return normalized
}

onMounted(async () => {
  await loadCategories()
  await loadSkills()
})
</script>

<template>
  <a-spin :loading="loading" class="block h-full w-full overflow-hidden">
    <div class="p-6 flex flex-col h-full min-h-0 overflow-hidden">
      <div class="flex items-center justify-between mb-5 flex-wrap gap-2">
        <div class="flex items-center gap-2">
          <a-avatar :size="32" class="bg-blue-700">
            <icon-storage :size="18" />
          </a-avatar>
          <div>
            <div class="text-lg font-medium text-gray-900">{{ t('store.skills.title') }}</div>
          </div>
        </div>
      </div>

      <div class="flex items-center justify-between mb-5 flex-wrap gap-2">
        <div class="flex items-center gap-2 flex-wrap">
          <a-button
            :type="selectedCategory === 'all' ? 'secondary' : 'text'"
            class="rounded-lg !text-gray-700 px-3"
            @click="handleCategoryChange('all')"
          >
            {{ t('store.skills.all') }}
          </a-button>
          <a-button
            v-for="item in categories"
            :key="item.id"
            :type="selectedCategory === item.id ? 'secondary' : 'text'"
            class="rounded-lg !text-gray-700 px-3"
            @click="handleCategoryChange(item.id)"
          >
            {{ getCategoryLabel(item.id || item.name) }}
          </a-button>
        </div>

        <a-input-search
          v-model="searchWord"
          :placeholder="t('store.skills.searchPlaceholder')"
          class="w-[240px] shrink-0 bg-white rounded-lg border-gray-300"
          @search="handleSearch"
        />
      </div>

      <card-grid-skeleton v-if="loading && skills.length === 0" :count="8" />
      <div v-else class="flex-1 min-h-0 overflow-y-auto overflow-x-hidden scrollbar-hide" @scroll="handleScroll">
        <a-row :gutter="[16, 16]">
          <a-col v-for="skill in skills" :key="skill.id" :xs="24" :sm="12" :md="8" :lg="6" :xl="6">
            <a-card
              hoverable
              class="cursor-pointer rounded-lg h-full overflow-hidden"
              :body-style="{ padding: '10px' }"
              @click="handleCardClick(skill)"
            >
              <div class="flex items-start gap-2.5 mb-2">
                <a-avatar
                  :size="34"
                  shape="square"
                  class="shrink-0 overflow-hidden"
                  :style="skill.icon ? { backgroundColor: '#f3f4f6' } : getSkillAvatarStyle(skill)"
                >
                  <img
                    v-if="skill.icon"
                    :src="normalizeIconUrl(skill.icon)"
                    :alt="skill.label"
                    class="w-full h-full object-cover"
                  />
                  <span v-else class="text-white font-semibold text-[12px] tracking-wide">
                    {{ getSkillAvatarText(skill) }}
                  </span>
                </a-avatar>
                <div class="flex-1 min-w-0">
                  <div class="flex items-center gap-1.5 min-w-0">
                    <div class="text-sm font-bold text-gray-900 truncate">{{ skill.label }}</div>
                  </div>
                  <div class="text-[11px] text-gray-500 line-clamp-1">
                    {{ skill.source_key }}
                    <template v-if="skill.tool_count > 0">
                      · {{ t('store.skills.toolCount', { count: skill.tool_count }) }}
                    </template>
                  </div>
                </div>
              </div>

              <resource-card-description :text="skill.description" />

              <div class="flex items-center gap-1.5 flex-wrap mt-2.5">
                <a-tag size="small" color="gray">{{ getCategoryLabel(skill.category) }}</a-tag>
                <a-tag size="small" :color="skill.executor_type === 'scf' ? 'green' : 'gray'">
                  {{ getExecutorTypeLabel(skill.executor_type) }}
                </a-tag>
              </div>

              <div class="flex items-center gap-1.5 mt-2.5">
                <a-avatar :size="16" class="bg-blue-700">
                  <icon-file :size="10" />
                </a-avatar>
                <div class="text-[11px] text-gray-400">
                  <template v-if="skill.tool_count > 0">{{ t('store.skills.toolCount', { count: skill.tool_count }) }}</template>
                  <template v-else>{{ t('store.skills.promptOnly') }}</template>
                </div>
              </div>
            </a-card>
          </a-col>

          <a-col v-if="skills.length === 0" :span="24">
            <a-empty :description="t('store.skills.empty')" class="py-20" />
          </a-col>
        </a-row>
      </div>
    </div>

    <a-drawer
      :visible="showDetailVisible"
      :width="560"
      :footer="false"
      :title="t('store.skills.detailTitle')"
      :drawer-style="{ background: '#F9FAFB' }"
      @cancel="showDetailVisible = false"
    >
      <a-spin :loading="detailLoading" class="block h-full w-full">
        <div v-if="activeSkill" class="flex flex-col gap-4">
          <div class="flex items-start gap-3">
            <a-avatar
              :size="40"
              shape="square"
              class="overflow-hidden"
              :style="activeSkill.icon ? { backgroundColor: '#f3f4f6' } : getSkillAvatarStyle(activeSkill)"
            >
              <img
                v-if="activeSkill.icon"
                :src="normalizeIconUrl(activeSkill.icon)"
                :alt="activeSkill.label"
                class="w-full h-full object-cover"
              />
              <span v-else class="text-white font-semibold text-[12px] tracking-wide">
                {{ getSkillAvatarText(activeSkill) }}
              </span>
            </a-avatar>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 flex-wrap">
                <div class="text-sm font-bold text-gray-900">{{ activeSkill.label }}</div>
                <a-tag size="small" color="gray">{{ getCategoryLabel(activeSkill.category) }}</a-tag>
              </div>
              <div class="text-[11px] text-gray-500 mt-1">
                {{ activeSkill.source_key }}
                <template v-if="activeSkill.tool_count > 0"> · {{ t('store.skills.toolCount', { count: activeSkill.tool_count }) }}</template>
              </div>
            </div>
          </div>

          <div class="rounded-lg bg-white p-3.5">
            <div class="markdown-body skill-markdown" v-html="detailMarkdown" />
          </div>

          <div class="grid grid-cols-2 gap-3">
            <div class="rounded-lg bg-white p-3">
              <div class="text-xs text-gray-500 mb-1">{{ t('store.skills.executor') }}</div>
              <div class="text-sm text-gray-800">{{ getExecutorTypeLabel(activeSkill.executor_type) }}</div>
            </div>
            <div class="rounded-lg bg-white p-3">
              <div class="text-xs text-gray-500 mb-1">{{ t('store.skills.toolCountLabel') }}</div>
              <div class="text-sm text-gray-800">{{ activeSkill.tool_count }}</div>
            </div>
          </div>

          <div v-if="activeSkill.tools.length > 0">
            <div class="text-sm font-bold text-gray-700 mb-2">{{ t('store.skills.toolsTitle') }}</div>
            <div class="space-y-2">
              <a-card
                v-for="tool in activeSkill.tools"
                :key="tool.name"
                class="rounded-lg"
                :body-style="{ padding: '12px' }"
              >
                <div class="font-semibold text-gray-900">{{ tool.label }}</div>
                <div class="text-xs text-gray-500 mt-1">{{ tool.description }}</div>
              </a-card>
            </div>
          </div>
        </div>
      </a-spin>
    </a-drawer>
  </a-spin>
</template>

<style scoped>
.scrollbar-hide {
  scrollbar-width: none;
  -ms-overflow-style: none;
}

.scrollbar-hide::-webkit-scrollbar {
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
