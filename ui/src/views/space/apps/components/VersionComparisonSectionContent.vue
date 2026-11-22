<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { apiPrefix } from '@/config'
import { getModelParameterDisplayLabel } from '@/utils/model-parameter-display'

const props = defineProps<{
  sectionKey: string
  value: unknown
  compareValue: unknown
  side: 'left' | 'right'
}>()
const { t } = useI18n()

const isPlainObject = (value: unknown): value is Record<string, any> => {
  return !!value && typeof value === 'object' && !Array.isArray(value)
}

const renderText = (value: unknown) => {
  if (value === null || value === undefined || value === '') {
    return t('appStudio.versions.sectionContent.unset')
  }

  if (typeof value === 'boolean') {
    return value
      ? t('appStudio.versions.sectionContent.enabled')
      : t('appStudio.versions.sectionContent.disabled')
  }

  return String(value)
}

const renderEnableLabel = (enabled: boolean) => {
  return enabled
    ? t('appStudio.versions.sectionContent.enabled')
    : t('appStudio.versions.sectionContent.disabled')
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
    return t('appStudio.versions.sectionContent.added')
  }

  if (status === 'removed') {
    return t('appStudio.versions.sectionContent.removed')
  }

  return t('appStudio.versions.sectionContent.retained')
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
    return [{ text: t('appStudio.versions.sectionContent.unset'), changed: false }]
  }

  if (currentText === targetText) {
    return [{ text: currentText || t('appStudio.versions.sectionContent.unset'), changed: false }]
  }

  if (!currentText) {
    return [{ text: t('appStudio.versions.sectionContent.unset'), changed: true }]
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
    ...['temperature', 'top_p', 'max_tokens', 'frequency_penalty', 'presence_penalty'].filter((key) => allKeys.includes(key)),
    ...allKeys.filter((key) => !['temperature', 'top_p', 'max_tokens', 'frequency_penalty', 'presence_penalty'].includes(key)).sort(),
  ]

  return orderedKeys.map((key) => ({
    key,
    label: getModelParameterDisplayLabel(key, key, t),
    value: renderText(parameters[key]),
    changed: isDifferent(parameters[key], compareParameters[key]),
  }))
})

const dialogRoundValue = computed(() => renderText(props.value))
const dialogRoundChanged = computed(() => isDifferent(props.value, props.compareValue))
const promptSegments = computed(() => buildTextDiffSegments(props.value, props.compareValue))
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
    label: t('appStudio.versions.sectionContent.retrievalStrategy'),
    value:
      objectValue.value.retrieval_strategy === 'full_text'
        ? t('appStudio.versions.sectionContent.retrievalStrategies.fullText')
        : objectValue.value.retrieval_strategy === 'hybrid_search'
          ? t('appStudio.versions.sectionContent.retrievalStrategies.hybrid')
          : t('appStudio.versions.sectionContent.retrievalStrategies.semantic'),
    changed: isDifferent(
      objectValue.value.retrieval_strategy,
      compareObjectValue.value.retrieval_strategy,
    ),
  },
  {
    key: 'k',
    label: t('appStudio.versions.sectionContent.recallCount'),
    value: renderText(objectValue.value.k),
    changed: isDifferent(objectValue.value.k, compareObjectValue.value.k),
  },
  {
    key: 'score',
    label: t('appStudio.versions.sectionContent.similarityThreshold'),
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
      label: t('appStudio.versions.sectionContent.longTermMemory'),
      enabled: longTermMemoryEnabled,
      detail: longTermMemoryEnabled
        ? t('appStudio.versions.sectionContent.longTermMemoryEnabled')
        : t('appStudio.versions.sectionContent.longTermMemoryDisabled'),
      changed: isDifferent(
        objectValue.value.long_term_memory,
        compareObjectValue.value.long_term_memory,
      ),
    },
    {
      key: 'speech_to_text',
      label: t('appStudio.versions.sectionContent.speechToText'),
      enabled: speechToTextEnabled,
      detail: speechToTextEnabled
        ? t('appStudio.versions.sectionContent.speechToTextEnabled')
        : t('appStudio.versions.sectionContent.speechToTextDisabled'),
      changed: isDifferent(
        objectValue.value.speech_to_text,
        compareObjectValue.value.speech_to_text,
      ),
    },
    {
      key: 'text_to_speech',
      label: t('appStudio.versions.sectionContent.textToSpeech'),
      enabled: textToSpeechEnabled,
      detail: textToSpeechEnabled
        ? t('appStudio.versions.sectionContent.textToSpeechEnabled', {
            voice: renderText(objectValue.value.text_to_speech?.voice),
            mode: objectValue.value.text_to_speech?.auto_play
              ? t('appStudio.versions.sectionContent.autoPlay')
              : t('appStudio.versions.sectionContent.manualPlay'),
          })
        : t('appStudio.versions.sectionContent.textToSpeechDisabled'),
      changed: isDifferent(
        objectValue.value.text_to_speech,
        compareObjectValue.value.text_to_speech,
      ),
    },
    {
      key: 'suggested_after_answer',
      label: t('appStudio.versions.sectionContent.suggestedAfterAnswer'),
      enabled: suggestedAfterAnswerEnabled,
      detail: suggestedAfterAnswerEnabled
        ? t('appStudio.versions.sectionContent.suggestedAfterAnswerEnabled')
        : t('appStudio.versions.sectionContent.suggestedAfterAnswerDisabled'),
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
      item.provider?.label
      || item.provider?.name
      || item.provider_id
      || t('appStudio.versions.sectionContent.unknownProvider')
    const toolLabel = item.tool?.label || item.tool?.name || item.tool_id || fallback
    return `${providerLabel} / ${toolLabel}`
  }

  return item.name || fallback
}

const getListItemDescription = (item: Record<string, any>) => {
  if (props.sectionKey === 'tools') {
    return item.tool?.description || item.provider?.description || t('appStudio.versions.sectionContent.noToolDescription')
  }

  return item.description || t('appStudio.versions.sectionContent.noDescription')
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
            <a-tag color="arcoblue" size="small">{{ t('appStudio.versions.sectionContent.model', { name: modelName }) }}</a-tag>
          </div>
          <div :class="modelProviderChanged ? 'rounded-lg bg-blue-100/80 px-1.5 py-1' : ''">
            <a-tag bordered size="small">{{ t('appStudio.versions.sectionContent.provider', { name: modelProvider }) }}</a-tag>
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
              <a-tag v-if="entry.changed" color="arcoblue" size="small">{{ t('appStudio.versions.sectionContent.modified') }}</a-tag>
            </div>
            <div class="mt-1 text-sm font-medium text-gray-700">{{ entry.value }}</div>
          </div>
        </div>
        <div v-else class="mt-4 text-sm text-gray-400">{{ t('appStudio.versions.sectionContent.noModelParameters') }}</div>
      </div>
    </template>

    <template v-else-if="sectionKey === 'dialog_round'">
      <div :class="getChangedCardClass(dialogRoundChanged)">
        <div class="text-xs text-gray-500">{{ t('appStudio.versions.sectionContent.contextRetention') }}</div>
        <div class="mt-2 flex flex-wrap items-center gap-2">
          <a-tag color="arcoblue" size="small">{{ t('appStudio.versions.sectionContent.dialogRounds', { count: dialogRoundValue }) }}</a-tag>
          <a-tag v-if="dialogRoundChanged" color="arcoblue" size="small">{{ t('appStudio.versions.sectionContent.modified') }}</a-tag>
          <span class="text-sm text-gray-500">{{ t('appStudio.versions.sectionContent.dialogRoundsHint') }}</span>
        </div>
      </div>
    </template>

    <template v-else-if="sectionKey === 'preset_prompt'">
      <div :class="getChangedCardClass(isDifferent(value, compareValue))">
        <div class="border-b border-gray-100 px-4 py-3 text-sm font-medium text-gray-700">
          <div class="flex items-center justify-between gap-2">
            <span>{{ t('appStudio.versions.sectionContent.presetPromptTitle') }}</span>
            <a-tag v-if="isDifferent(value, compareValue)" color="arcoblue" size="small">{{ t('appStudio.versions.sectionContent.modified') }}</a-tag>
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
                {{
                  getListItemName(
                    item,
                    sectionKey === 'tools'
                      ? t('appStudio.versions.sectionContent.unnamedTool')
                      : sectionKey === 'workflows'
                        ? t('appStudio.versions.sectionContent.unnamedWorkflow')
                        : t('appStudio.versions.sectionContent.unnamedDataset'),
                  )
                }}
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
            ? t('appStudio.versions.sectionContent.noTools')
            : sectionKey === 'workflows'
              ? t('appStudio.versions.sectionContent.noWorkflows')
              : t('appStudio.versions.sectionContent.noDatasets')
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
            <a-tag v-if="item.changed" color="arcoblue" size="small">{{ t('appStudio.versions.sectionContent.modified') }}</a-tag>
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
            <div class="text-xs text-gray-500">{{ t('appStudio.versions.sectionContent.openingStatement') }}</div>
            <a-tag
              v-if="isDifferent(objectValue.opening_statement, compareObjectValue.opening_statement)"
              color="arcoblue"
              size="small"
            >
              {{ t('appStudio.versions.sectionContent.modified') }}
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
          <div class="text-xs text-gray-500">{{ t('appStudio.versions.sectionContent.openingQuestions') }}</div>
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
          <div v-else class="mt-2 text-sm text-gray-400">{{ t('appStudio.versions.sectionContent.noOpeningQuestions') }}</div>
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
              <a-tag v-if="item.changed" color="arcoblue" size="small">{{ t('appStudio.versions.sectionContent.modified') }}</a-tag>
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
            <div class="text-sm font-medium text-gray-700">{{ t('appStudio.versions.sectionContent.reviewConfig') }}</div>
            <div class="flex items-center gap-2">
              <a-tag :color="renderEnableColor(reviewConfigEnabled)" size="small">
                {{ renderEnableLabel(reviewConfigEnabled) }}
              </a-tag>
              <a-tag v-if="reviewConfigChanged" color="arcoblue" size="small">{{ t('appStudio.versions.sectionContent.modified') }}</a-tag>
            </div>
          </div>
          <div class="mt-3 grid gap-3 sm:grid-cols-2">
            <div :class="inputReviewChanged ? 'rounded-xl border border-blue-200 bg-blue-50/70 p-3' : 'rounded-xl border border-gray-200 bg-gray-50 p-3'">
              <div class="flex items-center justify-between gap-2">
                <div class="text-xs text-gray-500">{{ t('appStudio.versions.sectionContent.inputReview') }}</div>
                <a-tag v-if="inputReviewChanged" color="arcoblue" size="small">{{ t('appStudio.versions.sectionContent.modified') }}</a-tag>
              </div>
              <div class="mt-1 text-sm font-medium text-gray-700">
                {{ renderEnableLabel(inputReviewEnabled) }}
              </div>
              <div class="mt-1 text-xs text-gray-500">
                {{ t('appStudio.versions.sectionContent.violationReply', { value: renderText(objectValue.inputs_config?.preset_response) }) }}
              </div>
            </div>
            <div :class="outputReviewChanged ? 'rounded-xl border border-blue-200 bg-blue-50/70 p-3' : 'rounded-xl border border-gray-200 bg-gray-50 p-3'">
              <div class="flex items-center justify-between gap-2">
                <div class="text-xs text-gray-500">{{ t('appStudio.versions.sectionContent.outputReview') }}</div>
                <a-tag v-if="outputReviewChanged" color="arcoblue" size="small">{{ t('appStudio.versions.sectionContent.modified') }}</a-tag>
              </div>
              <div class="mt-1 text-sm font-medium text-gray-700">
                {{ renderEnableLabel(outputReviewEnabled) }}
              </div>
            </div>
          </div>
        </div>
        <div :class="getChangedCardClass(isDifferent(reviewKeywords, compareReviewKeywords))">
          <div class="text-xs text-gray-500">{{ t('appStudio.versions.sectionContent.sensitiveKeywords') }}</div>
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
          <div v-else class="mt-2 text-sm text-gray-400">{{ t('appStudio.versions.sectionContent.noSensitiveKeywords') }}</div>
        </div>
      </div>
    </template>

    <template v-else>
      <div class="rounded-xl border border-dashed border-gray-200 bg-gray-50 px-4 py-6 text-sm text-gray-400">
        {{ t('appStudio.versions.sectionContent.unsupportedSection') }}
      </div>
    </template>
  </div>
</template>
