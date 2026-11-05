import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import DetailView from '../DetailView.vue'

const mocks = vi.hoisted(() => ({
  route: {
    params: { app_id: 'app-1' },
  } as any,
  draftAppConfigForm: null as null | { value: Record<string, any> },
  loadDraftAppConfig: vi.fn().mockResolvedValue(undefined),
}))

vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-router')>()
  return {
    ...actual,
    useRoute: () => mocks.route,
  }
})

vi.mock('@/hooks/use-app', async () => {
  const { ref } = await import('vue')
  if (!mocks.draftAppConfigForm) {
    mocks.draftAppConfigForm = ref({
      dialog_round: 3,
      model_config: { provider: 'deepseek', model: 'deepseek-chat', parameters: {} },
      capabilities: { image_input: { enabled: false } },
      preset_prompt: 'prompt',
      long_term_memory: { enable: false },
      opening_statement: '',
      opening_questions: [],
      suggested_after_answer: { enable: false },
      review_config: { enable: false },
      datasets: [],
      retrieval_config: { retrieval_strategy: 'semantic', k: 10, score: 0.5 },
      tools: [],
      mcp_bindings: [],
      mcp_tool_snapshots: [],
      workflows: [],
      speech_to_text: { enable: false },
      text_to_speech: { enable: false, voice: 'alex', auto_play: false },
    })
  }
  return {
    useGetDraftAppConfig: () => ({
      loading: ref(false),
      draftAppConfigForm: mocks.draftAppConfigForm,
      loadDraftAppConfig: mocks.loadDraftAppConfig,
    }),
  }
})

describe('DetailView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    if (!mocks.draftAppConfigForm) {
      throw new Error('draftAppConfigForm mock not initialized')
    }
    mocks.draftAppConfigForm.value = {
      dialog_round: 3,
      model_config: { provider: 'deepseek', model: 'deepseek-chat', parameters: {} },
      capabilities: { image_input: { enabled: false } },
      preset_prompt: 'prompt',
      long_term_memory: { enable: false },
      opening_statement: '',
      opening_questions: [],
      suggested_after_answer: { enable: false },
      review_config: { enable: false },
      datasets: [],
      retrieval_config: { retrieval_strategy: 'semantic', k: 10, score: 0.5 },
      tools: [],
      mcp_bindings: [],
      mcp_tool_snapshots: [],
      workflows: [],
      speech_to_text: { enable: false },
      text_to_speech: { enable: false, voice: 'alex', auto_play: false },
    }
  })

  it('reloads draft config when the selected model changes', async () => {
    const wrapper = shallowMount(DetailView, {
      props: {
        app: {
          id: 'app-1',
        },
      },
      global: {
        stubs: {
          'agent-app-ability': true,
          'model-config': true,
          'preset-prompt-textarea': true,
          'preview-debug-chat': true,
          'preview-debug-header': true,
        },
      },
    })

    await flushPromises()
    expect(mocks.loadDraftAppConfig).toHaveBeenCalledTimes(1)

    mocks.draftAppConfigForm!.value.model_config = {
      provider: 'openai',
      model: 'gpt-4o-mini',
      parameters: {},
    }

    await flushPromises()

    expect(mocks.loadDraftAppConfig).toHaveBeenCalledTimes(2)
    wrapper.unmount()
  })

  it('queues a draft refresh for a second model change during an existing refresh', async () => {
    let finishRefresh!: () => void
    const pendingRefresh = new Promise<void>((resolve) => { finishRefresh = resolve })
    mocks.loadDraftAppConfig
      .mockReset()
      .mockResolvedValueOnce(undefined)
      .mockReturnValueOnce(pendingRefresh)
      .mockResolvedValueOnce(undefined)
    const wrapper = shallowMount(DetailView, {
      props: { app: { id: 'app-1' } },
      global: { stubs: { 'agent-app-ability': true, 'model-config': true, 'preset-prompt-textarea': true, 'preview-debug-chat': true, 'preview-debug-header': true } },
    })
    await flushPromises()

    mocks.draftAppConfigForm!.value.model_config = { provider: 'first', model: 'first-model', parameters: {} }
    await flushPromises()
    expect(mocks.loadDraftAppConfig).toHaveBeenCalledTimes(2)

    mocks.draftAppConfigForm!.value.model_config = { provider: 'second', model: 'second-model', parameters: {} }
    await flushPromises()
    finishRefresh()
    await flushPromises()

    expect(mocks.loadDraftAppConfig).toHaveBeenCalledTimes(3)
    wrapper.unmount()
  })

  it('uses flex-based layout instead of viewport height constants', () => {
    const source = readFileSync(resolve(process.cwd(), 'src/views/space/apps/DetailView.vue'), 'utf8')

    expect(source).not.toContain('100vh-141px')
    expect(source).not.toContain('100vh-173px')
    expect(source).toContain('grid-cols-[minmax(0,13fr)_minmax(0,12fr)]')
  })
})
