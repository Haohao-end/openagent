<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useReplayMessage } from '@/hooks/use-conversation'
import type { ReplaySnapshotData } from '@/models/conversation'

const emit = defineEmits<{
  (e: 'replayed', data: ReplaySnapshotData): void
}>()

const { t } = useI18n()
const visible = ref(false)
const currentMessageId = ref('')
const query = ref('')
const presetPromptPatch = ref('')

const { loading, snapshot, executeReplay, clearReplay } = useReplayMessage()

const open = (message_id: string, initialQuery: string = '') => {
  currentMessageId.value = message_id
  query.value = initialQuery
  presetPromptPatch.value = ''
  visible.value = true
}

const close = () => {
  visible.value = false
  clearReplay()
}

const handleReplay = async () => {
  if (!currentMessageId.value) return
  const patch: Record<string, any> = {}
  if (presetPromptPatch.value.trim()) {
    patch.preset_prompt = presetPromptPatch.value.trim()
  }

  const result = await executeReplay(currentMessageId.value, { patch })
  if (result) {
    emit('replayed', result)
  }
}

defineExpose({ open, handleReplay })
</script>

<template>
  <a-modal
    v-model:visible="visible"
    :title="t('chat.replayMessage.title')"
    :footer="false"
    width="640px"
    @cancel="close"
  >
    <a-spin :loading="loading" class="w-full">
      <div class="flex flex-col gap-4">
        <!-- Input Query (Read-only snapshot display if provided) -->
        <div v-if="query || snapshot?.input_snapshot?.query" class="flex flex-col gap-1">
          <label class="text-xs font-semibold text-gray-600">{{ t('chat.replayMessage.query') }}</label>
          <div class="text-xs p-2.5 bg-gray-50 border rounded text-gray-800">
            {{ snapshot?.input_snapshot?.query || query }}
          </div>
        </div>

        <!-- Preset Prompt Patch Input -->
        <div class="flex flex-col gap-1">
          <label class="text-xs font-semibold text-gray-600">{{ t('chat.replayMessage.presetPrompt') }}</label>
          <a-textarea
            v-model="presetPromptPatch"
            :placeholder="t('chat.replayMessage.presetPromptPlaceholder')"
            :auto-size="{ minRows: 3, maxRows: 6 }"
          />
        </div>

        <!-- Snapshot Result after replay -->
        <div v-if="snapshot" class="p-3 bg-emerald-50 border border-emerald-200 rounded-lg flex flex-col gap-2 text-xs">
          <div class="font-semibold text-emerald-800 flex items-center gap-1">
            <icon-check-circle class="text-emerald-600" />
            {{ t('chat.replayMessage.snapshotReady') }}
          </div>
          <div class="flex items-center gap-2 flex-wrap">
            <span class="text-gray-600 font-medium">{{ t('chat.replayMessage.appliedPatches') }}:</span>
            <template v-if="snapshot.applied_patch_keys && snapshot.applied_patch_keys.length > 0">
              <a-tag
                v-for="key in snapshot.applied_patch_keys"
                :key="key"
                size="small"
                color="green"
              >
                {{ key }}
              </a-tag>
            </template>
            <span v-else class="text-gray-400">{{ t('chat.replayMessage.noPatches') }}</span>
          </div>
        </div>

        <!-- Actions -->
        <div class="flex justify-end gap-2 pt-2 border-t">
          <a-button @click="close">{{ t('common.cancel') }}</a-button>
          <a-button
            type="primary"
            :loading="loading"
            @click="handleReplay"
          >
            {{ t('chat.replayMessage.executeReplay') }}
          </a-button>
        </div>
      </div>
    </a-spin>
  </a-modal>
</template>
