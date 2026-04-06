<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useGetVersions } from '@/hooks/use-app'
import { formatTimestampLong } from '@/utils/time-formatter'
import VersionComparisonSectionContent from './components/VersionComparisonSectionContent.vue'

const route = useRoute()
const props = defineProps({
  app: {
    type: Object,
    default: () => ({}),
    required: true,
  },
})

const showOnlyChanged = ref(false)
const leftVersionId = ref('')
const rightVersionId = ref('')
const { loading, versions, loadVersions } = useGetVersions()

const normalizeValue = (value: unknown): unknown => {
  if (Array.isArray(value)) {
    return value.map((item) => normalizeValue(item))
  }

  if (value && typeof value === 'object') {
    return Object.keys(value as Record<string, unknown>)
      .sort()
      .reduce(
        (acc, key) => {
          acc[key] = normalizeValue((value as Record<string, unknown>)[key])
          return acc
        },
        {} as Record<string, unknown>,
      )
  }

  return value
}

const serializeValue = (value: unknown) => JSON.stringify(normalizeValue(value))

const leftVersion = computed(
  () => versions.value.find((version: any) => version.id === leftVersionId.value) || null,
)
const rightVersion = computed(
  () => versions.value.find((version: any) => version.id === rightVersionId.value) || null,
)

const createSection = (
  key: string,
  label: string,
  pickValue: (version: any) => unknown,
) => {
  const leftRaw = pickValue(leftVersion.value)
  const rightRaw = pickValue(rightVersion.value)

  return {
    key,
    label,
    changed: serializeValue(leftRaw) !== serializeValue(rightRaw),
    leftValue: leftRaw,
    rightValue: rightRaw,
  }
}

const comparisonSections = computed(() => [
  createSection('model_config', '模型配置', (version) => version?.config.model_config),
  createSection('dialog_round', '上下文轮数', (version) => version?.config.dialog_round),
  createSection('preset_prompt', '人设与回复逻辑', (version) => version?.config.preset_prompt),
  createSection('tools', '扩展插件', (version) => version?.config.tools),
  createSection('workflows', '工作流', (version) => version?.config.workflows),
  createSection('datasets', '知识库', (version) => version?.config.datasets),
  createSection('retrieval_config', '检索配置', (version) => version?.config.retrieval_config),
  createSection('opening', '对话开场白', (version) => ({
    opening_statement: version?.config.opening_statement || '',
    opening_questions: version?.config.opening_questions || [],
  })),
  createSection('experience', '交互体验', (version) => ({
    long_term_memory: version?.config.long_term_memory || {},
    speech_to_text: version?.config.speech_to_text || {},
    text_to_speech: version?.config.text_to_speech || {},
    suggested_after_answer: version?.config.suggested_after_answer || {},
  })),
  createSection('review_config', '审核配置', (version) => version?.config.review_config),
])

const visibleSections = computed(() => {
  if (!showOnlyChanged.value) {
    return comparisonSections.value
  }

  return comparisonSections.value.filter((section) => section.changed)
})

const changedSectionCount = computed(
  () => comparisonSections.value.filter((section) => section.changed).length,
)

const getVersionTagColor = (version: Record<string, any> | null) => {
  if (!version) {
    return 'gray'
  }

  if (version.config_type === 'draft') {
    return 'arcoblue'
  }

  return version.is_current_published ? 'green' : 'gray'
}

const getVersionTagLabel = (version: Record<string, any> | null) => {
  if (!version) {
    return '未选择版本'
  }

  if (version.config_type === 'draft') {
    return '草稿'
  }

  return version.is_current_published ? '当前线上版本' : '历史版本'
}

const getVersionCollectionCount = (
  version: Record<string, any> | null,
  key: 'tools' | 'workflows' | 'datasets',
) => {
  const value = version?.config?.[key]
  return Array.isArray(value) ? value.length : 0
}

const setDefaultSelectedVersions = () => {
  if (!versions.value.length) {
    leftVersionId.value = ''
    rightVersionId.value = ''
    return
  }

  leftVersionId.value = versions.value[0]?.id || ''

  const currentPublishedVersion = versions.value.find((version: any) => version.is_current_published)
  const fallbackRightVersion = versions.value.find((version: any) => version.id !== leftVersionId.value)
  rightVersionId.value =
    currentPublishedVersion?.id || fallbackRightVersion?.id || leftVersionId.value
}

const loadComparisonData = async () => {
  await loadVersions(String(route.params?.app_id))
  setDefaultSelectedVersions()
}

watch(
  () => route.params?.app_id,
  async (appId, previousAppId) => {
    if (!appId || appId === previousAppId) {
      return
    }
    await loadComparisonData()
  },
)

onMounted(async () => {
  await loadComparisonData()
})
</script>

<template>
  <div class="bg-gray-50 flex-1 w-full min-h-0 overflow-hidden">
    <a-spin :loading="loading" class="h-full min-h-0">
      <div
        data-testid="versions-scroll-container"
        class="h-full min-h-0 overflow-y-auto overflow-x-hidden scrollbar-w-none"
      >
        <div class="space-y-4 p-6">
          <div class="overflow-hidden rounded-[28px] border border-gray-100 bg-white shadow-sm">
            <div class="flex flex-wrap items-start justify-between gap-4 border-b border-gray-100 px-6 py-5">
              <div>
                <div class="text-lg font-semibold text-gray-800">版本对比</div>
                <div class="mt-1 text-sm text-gray-500">
                  对比草稿与历史发布版本的配置差异，快速确认本次改动范围。
                </div>
                <div v-if="props.app?.name" class="mt-2 text-sm text-gray-500">
                  当前应用：{{ props.app.name }}
                </div>
              </div>
              <div class="flex flex-wrap items-center gap-3 text-sm text-gray-500">
                <div>共 {{ versions.length }} 个可选版本</div>
                <div>差异区块 {{ changedSectionCount }}</div>
                <a-switch v-model:model-value="showOnlyChanged" size="small" />
                <div>仅看差异</div>
              </div>
            </div>

            <div class="grid gap-0 lg:grid-cols-2 lg:divide-x lg:divide-gray-100">
              <div class="min-w-0 p-6">
                <div class="mb-3 text-xs font-medium tracking-wide text-gray-400">对比版本 A</div>
                <a-select v-model:model-value="leftVersionId" placeholder="请选择版本">
                  <a-option v-for="version in versions" :key="version.id" :value="version.id">
                    {{ version.label }} · {{ version.summary }}
                  </a-option>
                </a-select>
                <div v-if="leftVersion" class="mt-4 space-y-3 text-sm text-gray-600">
                  <div class="flex flex-wrap items-center gap-2">
                    <a-tag bordered>{{ leftVersion.label }}</a-tag>
                    <a-tag :color="getVersionTagColor(leftVersion)" bordered>
                      {{ getVersionTagLabel(leftVersion) }}
                    </a-tag>
                  </div>
                  <div>更新时间：{{ formatTimestampLong(leftVersion.updated_at) }}</div>
                  <div class="text-gray-500">
                    扩展插件 {{ getVersionCollectionCount(leftVersion, 'tools') }} 个 · 工作流
                    {{ getVersionCollectionCount(leftVersion, 'workflows') }} 个 · 知识库
                    {{ getVersionCollectionCount(leftVersion, 'datasets') }} 个
                  </div>
                </div>
              </div>

              <div class="min-w-0 p-6">
                <div class="mb-3 text-xs font-medium tracking-wide text-gray-400">对比版本 B</div>
                <a-select v-model:model-value="rightVersionId" placeholder="请选择版本">
                  <a-option v-for="version in versions" :key="version.id" :value="version.id">
                    {{ version.label }} · {{ version.summary }}
                  </a-option>
                </a-select>
                <div v-if="rightVersion" class="mt-4 space-y-3 text-sm text-gray-600">
                  <div class="flex flex-wrap items-center gap-2">
                    <a-tag bordered>{{ rightVersion.label }}</a-tag>
                    <a-tag :color="getVersionTagColor(rightVersion)" bordered>
                      {{ getVersionTagLabel(rightVersion) }}
                    </a-tag>
                  </div>
                  <div>更新时间：{{ formatTimestampLong(rightVersion.updated_at) }}</div>
                  <div class="text-gray-500">
                    扩展插件 {{ getVersionCollectionCount(rightVersion, 'tools') }} 个 · 工作流
                    {{ getVersionCollectionCount(rightVersion, 'workflows') }} 个 · 知识库
                    {{ getVersionCollectionCount(rightVersion, 'datasets') }} 个
                  </div>
                </div>
              </div>
            </div>
          </div>

          <a-empty
            v-if="!versions.length"
            description="当前应用还没有可对比的版本数据"
            class="bg-white rounded-2xl border border-dashed border-gray-200 py-24"
          />

          <a-empty
            v-else-if="showOnlyChanged && visibleSections.length === 0"
            description="所选两个版本没有差异"
            class="bg-white rounded-2xl border border-dashed border-gray-200 py-24"
          />

          <div v-else class="space-y-4">
            <div
              v-for="section in visibleSections"
              :key="section.key"
              :data-testid="`comparison-section-${section.key}`"
              class="overflow-hidden rounded-[28px] border border-gray-100 bg-white shadow-sm"
            >
              <div
                class="flex items-center justify-between border-b border-gray-100 bg-gray-50/80 px-6 py-4"
              >
                <div class="text-sm font-semibold text-gray-800">{{ section.label }}</div>
                <a-tag :color="section.changed ? 'arcoblue' : 'green'" bordered>
                  {{ section.changed ? '已变更' : '无变化' }}
                </a-tag>
              </div>
              <div class="grid gap-0 lg:grid-cols-2 lg:divide-x lg:divide-gray-100">
                <div class="min-w-0 border-b border-gray-100 p-6 lg:border-b-0">
                  <div class="mb-4 flex flex-wrap items-center gap-2 text-sm text-gray-500">
                    <a-tag size="small" bordered>{{ leftVersion?.label || '未选择版本' }}</a-tag>
                    <a-tag size="small" :color="getVersionTagColor(leftVersion)" bordered>
                      {{ getVersionTagLabel(leftVersion) }}
                    </a-tag>
                  </div>
                  <version-comparison-section-content
                    :section-key="section.key"
                    :value="section.leftValue"
                    :compare-value="section.rightValue"
                    side="left"
                  />
                </div>
                <div class="min-w-0 p-6">
                  <div class="mb-4 flex flex-wrap items-center gap-2 text-sm text-gray-500">
                    <a-tag size="small" bordered>{{ rightVersion?.label || '未选择版本' }}</a-tag>
                    <a-tag size="small" :color="getVersionTagColor(rightVersion)" bordered>
                      {{ getVersionTagLabel(rightVersion) }}
                    </a-tag>
                  </div>
                  <version-comparison-section-content
                    :section-key="section.key"
                    :value="section.rightValue"
                    :compare-value="section.leftValue"
                    side="right"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </a-spin>
  </div>
</template>
