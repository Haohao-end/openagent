<script setup lang="ts">
import { computed, nextTick, ref, watch, type PropType } from 'vue'
import { useUpdateDraftAppConfig } from '@/hooks/use-app'
import { useI18n } from 'vue-i18n'

// 1.定义自定义组件所需数据
const { t } = useI18n()
const props = defineProps({
  app_id: { type: String, default: '', required: true },
  opening_statement: { type: String, default: '', required: true },
  opening_questions: { type: Array as PropType<string[]>, default: () => [], required: true },
})
const emits = defineEmits(['update:opening_statement', 'update:opening_questions'])
const { handleUpdateDraftAppConfig } = useUpdateDraftAppConfig()
const openingStatement = ref(props.opening_statement)
watch(() => props.opening_statement, (value) => { openingStatement.value = value })
const computed_opening_questions = computed({
  get(): string[] {
    // 1.检测传递的opening_questions长度是否等于3，如果小于3并且最后一个元素不是空数据则新增一个
    const newValue = [...props.opening_questions]
    if (newValue.length < 3 && newValue[newValue.length - 1] !== '') {
      newValue.push('')
    }

    return newValue
  },
  set(newValue: string[]) {
    emits('update:opening_questions', newValue)
  },
})

// 2.定义提交开场建议问题列表处理器
const handleUpdateOpeningQuestions = async () => {
  await handleUpdateDraftAppConfig(props.app_id, {
    opening_questions: computed_opening_questions.value.filter((item) => item.trim() !== ''),
  })
}

const handleUpdateOpeningStatement = async () => {
  const statement = openingStatement.value
  try {
    await handleUpdateDraftAppConfig(props.app_id, { opening_statement: statement })
    emits('update:opening_statement', statement)
  } catch {
    openingStatement.value = props.opening_statement
  }
}
</script>

<template>
  <div class="">
    <a-collapse-item key="opening" class="app-ability-item">
      <template #header>
        <div class="text-gray-700 font-bold">{{ t('appStudio.abilities.opening.title') }}</div>
      </template>
      <div class="text-xs text-gray-500">
        <!-- 开场白文案 -->
        <div class="flex flex-col gap-2 mb-2">
          <div class="flex items-center gap-2">
            <div class="text-gray-700">{{ t('appStudio.abilities.opening.statementLabel') }}</div>
            <a-tooltip :content="t('appStudio.abilities.opening.statementTooltip')">
              <icon-exclamation-circle />
            </a-tooltip>
          </div>
          <a-textarea
            :model-value="openingStatement"
            @update:model-value="(value) => (openingStatement = String(value ?? ''))"
            :placeholder="t('appStudio.abilities.opening.statementPlaceholder')"
            class="bg-white text-gray-700 rounded-lg border border-gray-200"
            :auto-size="{ minRows: 4, maxRows: 4 }"
            @blur="handleUpdateOpeningStatement"
          />
        </div>
        <!-- 开场白建议问题 -->
        <div class="flex flex-col gap-2 mb-2">
          <div class="flex items-center gap-2">
            <div class="text-gray-700">{{ t('appStudio.abilities.opening.presetQuestionsLabel') }}</div>
            <a-tooltip :content="t('appStudio.abilities.opening.presetQuestionsTooltip')">
              <icon-exclamation-circle />
            </a-tooltip>
          </div>
          <!-- 预设问题列表 -->
          <div class="flex flex-col gap-2">
            <!-- 建议问题选项 -->
            <div
              v-for="(opening_question, idx) in computed_opening_questions"
              :key="idx"
              class="flex items-center gap-2"
            >
              <a-input
                :model-value="opening_question"
                @update:model-value="
                  (value: string | number) => {
                    const newQuestions = [...computed_opening_questions]
                    newQuestions[idx] = String(value ?? '')
                    computed_opening_questions = newQuestions
                  }
                "
                class="rounded-lg bg-white"
                :placeholder="t('appStudio.abilities.opening.questionPlaceholder')"
                @blur="async () => await handleUpdateOpeningQuestions()"
              />
              <a-button
                class="rounded-lg"
                @click="
                  async () => {
                    // 1.创建数组副本并清除指定项
                    const newQuestions = [...computed_opening_questions]
                    newQuestions.splice(idx, 1)
                    emits('update:opening_questions', newQuestions)

                    // 2.使用nextTick()方法确保数据更新
                    await nextTick()

                    // 3.提交草稿配置更新
                    await handleUpdateOpeningQuestions()
                  }
                "
              >
                <template #icon>
                  <icon-delete />
                </template>
              </a-button>
            </div>
          </div>
        </div>
      </div>
    </a-collapse-item>
  </div>
</template>
