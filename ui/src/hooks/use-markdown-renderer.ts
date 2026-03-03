import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js/lib/common'
import { Message } from '@arco-design/web-vue'
import { copyTextToClipboard } from '@/utils/clipboard'

type MarkdownRendererOptions = {
  typographer?: boolean
}

type CopyHandlerOptions = {
  successMessage?: string
}

const escapeHtml = (content: string) =>
  content
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')

export const useMarkdownRenderer = (options: MarkdownRendererOptions = {}) => {
  const md = new MarkdownIt({
    html: false,
    linkify: true,
    breaks: true,
    typographer: options.typographer ?? false,
  })

  md.renderer.rules.fence = (tokens, idx) => {
    const token = tokens[idx] as { info?: unknown; content?: unknown }
    const language = String(token.info || '')
      .trim()
      .split(/\s+/g)[0]
    const code = String(token.content || '')

    let highlightedCode = escapeHtml(code)
    let languageLabel = 'text'
    if (language && hljs.getLanguage(language)) {
      highlightedCode = hljs.highlight(code, { language, ignoreIllegals: true }).value
      languageLabel = language
    }

    const encodedCode = encodeURIComponent(code)

    return `<div class="md-code-block">
    <div class="md-code-header">
      <span class="md-code-lang">${escapeHtml(languageLabel)}</span>
      <button type="button" class="md-code-copy-btn" data-copy-code="${encodedCode}">复制代码</button>
    </div>
    <pre class="hljs"><code>${highlightedCode}</code></pre>
  </div>`
  }

  const renderMarkdown = (content: string) => {
    return md.render(content)
  }

  const renderMarkdownWithPlaceholder = (content: string, placeholder: string) => {
    if (!content) {
      return `<div class="text-gray-400 text-sm">${escapeHtml(placeholder)}</div>`
    }
    return md.render(content)
  }

  const handleMarkdownCopyClick = async (
    event: MouseEvent,
    copyOptions: CopyHandlerOptions = {},
  ) => {
    const target = event.target as HTMLElement | null
    if (!target) return false

    const copyButton = target.closest('.md-code-copy-btn') as HTMLElement | null
    if (!copyButton) return false

    event.preventDefault()
    const encodedCode = copyButton.getAttribute('data-copy-code') || ''
    const code = decodeURIComponent(encodedCode)
    await copyTextToClipboard(code)

    const previousText = copyButton.textContent || '复制代码'
    copyButton.textContent = '已复制'
    copyButton.setAttribute('disabled', 'true')

    const resetTimer = copyButton.getAttribute('data-reset-timer')
    if (resetTimer) {
      globalThis.clearTimeout(Number(resetTimer))
    }

    const timer = globalThis.setTimeout(() => {
      copyButton.textContent = previousText
      copyButton.removeAttribute('disabled')
    }, 1200)

    copyButton.setAttribute('data-reset-timer', String(timer))

    if (copyOptions.successMessage) {
      Message.success(copyOptions.successMessage)
    }

    return true
  }

  return {
    renderMarkdown,
    renderMarkdownWithPlaceholder,
    handleMarkdownCopyClick,
  }
}
