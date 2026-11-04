import { defineComponent } from 'vue'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import PresetPromptTextarea from '@/views/space/apps/components/PresetPromptTextarea.vue'
const { updateDraft } = vi.hoisted(() => ({ updateDraft: vi.fn() }))
vi.mock('@/hooks/use-app', () => ({
  useUpdateDraftAppConfig: () => ({ handleUpdateDraftAppConfig: updateDraft }),
}))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
const stubs = {
  MarkdownEditor: defineComponent({ emits: ['blur'], template: '<textarea data-testid="editor" @blur="$emit(\'blur\')" />' }),
  PromptOptimizeTrigger: defineComponent({ emits: ['apply'], template: '<button data-testid="optimize" @click="$emit(\'apply\', \'optimized\')" />' }),
  'a-space': defineComponent({ template: '<div><slot /></div>' }),
}
it('does not print raw prompt save errors', async () => {
  updateDraft.mockRejectedValue(new Error('token=private-prompt-detail'))
  const log = vi.spyOn(console, 'error').mockImplementation(() => {})
  const wrapper = shallowMount(PresetPromptTextarea, {
    props: { app_id: 'app-1', preset_prompt: 'private prompt' },
    global: { stubs },
  })
  await wrapper.get('[data-testid="optimize"]').trigger('click')
  await flushPromises()
  await wrapper.get('[data-testid="editor"]').trigger('blur')
  await flushPromises()
  expect(log).toHaveBeenCalledTimes(2)
  expect(log.mock.calls.flat().join(' ')).not.toContain('private-prompt-detail')
  wrapper.unmount()
  log.mockRestore()
})
