import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import MarkdownEditor from '../MarkdownEditor.vue'

const markdownEditorSource = readFileSync(
  resolve(process.cwd(), 'src/components/MarkdownEditor.vue'),
  'utf8',
)

describe('MarkdownEditor.vue', () => {
  it('keeps split mode shrinkable instead of forcing fixed-width tracks', () => {
    expect(markdownEditorSource).toContain('.editor-body.split-mode')
    expect(markdownEditorSource).not.toContain('max(600px')
    expect(markdownEditorSource).toContain('grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);')
    expect(markdownEditorSource).toContain('min-width: 0;')
  })

  it('supports a compact toolbar variant for prompt editors', () => {
    const compactToolbarSource = markdownEditorSource
      .split('<template v-if="isCompactToolbar">')[1]
      ?.split('<template v-else>')[0] ?? ''

    expect(markdownEditorSource).toContain(
      "toolbarVariant: { type: String as () => 'full' | 'compact', default: 'full' }",
    )
    expect(markdownEditorSource).toContain(
      "const isCompactToolbar = computed(() => props.toolbarVariant === 'compact')",
    )
    expect(markdownEditorSource).toContain('v-if="isCompactToolbar"')
    expect(markdownEditorSource).toContain('v-else')
    expect(compactToolbarSource).not.toContain('icon-more')
    expect(compactToolbarSource).not.toContain('icon-quote')
    expect(compactToolbarSource).not.toContain('icon-code-block')
    expect(compactToolbarSource).not.toContain('icon-unordered-list')
    expect(compactToolbarSource).not.toContain('icon-ordered-list')
    expect(compactToolbarSource).toContain('toolbar-text-btn')
    expect(compactToolbarSource).toContain('H2')
    expect(compactToolbarSource).toContain('H3')
    expect(compactToolbarSource).toContain('icon-bold')
    expect(compactToolbarSource).toContain('icon-italic')
    expect(compactToolbarSource).toContain('icon-code')
    expect(compactToolbarSource).toContain('icon-link')
    expect(markdownEditorSource).not.toContain("insertMarkdown('ul')")
    expect(markdownEditorSource).not.toContain("insertMarkdown('ol')")
  })

  it('keeps the footer outside the mode-specific panes so the card height stays stable', () => {
    expect(markdownEditorSource).toContain('class="editor-footer"')
    expect(markdownEditorSource).toContain('class="preview-pane"')
    expect(markdownEditorSource.indexOf('class="editor-footer"')).toBeGreaterThan(
      markdownEditorSource.indexOf('class="preview-pane"'),
    )
  })

  it('uses a unified box model so edit preview and split share the same outer height', () => {
    expect(markdownEditorSource).toContain('grid-template-columns: minmax(0, 1fr);')
    expect(markdownEditorSource).toContain('height: 100%;')
    expect(markdownEditorSource).toContain('box-sizing: border-box;')
    expect(markdownEditorSource).toContain('.preview-content')
    expect(markdownEditorSource).toContain('class="editor-surface editor-surface--edit"')
    expect(markdownEditorSource).toContain('class="editor-surface editor-surface--preview"')
    expect(markdownEditorSource).toContain('.editor-surface {')
    expect(markdownEditorSource).toContain('padding: 16px;')
    expect(markdownEditorSource).toContain('padding: 0;')
  })

  it('keeps the edit split preview mode buttons on the same width baseline', () => {
    expect(markdownEditorSource).toContain('type="text"')
    expect(markdownEditorSource).toContain('toolbar-mode-btn')
    expect(markdownEditorSource).toContain('toolbar-mode-btn--active')
    expect(markdownEditorSource).toContain('min-width: 68px;')
    expect(markdownEditorSource).toContain('padding: 0 8px;')
    expect(markdownEditorSource).not.toContain(":type=\"mode === 'edit' ? 'primary' : 'text'\"")
    expect(markdownEditorSource).not.toContain(":type=\"mode === 'split' ? 'primary' : 'text'\"")
    expect(markdownEditorSource).not.toContain(":type=\"mode === 'preview' ? 'primary' : 'text'\"")
  })

  it('does not let toolbar formatting exceed the editor length limit', async () => {
    const wrapper = mount(MarkdownEditor, {
      props: { modelValue: 'a'.repeat(5), maxLength: 5, toolbarVariant: 'compact' },
      global: {
        stubs: {
          '*': true,
          'a-space': { template: '<div><slot /></div>' },
          'a-button': {
            emits: ['click'],
            template: '<button class="toolbar-btn" @click="$emit(\'click\')"><slot /></button>',
          },
        },
      },
    })
    const textarea = wrapper.get('textarea').element as HTMLTextAreaElement
    textarea.setSelectionRange(4, 5)

    await wrapper.findAll('button.toolbar-btn')[3].trigger('click')

    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
    await wrapper.setProps({ modelValue: 'a', maxLength: 10 })
    textarea.setSelectionRange(0, 1)
    await wrapper.findAll('button.toolbar-btn')[3].trigger('click')
    expect(wrapper.emitted('update:modelValue')).toEqual([['**a**']])
    wrapper.unmount()
  })
})
