import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js/lib/common'
import { Message } from '@arco-design/web-vue'
import { i18n } from '@/i18n'
import { copyTextToClipboard } from '@/utils/clipboard'

type MarkdownRendererOptions = {
  typographer?: boolean
}

type CopyHandlerOptions = {
  successMessage?: string
  errorMessage?: string
}

const ALLOWED_LINK_PROTOCOLS = new Set(['http:', 'https:'])
const translate = (key: string, values?: Record<string, unknown>) =>
  (values ? i18n.global.t(key, values) : i18n.global.t(key)) as string

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
  md.validateLink = (url: string) => {
    try {
      const parsed = new URL(url)
      return ALLOWED_LINK_PROTOCOLS.has(parsed.protocol)
    } catch {
      return false
    }
  }

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
      <button type="button" class="md-code-copy-btn" data-copy-code="${encodedCode}">${escapeHtml(translate('chat.markdown.copyCode'))}</button>
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
    try {
      await copyTextToClipboard(code)
    } catch {
      Message.error(copyOptions.errorMessage || translate('chat.messages.copyFailed'))
      return false
    }

    const defaultCopyText = translate('chat.markdown.copyCode')
    const copiedText = translate('chat.messages.codeCopied')
    const previousText = copyButton.textContent || defaultCopyText
    copyButton.textContent = copiedText
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
