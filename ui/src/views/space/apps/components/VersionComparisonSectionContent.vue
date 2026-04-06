<script setup lang="ts">
import { computed } from 'vue'
import { apiPrefix } from '@/config'

const props = defineProps<{
  sectionKey: string
  value: unknown
  compareValue: unknown
  side: 'left' | 'right'
}>()

const parameterLabelMap: Record<string, string> = {
  temperature: '温度',
  top_p: 'Top P',
  max_tokens: '最大输出',
  frequency_penalty: '频率惩罚',
  presence_penalty: '存在惩罚',
}

const isPlainObject = (value: unknown): value is Record<string, any> => {
  return !!value && typeof value === 'object' && !Array.isArray(value)
}

const renderText = (value: unknown) => {
  if (value === null || value === undefined || value === '') {
    return '未设置'
  }

  if (typeof value === 'boolean') {
    return value ? '已启用' : '未启用'
  }

  return String(value)
}

const renderEnableLabel = (enabled: boolean) => {
  return enabled ? '已启用' : '未启用'
}

const renderEnableColor = (enabled: boolean) => {
  return enabled ? 'green' : 'gray'
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

const isDifferent = (value: unknown, compareValue: unknown) => {
  return serializeValue(value) !== serializeValue(compareValue)
}

const getChangedCardClass = (changed: boolean) => {
  return changed
    ? 'rounded-2xl border border-blue-200 bg-blue-50/70'
    : 'rounded-2xl border border-gray-200 bg-white'
}

const getItemStatusClass = (status: 'same' | 'added' | 'removed') => {
  if (status === 'added') {
    return 'rounded-2xl border border-green-200 bg-green-50/70'
  }

  if (status === 'removed') {
    return 'rounded-2xl border border-red-200 bg-red-50/70'
  }

  return 'rounded-2xl border border-gray-200 bg-white'
}

const getItemStatusLabel = (status: 'same' | 'added' | 'removed') => {
  if (status === 'added') {
    return '新增'
  }

  if (status === 'removed') {
    return '已移除'
  }

  return '保留'
}

const getItemStatusColor = (status: 'same' | 'added' | 'removed') => {
  if (status === 'added') {
    return 'green'
  }

  if (status === 'removed') {
    return 'red'
  }

  return 'gray'
}

const buildTextDiffSegments = (value: unknown, compareValue: unknown) => {
  const currentText = value === null || value === undefined ? '' : String(value)
  const targetText = compareValue === null || compareValue === undefined ? '' : String(compareValue)

  if (!currentText && !targetText) {
    return [{ text: '未设置', changed: false }]
  }

  if (currentText === targetText) {
    return [{ text: currentText || '未设置', changed: false }]
  }

  if (!currentText) {
    return [{ text: '未设置', changed: true }]
  }

  if (!targetText) {
    return [{ text: currentText, changed: true }]
  }

  let prefixLength = 0
  while (
    prefixLength < currentText.length &&
    prefixLength < targetText.length &&
    currentText[prefixLength] === targetText[prefixLength]
  ) {
    prefixLength += 1
  }

  let suffixLength = 0
  while (
    suffixLength < currentText.length - prefixLength &&
    suffixLength < targetText.length - prefixLength &&
    currentText[currentText.length - 1 - suffixLength] === targetText[targetText.length - 1 - suffixLength]
  ) {
    suffixLength += 1
  }

  const prefix = currentText.slice(0, prefixLength)
  const middle = currentText.slice(prefixLength, currentText.length - suffixLength)
  const suffix = currentText.slice(currentText.length - suffixLength)
  const segments = []

  if (prefix) {
    segments.push({ text: prefix, changed: false })
  }

  if (middle) {
    segments.push({ text: middle, changed: true })
  }

  if (suffix) {
    segments.push({ text: suffix, changed: false })
  }

  return segments.length ? segments : [{ text: currentText, changed: true }]
}

const listValue = computed<any[]>(() => (Array.isArray(props.value) ? props.value : []))
const compareListValue = computed<any[]>(() => (Array.isArray(props.compareValue) ? props.compareValue : []))
const objectValue = computed<Record<string, any>>(() =>
  isPlainObject(props.value) ? props.value : {},
)
const compareObjectValue = computed<Record<string, any>>(() =>
  isPlainObject(props.compareValue) ? props.compareValue : {},
)

const modelProvider = computed(() => renderText(objectValue.value.provider))
const modelName = computed(() => renderText(objectValue.value.model))
const modelProviderChanged = computed(() =>
  isDifferent(objectValue.value.provider, compareObjectValue.value.provider),
)
const modelNameChanged = computed(() => isDifferent(objectValue.value.model, compareObjectValue.value.model))
const parameterEntries = computed(() => {
  const parameters = isPlainObject(objectValue.value.parameters) ? objectValue.value.parameters : {}
  const compareParameters = isPlainObject(compareObjectValue.value.parameters)
    ? compareObjectValue.value.parameters
    : {}
  const allKeys = Array.from(new Set([...Object.keys(parameters), ...Object.keys(compareParameters)]))
  const orderedKeys = [
    ...Object.keys(parameterLabelMap).filter((key) => allKeys.includes(key)),
    ...allKeys.filter((key) => !(key in parameterLabelMap)).sort(),
  ]

  return orderedKeys.map((key) => ({
    key,
    label: parameterLabelMap[key] || key,
    value: renderText(parameters[key]),
    changed: isDifferent(parameters[key], compareParameters[key]),
  }))
})

const promptText = computed(() => renderText(props.value))
const dialogRoundValue = computed(() => renderText(props.value))
const dialogRoundChanged = computed(() => isDifferent(props.value, props.compareValue))
const promptSegments = computed(() => buildTextDiffSegments(props.value, props.compareValue))
const openingStatement = computed(() => renderText(objectValue.value.opening_statement))
const openingQuestions = computed(() =>
  Array.isArray(objectValue.value.opening_questions) ? objectValue.value.opening_questions : [],
)
const compareOpeningQuestions = computed(() =>
  Array.isArray(compareObjectValue.value.opening_questions) ? compareObjectValue.value.opening_questions : [],
)
const openingStatementSegments = computed(() =>
  buildTextDiffSegments(objectValue.value.opening_statement, compareObjectValue.value.opening_statement),
)

const retrievalItems = computed(() => [
  {
    key: 'retrieval_strategy',
    label: '检索策略',
    value:
      objectValue.value.retrieval_strategy === 'full_text'
        ? '全文检索'
        : objectValue.value.retrieval_strategy === 'hybrid_search'
          ? '混合检索'
          : '相似性检索',
    changed: isDifferent(
      objectValue.value.retrieval_strategy,
      compareObjectValue.value.retrieval_strategy,
    ),
  },
  {
    key: 'k',
    label: '召回数量',
    value: renderText(objectValue.value.k),
    changed: isDifferent(objectValue.value.k, compareObjectValue.value.k),
  },
  {
    key: 'score',
    label: '相似度阈值',
    value: renderText(objectValue.value.score),
    changed: isDifferent(objectValue.value.score, compareObjectValue.value.score),
  },
])

const experienceItems = computed(() => {
  const longTermMemoryEnabled = !!objectValue.value.long_term_memory?.enable
  const speechToTextEnabled = !!objectValue.value.speech_to_text?.enable
  const textToSpeechEnabled = !!objectValue.value.text_to_speech?.enable
  const suggestedAfterAnswerEnabled = !!objectValue.value.suggested_after_answer?.enable

  return [
    {
      key: 'long_term_memory',
      label: '长期记忆',
      enabled: longTermMemoryEnabled,
      detail: longTermMemoryEnabled ? '会在对话中召回历史记忆。' : '不会召回长期记忆。',
      changed: isDifferent(
        objectValue.value.long_term_memory,
        compareObjectValue.value.long_term_memory,
      ),
    },
    {
      key: 'speech_to_text',
      label: '语音输入',
      enabled: speechToTextEnabled,
      detail: speechToTextEnabled ? '支持语音转文本输入。' : '不支持语音输入。',
      changed: isDifferent(
        objectValue.value.speech_to_text,
        compareObjectValue.value.speech_to_text,
      ),
    },
    {
      key: 'text_to_speech',
      label: '语音输出',
      enabled: textToSpeechEnabled,
      detail: textToSpeechEnabled
        ? `音色 ${renderText(objectValue.value.text_to_speech?.voice)} · ${objectValue.value.text_to_speech?.auto_play ? '自动播放' : '手动播放'}`
        : '不支持语音播报。',
      changed: isDifferent(
        objectValue.value.text_to_speech,
        compareObjectValue.value.text_to_speech,
      ),
    },
    {
      key: 'suggested_after_answer',
      label: '回答后建议问题',
      enabled: suggestedAfterAnswerEnabled,
      detail: suggestedAfterAnswerEnabled ? '回答后会生成推荐追问。' : '回答后不生成推荐追问。',
      changed: isDifferent(
        objectValue.value.suggested_after_answer,
        compareObjectValue.value.suggested_after_answer,
      ),
    },
  ]
})

const reviewKeywords = computed(() =>
  Array.isArray(objectValue.value.keywords) ? objectValue.value.keywords : [],
)
const compareReviewKeywords = computed(() =>
  Array.isArray(compareObjectValue.value.keywords) ? compareObjectValue.value.keywords : [],
)

const reviewConfigEnabled = computed(() => !!objectValue.value.enable)
const inputReviewEnabled = computed(() => !!objectValue.value.inputs_config?.enable)
const outputReviewEnabled = computed(() => !!objectValue.value.outputs_config?.enable)
const reviewConfigChanged = computed(() => isDifferent(objectValue.value.enable, compareObjectValue.value.enable))
const inputReviewChanged = computed(() =>
  isDifferent(objectValue.value.inputs_config, compareObjectValue.value.inputs_config),
)
const outputReviewChanged = computed(() =>
  isDifferent(objectValue.value.outputs_config, compareObjectValue.value.outputs_config),
)

const getListItemIdentifier = (item: Record<string, any>) => {
  if (props.sectionKey === 'tools') {
    return [
      item.type || '',
      item.provider?.id || item.provider_id || '',
      item.tool?.id || item.tool?.name || item.tool_id || '',
    ].join(':')
  }

  return item.id || item.name || JSON.stringify(item)
}

const getListItemStatus = (item: Record<string, any>) => {
  const compareIds = new Set(compareListValue.value.map((compareItem) => getListItemIdentifier(compareItem)))
  const existsInCompare = compareIds.has(getListItemIdentifier(item))

  if (existsInCompare) {
    return 'same' as const
  }

  return props.side === 'right' ? ('added' as const) : ('removed' as const)
}

const getTextListItemStatus = (item: string, compareItems: string[]) => {
  if (compareItems.includes(item)) {
    return 'same' as const
  }

  return props.side === 'right' ? ('added' as const) : ('removed' as const)
}

const getListItemName = (item: Record<string, any>, fallback: string) => {
  if (props.sectionKey === 'tools') {
    const providerLabel =
      item.provider?.label || item.provider?.name || item.provider_id || '未知提供方'
    const toolLabel = item.tool?.label || item.tool?.name || item.tool_id || fallback
    return `${providerLabel} / ${toolLabel}`
  }

  return item.name || fallback
}

const getListItemDescription = (item: Record<string, any>) => {
  if (props.sectionKey === 'tools') {
    return item.tool?.description || item.provider?.description || '暂无插件说明'
  }

  return item.description || '暂无说明'
}

const getListItemIcon = (item: Record<string, any>) => {
  if (props.sectionKey === 'tools') {
    return normalizeIconUrl(item.provider?.icon || '')
  }

  if (props.sectionKey === 'workflows') {
    return item.icon || ''
  }

  return item.icon || ''
}
</script>

<template>
  <div :data-testid="`section-content-${sectionKey}`" class="space-y-4">
    <template v-if="sectionKey === 'model_config'">
      <div class="rounded-2xl border border-gray-200 bg-gray-50 p-4">
        <div class="flex flex-wrap items-center gap-2">
          <div :class="modelNameChanged ? 'rounded-lg bg-blue-100/80 px-1.5 py-1' : ''">
            <a-tag color="arcoblue" size="small">模型 {{ modelName }}</a-tag>
          </div>
          <div :class="modelProviderChanged ? 'rounded-lg bg-blue-100/80 px-1.5 py-1' : ''">
            <a-tag bordered size="small">提供方 {{ modelProvider }}</a-tag>
          </div>
        </div>
        <div v-if="parameterEntries.length" class="mt-4 grid gap-3 sm:grid-cols-2">
          <div
            v-for="entry in parameterEntries"
            :key="entry.key"
            :data-testid="`field-diff-${sectionKey}-${entry.key}`"
            :class="entry.changed ? 'rounded-xl border border-blue-200 bg-blue-50/80 p-3' : 'rounded-xl border border-white bg-white p-3'"
          >
            <div class="flex items-center justify-between gap-2">
              <div class="text-xs text-gray-500">{{ entry.label }}</div>
              <a-tag v-if="entry.changed" color="arcoblue" size="small">已修改</a-tag>
            </div>
            <div class="mt-1 text-sm font-medium text-gray-700">{{ entry.value }}</div>
          </div>
        </div>
        <div v-else class="mt-4 text-sm text-gray-400">未配置模型参数</div>
      </div>
    </template>

    <template v-else-if="sectionKey === 'dialog_round'">
      <div :class="getChangedCardClass(dialogRoundChanged)">
        <div class="text-xs text-gray-500">上下文保留策略</div>
        <div class="mt-2 flex flex-wrap items-center gap-2">
          <a-tag color="arcoblue" size="small">对话轮次 {{ dialogRoundValue }}</a-tag>
          <a-tag v-if="dialogRoundChanged" color="arcoblue" size="small">已修改</a-tag>
          <span class="text-sm text-gray-500">用于控制对话时保留的历史消息轮数。</span>
        </div>
      </div>
    </template>

    <template v-else-if="sectionKey === 'preset_prompt'">
      <div :class="getChangedCardClass(isDifferent(value, compareValue))">
        <div class="border-b border-gray-100 px-4 py-3 text-sm font-medium text-gray-700">
          <div class="flex items-center justify-between gap-2">
            <span>人设与回复逻辑</span>
            <a-tag v-if="isDifferent(value, compareValue)" color="arcoblue" size="small">已修改</a-tag>
          </div>
        </div>
        <div class="bg-gray-50 px-4 py-4">
          <div class="whitespace-pre-wrap break-words rounded-xl border border-gray-200 bg-white p-4 text-sm leading-6 text-gray-700">
            <template v-for="(segment, index) in promptSegments" :key="`${sectionKey}-prompt-${index}`">
              <span :class="segment.changed ? 'rounded bg-blue-100/90 px-0.5 text-gray-900' : ''">
                {{ segment.text }}
              </span>
            </template>
          </div>
        </div>
      </div>
    </template>

    <template v-else-if="['tools', 'workflows', 'datasets'].includes(sectionKey)">
      <div v-if="listValue.length" class="space-y-3">
        <div
          v-for="(item, index) in listValue"
          :key="item.id || item.tool?.id || `${sectionKey}-${index}`"
          :data-testid="`field-diff-${sectionKey}-item-${index}`"
          :class="`${getItemStatusClass(getListItemStatus(item))} flex items-center justify-between p-4`"
        >
          <div class="flex min-w-0 items-center gap-3">
            <a-avatar
              :size="36"
              shape="square"
              class="rounded-lg flex-shrink-0"
              :image-url="getListItemIcon(item)"
            >
              <icon-apps v-if="sectionKey !== 'datasets'" />
              <icon-storage v-else />
            </a-avatar>
            <div class="min-w-0">
              <div class="line-clamp-1 text-sm font-bold text-gray-700">
                {{ getListItemName(item, `未命名${sectionKey === 'tools' ? '插件' : sectionKey === 'workflows' ? '工作流' : '知识库'}`) }}
              </div>
              <div class="mt-1 line-clamp-1 text-xs text-gray-500">
                {{ getListItemDescription(item) }}
              </div>
            </div>
          </div>
          <a-tag :color="getItemStatusColor(getListItemStatus(item))" size="small" bordered>
            {{ getItemStatusLabel(getListItemStatus(item)) }}
          </a-tag>
        </div>
      </div>
      <div
        v-else
        class="rounded-2xl border border-dashed border-gray-200 bg-gray-50 px-4 py-6 text-sm text-gray-400"
      >
        {{
          sectionKey === 'tools'
            ? '未配置扩展插件'
            : sectionKey === 'workflows'
              ? '未配置工作流'
              : '未配置知识库'
        }}
      </div>
    </template>

    <template v-else-if="sectionKey === 'retrieval_config'">
      <div class="grid gap-3 sm:grid-cols-3">
        <div
          v-for="item in retrievalItems"
          :key="item.key"
          :data-testid="`field-diff-${sectionKey}-${item.key}`"
          :class="item.changed ? 'rounded-2xl border border-blue-200 bg-blue-50/80 p-4' : 'rounded-2xl border border-gray-200 bg-white p-4'"
        >
          <div class="flex items-center justify-between gap-2">
            <div class="text-xs text-gray-500">{{ item.label }}</div>
            <a-tag v-if="item.changed" color="arcoblue" size="small">已修改</a-tag>
          </div>
          <div class="mt-1 text-sm font-medium text-gray-700">{{ item.value }}</div>
        </div>
      </div>
    </template>

    <template v-else-if="sectionKey === 'opening'">
      <div class="space-y-3">
        <div
          :data-testid="`field-diff-${sectionKey}-statement`"
          :class="getChangedCardClass(isDifferent(objectValue.opening_statement, compareObjectValue.opening_statement))"
        >
          <div class="flex items-center justify-between gap-2">
            <div class="text-xs text-gray-500">开场白</div>
            <a-tag
              v-if="isDifferent(objectValue.opening_statement, compareObjectValue.opening_statement)"
              color="arcoblue"
              size="small"
            >
              已修改
            </a-tag>
          </div>
          <div class="mt-2 whitespace-pre-wrap break-words text-sm leading-6 text-gray-700">
            <template
              v-for="(segment, index) in openingStatementSegments"
              :key="`${sectionKey}-statement-${index}`"
            >
              <span :class="segment.changed ? 'rounded bg-blue-100/90 px-0.5 text-gray-900' : ''">
                {{ segment.text }}
              </span>
            </template>
          </div>
        </div>
        <div class="rounded-2xl border border-gray-200 bg-white p-4">
          <div class="text-xs text-gray-500">开场问题</div>
          <div v-if="openingQuestions.length" class="mt-3 space-y-2">
            <div
              v-for="question in openingQuestions"
              :key="question"
              :class="`${getItemStatusClass(getTextListItemStatus(question, compareOpeningQuestions))} px-3 py-2 text-sm text-gray-700`"
            >
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0 flex-1 break-words">{{ question }}</div>
                <a-tag
                  :color="getItemStatusColor(getTextListItemStatus(question, compareOpeningQuestions))"
                  size="small"
                  bordered
                >
                  {{ getItemStatusLabel(getTextListItemStatus(question, compareOpeningQuestions)) }}
                </a-tag>
              </div>
            </div>
          </div>
          <div v-else class="mt-2 text-sm text-gray-400">未配置开场问题</div>
        </div>
      </div>
    </template>

    <template v-else-if="sectionKey === 'experience'">
      <div class="grid gap-3 sm:grid-cols-2">
        <div
          v-for="item in experienceItems"
          :key="item.key"
          :data-testid="`field-diff-${sectionKey}-${item.key}`"
          :class="item.changed ? 'rounded-2xl border border-blue-200 bg-blue-50/80 p-4' : 'rounded-2xl border border-gray-200 bg-white p-4'"
        >
          <div class="flex items-center justify-between gap-3">
            <div class="text-sm font-medium text-gray-700">{{ item.label }}</div>
            <div class="flex items-center gap-2">
              <a-tag :color="renderEnableColor(item.enabled)" size="small">
                {{ renderEnableLabel(item.enabled) }}
              </a-tag>
              <a-tag v-if="item.changed" color="arcoblue" size="small">已修改</a-tag>
            </div>
          </div>
          <div class="mt-2 text-xs leading-5 text-gray-500">{{ item.detail }}</div>
        </div>
      </div>
    </template>

    <template v-else-if="sectionKey === 'review_config'">
      <div class="space-y-3">
        <div :class="getChangedCardClass(reviewConfigChanged)">
          <div class="flex items-center justify-between gap-3">
            <div class="text-sm font-medium text-gray-700">内容审核</div>
            <div class="flex items-center gap-2">
              <a-tag :color="renderEnableColor(reviewConfigEnabled)" size="small">
                {{ renderEnableLabel(reviewConfigEnabled) }}
              </a-tag>
              <a-tag v-if="reviewConfigChanged" color="arcoblue" size="small">已修改</a-tag>
            </div>
          </div>
          <div class="mt-3 grid gap-3 sm:grid-cols-2">
            <div :class="inputReviewChanged ? 'rounded-xl border border-blue-200 bg-blue-50/70 p-3' : 'rounded-xl border border-gray-200 bg-gray-50 p-3'">
              <div class="flex items-center justify-between gap-2">
                <div class="text-xs text-gray-500">输入审核</div>
                <a-tag v-if="inputReviewChanged" color="arcoblue" size="small">已修改</a-tag>
              </div>
              <div class="mt-1 text-sm font-medium text-gray-700">
                {{ renderEnableLabel(inputReviewEnabled) }}
              </div>
              <div class="mt-1 text-xs text-gray-500">
                违规回复：{{ renderText(objectValue.inputs_config?.preset_response) }}
              </div>
            </div>
            <div :class="outputReviewChanged ? 'rounded-xl border border-blue-200 bg-blue-50/70 p-3' : 'rounded-xl border border-gray-200 bg-gray-50 p-3'">
              <div class="flex items-center justify-between gap-2">
                <div class="text-xs text-gray-500">输出审核</div>
                <a-tag v-if="outputReviewChanged" color="arcoblue" size="small">已修改</a-tag>
              </div>
              <div class="mt-1 text-sm font-medium text-gray-700">
                {{ renderEnableLabel(outputReviewEnabled) }}
              </div>
            </div>
          </div>
        </div>
        <div :class="getChangedCardClass(isDifferent(reviewKeywords, compareReviewKeywords))">
          <div class="text-xs text-gray-500">敏感关键词</div>
          <div v-if="reviewKeywords.length" class="mt-3 flex flex-wrap gap-2">
            <a-tag
              v-for="keyword in reviewKeywords"
              :key="keyword"
              :color="getItemStatusColor(getTextListItemStatus(keyword, compareReviewKeywords))"
              bordered
              size="small"
            >
              {{ keyword }} · {{ getItemStatusLabel(getTextListItemStatus(keyword, compareReviewKeywords)) }}
            </a-tag>
          </div>
          <div v-else class="mt-2 text-sm text-gray-400">未配置敏感关键词</div>
        </div>
      </div>
    </template>

    <template v-else>
      <div class="rounded-xl border border-dashed border-gray-200 bg-gray-50 px-4 py-6 text-sm text-gray-400">
        当前区块暂不支持可视化展示
      </div>
    </template>
  </div>
</template>
