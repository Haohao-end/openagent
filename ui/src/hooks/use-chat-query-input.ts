import { nextTick, ref, watch } from 'vue'
import storage from '@/utils/storage'

type UseChatQueryInputOptions = {
  getDraftKey: () => string
  minHeight: number
  maxHeight: number
}

export const useChatQueryInput = (options: UseChatQueryInputOptions) => {
  const query = ref('')
  const queryTextareaRef = ref<HTMLTextAreaElement | null>(null)

  const adjustQueryTextareaHeight = () => {
    const textarea = queryTextareaRef.value
    if (!textarea) return

    textarea.style.height = 'auto'
    const nextHeight = Math.min(
      Math.max(textarea.scrollHeight, options.minHeight),
      options.maxHeight,
    )
    textarea.style.height = `${nextHeight}px`
    textarea.style.overflowY = textarea.scrollHeight > options.maxHeight ? 'auto' : 'hidden'
  }

  const persistQueryDraft = (value: string) => {
    const key = options.getDraftKey()
    if (value.trim() === '') {
      storage.remove(key)
      return
    }
    storage.set(key, value)
  }

  const restoreQueryDraft = () => {
    query.value = String(storage.get(options.getDraftKey(), ''))
  }

  watch(query, (value) => {
    persistQueryDraft(value)
    nextTick(() => adjustQueryTextareaHeight())
  })

  return {
    query,
    queryTextareaRef,
    adjustQueryTextareaHeight,
    restoreQueryDraft,
  }
}
