<script setup lang="ts">
import { computed, ref, type PropType } from 'vue'

type ComposerSize = 'default' | 'compact'

const props = defineProps({
  modelValue: { type: String, default: '' },
  placeholder: { type: String, default: '发送消息' },
  size: { type: String as PropType<ComposerSize>, default: 'default' },
  textareaRefSetter: {
    type: Function as PropType<(element: HTMLTextAreaElement | null) => void>,
    default: undefined,
  },
  fileInputRefSetter: {
    type: Function as PropType<(element: HTMLInputElement | null) => void>,
    default: undefined,
  },
  imageUrls: { type: Array as PropType<string[]>, default: () => [] },
  showImagePreviews: { type: Boolean, default: false },
  showClearButton: { type: Boolean, default: true },
  showUploadButton: { type: Boolean, default: true },
  showVoiceButton: { type: Boolean, default: true },
  clearTitle: { type: String, default: '清空会话' },
  clearDisabled: { type: Boolean, default: false },
  clearLoading: { type: Boolean, default: false },
  uploadLoading: { type: Boolean, default: false },
  submitLoading: { type: Boolean, default: false },
  audioToTextLoading: { type: Boolean, default: false },
  isRecording: { type: Boolean, default: false },
  isInputBreathing: { type: Boolean, default: false },
})

const emit = defineEmits([
  'update:modelValue',
  'clear',
  'upload',
  'remove-image',
  'start-record',
  'stop-record',
  'submit',
  'input',
  'keydown',
  'focus',
  'blur',
  'file-change',
])

const isFocused = ref(false)
const localTextareaRef = ref<HTMLTextAreaElement | null>(null)
const localFileInputRef = ref<HTMLInputElement | null>(null)
const isCompact = computed(() => props.size === 'compact')

const rootClass = computed(() => {
  if (!props.showClearButton) return 'w-full'

  return isCompact.value
    ? 'grid w-full grid-cols-[auto_minmax(0,1fr)] items-center gap-2.5'
    : 'grid w-full grid-cols-[auto_minmax(0,1fr)] items-center gap-3'
})

const clearButtonClass = computed(() => {
  return [
    'chat-composer-clear-btn',
    isCompact.value ? 'h-9 w-9 rounded-xl' : 'h-10 w-10 rounded-xl',
    props.clearDisabled || props.clearLoading
      ? 'chat-composer-clear-btn--disabled'
      : 'chat-composer-clear-btn--active',
  ]
})

const shellClass = computed(() => {
  return [
    'chat-composer-shell',
    isCompact.value
      ? 'chat-composer-shell--compact rounded-xl px-3 py-2'
      : 'rounded-2xl px-3 sm:px-4 py-2.5',
    {
      'chat-composer-shell--breathing': props.isInputBreathing,
      'chat-composer-shell--focused': isFocused.value,
      'chat-composer-shell--with-images': props.showImagePreviews && props.imageUrls.length > 0,
    },
  ]
})

const inputRowClass = computed(() => {
  return props.showUploadButton
    ? 'grid min-w-0 grid-cols-[auto_minmax(0,1fr)_auto] items-center'
    : 'grid min-w-0 grid-cols-[minmax(0,1fr)_auto] items-center'
})

const actionButtonClass = computed(() => {
  return [
    'chat-composer-action-btn',
    isCompact.value ? 'h-8 w-8 rounded-[10px]' : 'h-10 w-10 rounded-xl',
  ]
})

const textareaClass = computed(() => {
  return [
    'chat-composer-textarea',
    isCompact.value ? 'chat-composer-textarea--compact' : 'chat-composer-textarea--default',
  ]
})

const trailingActionsClass = computed(() => {
  return ['flex shrink-0 items-center self-center', isCompact.value ? 'gap-1' : 'gap-1.5']
})

const previewSizeClass = computed(() => {
  return isCompact.value ? 'h-9 w-9 rounded-lg' : 'h-10 w-10 rounded-lg'
})

const assignTextareaRef = (element: unknown) => {
  localTextareaRef.value = element as HTMLTextAreaElement | null
  props.textareaRefSetter?.(localTextareaRef.value)
}

const assignFileInputRef = (element: unknown) => {
  localFileInputRef.value = element as HTMLInputElement | null
  props.fileInputRefSetter?.(localFileInputRef.value)
}

const focusTextarea = () => {
  localTextareaRef.value?.focus()
}

const handleInput = (event: Event) => {
  emit('update:modelValue', (event.target as HTMLTextAreaElement).value)
  emit('input', event)
}

const handleFocus = (event: FocusEvent) => {
  isFocused.value = true
  emit('focus', event)
}

const handleBlur = (event: FocusEvent) => {
  isFocused.value = false
  emit('blur', event)
}
</script>

<template>
  <div :class="rootClass">
    <button
      v-if="showClearButton"
      type="button"
      :disabled="clearDisabled || clearLoading"
      :class="clearButtonClass"
      :title="clearTitle"
      @click="$emit('clear')"
    >
      <svg
        v-if="!clearLoading"
        :class="isCompact ? 'h-4 w-4' : 'h-5 w-5'"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
        />
      </svg>
      <svg
        v-else
        :class="['animate-spin', isCompact ? 'h-4 w-4' : 'h-5 w-5']"
        viewBox="0 0 24 24"
        fill="none"
      >
        <circle class="opacity-25" cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2" />
        <path
          class="opacity-90"
          d="M21 12a9 9 0 0 0-9-9"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
        />
      </svg>
    </button>

    <div :class="shellClass" @click="focusTextarea">
      <div
        v-if="showImagePreviews && imageUrls.length > 0"
        class="flex flex-wrap items-center gap-2"
      >
        <div
          v-for="(imageUrl, index) in imageUrls"
          :key="`${imageUrl}-${index}`"
          :class="['chat-composer-image', previewSizeClass]"
        >
          <img :src="imageUrl" alt="" class="h-full w-full object-cover" />
          <button
            type="button"
            class="chat-composer-image-remove"
            title="移除图片"
            @click.stop="$emit('remove-image', index)"
          >
            <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>
      </div>

      <div :class="[inputRowClass, isCompact ? 'gap-1.5' : 'gap-2']">
        <button
          v-if="showUploadButton"
          type="button"
          :disabled="uploadLoading"
          :class="[
            actionButtonClass,
            'text-gray-600 hover:bg-white/20 hover:text-gray-800 disabled:opacity-60',
          ]"
          title="上传图片"
          @click.stop="$emit('upload')"
        >
          <svg
            v-if="!uploadLoading"
            :class="isCompact ? 'h-4 w-4' : 'h-5 w-5'"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M12 4v16m8-8H4"
            />
          </svg>
          <svg
            v-else
            :class="['animate-spin', isCompact ? 'h-4 w-4' : 'h-5 w-5']"
            viewBox="0 0 24 24"
            fill="none"
          >
            <circle
              class="opacity-25"
              cx="12"
              cy="12"
              r="9"
              stroke="currentColor"
              stroke-width="2"
            />
            <path
              class="opacity-90"
              d="M21 12a9 9 0 0 0-9-9"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
            />
          </svg>
        </button>

        <input
          type="file"
          :ref="assignFileInputRef"
          accept="image/*"
          class="hidden"
          @change="$emit('file-change', $event)"
        />

        <textarea
          :ref="assignTextareaRef"
          :value="modelValue"
          rows="1"
          :class="textareaClass"
          :placeholder="placeholder"
          @input="handleInput"
          @keydown="$emit('keydown', $event)"
          @focus="handleFocus"
          @blur="handleBlur"
        />

        <div :class="trailingActionsClass">
          <button
            v-if="showVoiceButton && !audioToTextLoading && !isRecording"
            type="button"
            :class="[actionButtonClass, 'text-gray-600 hover:bg-white/20 hover:text-gray-800']"
            title="开始录音"
            @click.stop="$emit('start-record')"
          >
            <svg
              :class="isCompact ? 'h-4 w-4' : 'h-5 w-5'"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <rect x="9" y="3" width="6" height="11" rx="3" stroke-width="1.9" />
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="1.9"
                d="M6 10.5v1a6 6 0 0 0 12 0v-1M12 17.5V21M8.5 21h7"
              />
            </svg>
          </button>

          <button
            v-else-if="showVoiceButton && isRecording"
            type="button"
            :class="[
              actionButtonClass,
              'animate-pulse text-red-500 hover:bg-red-50/60 hover:text-red-600',
            ]"
            title="停止录音"
            @click.stop="$emit('stop-record')"
          >
            <svg :class="isCompact ? 'h-4 w-4' : 'h-5 w-5'" fill="currentColor" viewBox="0 0 24 24">
              <path d="M6 4h12v12H6z" />
            </svg>
          </button>

          <button
            v-else-if="showVoiceButton"
            type="button"
            disabled
            :class="[actionButtonClass, 'cursor-wait text-cyan-500/80']"
            title="正在转写"
          >
            <svg
              :class="['animate-spin', isCompact ? 'h-4 w-4' : 'h-5 w-5']"
              viewBox="0 0 24 24"
              fill="none"
            >
              <circle
                class="opacity-25"
                cx="12"
                cy="12"
                r="9"
                stroke="currentColor"
                stroke-width="2"
              />
              <path
                class="opacity-90"
                d="M21 12a9 9 0 0 0-9-9"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
              />
            </svg>
          </button>

          <button
            type="button"
            :disabled="submitLoading"
            :class="[
              actionButtonClass,
              'text-cyan-600 hover:bg-cyan-500/20 hover:text-cyan-700 disabled:opacity-50',
            ]"
            title="发送消息"
            aria-label="发送消息"
            @click.stop="$emit('submit')"
          >
            <svg :class="isCompact ? 'h-4 w-4' : 'h-5 w-5'" fill="currentColor" viewBox="0 0 24 24">
              <path
                d="M16.6915026,12.4744748 L3.50612381,13.2599618 C3.19218622,13.2599618 3.03521743,13.4170592 3.03521743,13.5741566 L1.15159189,20.0151496 C0.8376543,20.8006365 0.99,21.89 1.77946707,22.52 C2.41,22.99 3.50612381,23.1 4.13399899,22.8429026 L21.714504,14.0454487 C22.6563168,13.5741566 23.1272231,12.6315722 22.9702544,11.6889879 L4.13399899,1.16346272 C3.34915502,0.9 2.40734225,1.00636533 1.77946707,1.4776575 C0.994623095,2.10604706 0.837654326,3.0486314 1.15159189,3.99701575 L3.03521743,10.4380088 C3.03521743,10.5951061 3.19218622,10.7522035 3.50612381,10.7522035 L16.6915026,11.5376905 C16.6915026,11.5376905 17.1624089,11.5376905 17.1624089,12.0089827 C17.1624089,12.4744748 16.6915026,12.4744748 16.6915026,12.4744748 Z"
              />
            </svg>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-composer-shell {
  min-width: 0;
  min-height: 56px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  background:
    linear-gradient(0deg, rgba(255, 255, 255, 0.96), rgba(255, 255, 255, 0.96)) padding-box,
    linear-gradient(
        135deg,
        rgba(56, 189, 248, 0.36) 0%,
        rgba(167, 139, 250, 0.3) 52%,
        rgba(244, 114, 182, 0.36) 100%
      )
      border-box;
  -webkit-backdrop-filter: blur(12px);
  backdrop-filter: blur(12px);
  border: 2px solid transparent;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.88),
    inset 0 -1px 0 rgba(15, 23, 42, 0.04),
    0 10px 28px rgba(14, 165, 233, 0.08);
  transition: all 0.3s ease;
}

.chat-composer-shell--compact {
  min-height: 50px;
  gap: 6px;
}

.chat-composer-shell--with-images {
  min-height: auto;
}

.chat-composer-shell:focus-within,
.chat-composer-shell--focused {
  background:
    linear-gradient(0deg, rgba(255, 255, 255, 1), rgba(255, 255, 255, 1)) padding-box,
    linear-gradient(135deg, #38bdf8 0%, #a78bfa 52%, #f472b6 100%) border-box;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.96),
    inset 0 -1px 0 rgba(15, 23, 42, 0.04),
    0 0 0 4px rgba(125, 211, 252, 0.12),
    0 14px 40px rgba(14, 165, 233, 0.1);
}

.chat-composer-shell--breathing {
  animation: chat-composer-breathe 1.4s ease-in-out infinite;
}

.chat-composer-clear-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border: 1px solid transparent;
  transition: all 0.3s ease;
}

.chat-composer-clear-btn--active {
  background: rgba(255, 255, 255, 0.4);
  -webkit-backdrop-filter: blur(12px);
  backdrop-filter: blur(12px);
  border-color: rgba(255, 255, 255, 0.6);
  color: #4b5563;
}

.chat-composer-clear-btn--active:hover {
  background: rgba(255, 255, 255, 0.6);
  color: #dc2626;
  border-color: rgba(252, 165, 165, 0.65);
  box-shadow: 0 8px 20px rgba(248, 113, 113, 0.16);
}

.chat-composer-clear-btn--disabled {
  background: rgba(255, 255, 255, 0.2);
  border-color: rgba(255, 255, 255, 0.4);
  color: #9ca3af;
  cursor: not-allowed;
  opacity: 0.72;
}

.chat-composer-action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition:
    color 0.2s ease,
    background-color 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.2s ease;
}

.chat-composer-action-btn:disabled {
  cursor: not-allowed;
}

.chat-composer-textarea {
  width: 100%;
  min-width: 0;
  margin: 0;
  border: 0;
  background: transparent;
  color: #1f2937;
  resize: none;
  outline: none;
  caret-color: #0ea5e9;
  overflow-y: auto;
  overscroll-behavior: contain;
}

.chat-composer-textarea--default {
  min-height: 36px;
  max-height: 120px;
  padding: 7px 0;
  font-size: 14px;
  line-height: 1.5;
}

.chat-composer-textarea--compact {
  min-height: 32px;
  max-height: 96px;
  padding: 5px 0;
  font-size: 13px;
  line-height: 1.45;
}

.chat-composer-textarea::placeholder {
  color: #9ca3af;
}

.chat-composer-textarea:focus {
  outline: none;
  box-shadow: none;
}

.chat-composer-textarea::-webkit-scrollbar {
  width: 4px;
}

.chat-composer-textarea::-webkit-scrollbar-track {
  background: transparent;
}

.chat-composer-textarea::-webkit-scrollbar-thumb {
  background: rgba(125, 211, 252, 0.3);
  border-radius: 2px;
}

.chat-composer-textarea::-webkit-scrollbar-thumb:hover {
  background: rgba(125, 211, 252, 0.5);
}

.chat-composer-image {
  position: relative;
  overflow: hidden;
  border: 1px solid rgba(226, 232, 240, 0.85);
  background: #f8fafc;
  box-shadow: 0 6px 14px rgba(148, 163, 184, 0.14);
}

.chat-composer-image-remove {
  position: absolute;
  right: 4px;
  bottom: 4px;
  display: inline-flex;
  height: 18px;
  width: 18px;
  align-items: center;
  justify-content: center;
  border-radius: 9999px;
  background: rgba(15, 23, 42, 0.72);
  color: #fff;
  transition: background-color 0.2s ease;
}

.chat-composer-image-remove:hover {
  background: rgba(15, 23, 42, 0.88);
}

@keyframes chat-composer-breathe {
  0% {
    background:
      linear-gradient(0deg, rgba(255, 255, 255, 0.96), rgba(255, 255, 255, 0.96)) padding-box,
      linear-gradient(
          135deg,
          rgba(56, 189, 248, 0.36) 0%,
          rgba(167, 139, 250, 0.3) 52%,
          rgba(244, 114, 182, 0.36) 100%
        )
        border-box;
    box-shadow:
      inset 0 1px 0 rgba(255, 255, 255, 0.88),
      inset 0 -1px 0 rgba(15, 23, 42, 0.04),
      0 10px 28px rgba(14, 165, 233, 0.08);
  }
  50% {
    background:
      linear-gradient(0deg, rgba(255, 255, 255, 1), rgba(255, 255, 255, 1)) padding-box,
      linear-gradient(
          135deg,
          rgba(56, 189, 248, 0.54) 0%,
          rgba(167, 139, 250, 0.42) 52%,
          rgba(244, 114, 182, 0.5) 100%
        )
        border-box;
    box-shadow:
      inset 0 1px 0 rgba(255, 255, 255, 0.96),
      inset 0 -1px 0 rgba(15, 23, 42, 0.04),
      0 0 0 5px rgba(125, 211, 252, 0.12),
      0 14px 36px rgba(14, 165, 233, 0.1);
  }
  100% {
    background:
      linear-gradient(0deg, rgba(255, 255, 255, 0.96), rgba(255, 255, 255, 0.96)) padding-box,
      linear-gradient(
          135deg,
          rgba(56, 189, 248, 0.36) 0%,
          rgba(167, 139, 250, 0.3) 52%,
          rgba(244, 114, 182, 0.36) 100%
        )
        border-box;
    box-shadow:
      inset 0 1px 0 rgba(255, 255, 255, 0.88),
      inset 0 -1px 0 rgba(15, 23, 42, 0.04),
      0 10px 28px rgba(14, 165, 233, 0.08);
  }
}
</style>
