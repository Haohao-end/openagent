import { describe, expect, it, vi } from 'vitest'
import { Message } from '@arco-design/web-vue'
import { copyTextToClipboard } from '@/utils/clipboard'
import { useMarkdownRenderer } from '@/hooks/use-markdown-renderer'

vi.mock('@/utils/clipboard', () => ({
  copyTextToClipboard: vi.fn(),
}))

vi.mock('@arco-design/web-vue', () => ({
  Message: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
  },
}))

describe('useMarkdownRenderer', () => {
  it('renders http links as clickable anchors', () => {
    const { renderMarkdown } = useMarkdownRenderer()

    const html = renderMarkdown('[下载附件](https://example.com/file.svg)')

    expect(html).toContain('href="https://example.com/file.svg"')
  })

  it('rejects sandbox links from markdown output', () => {
    const { renderMarkdown } = useMarkdownRenderer()

    const html = renderMarkdown('[下载附件](sandbox:/mnt/data/file.svg)')

    expect(html).not.toContain('href="sandbox:/mnt/data/file.svg"')
    expect(html).toContain('[下载附件](sandbox:/mnt/data/file.svg)')
  })

  it('copies code and updates button state on click success', async () => {
    vi.mocked(copyTextToClipboard).mockResolvedValueOnce(undefined)
    const { handleMarkdownCopyClick } = useMarkdownRenderer()
    const button = document.createElement('button')
    button.className = 'md-code-copy-btn'
    button.textContent = '复制代码'
    button.setAttribute('data-copy-code', encodeURIComponent('print("ok")'))
    const event = { target: button, preventDefault: vi.fn() } as unknown as MouseEvent

    const result = await handleMarkdownCopyClick(event, { successMessage: '已复制' })

    expect(result).toBe(true)
    expect(copyTextToClipboard).toHaveBeenCalledWith('print("ok")')
    expect(Message.success).toHaveBeenCalledWith('已复制')
    expect(button.textContent).toBe('代码已复制')
  })

  it('surfaces error feedback and preserves button state when copying fails', async () => {
    vi.mocked(copyTextToClipboard).mockRejectedValueOnce(new Error('Permission denied'))
    const { handleMarkdownCopyClick } = useMarkdownRenderer()
    const button = document.createElement('button')
    button.className = 'md-code-copy-btn'
    button.textContent = '复制代码'
    button.setAttribute('data-copy-code', encodeURIComponent('print("err")'))
    const event = { target: button, preventDefault: vi.fn() } as unknown as MouseEvent

    const result = await handleMarkdownCopyClick(event)

    expect(result).toBe(false)
    expect(copyTextToClipboard).toHaveBeenCalledWith('print("err")')
    expect(Message.error).toHaveBeenCalledWith('复制失败')
    expect(button.textContent).toBe('复制代码')
  })
})
