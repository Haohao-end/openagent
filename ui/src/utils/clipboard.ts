export const copyTextToClipboard = async (text: string) => {
  if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text)
      return
    } catch {
      // Clipboard permissions can fail even when the modern API exists; try the DOM fallback.
    }
  }

  if (typeof document === 'undefined') throw new Error('Clipboard is unavailable')

  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.style.position = 'fixed'
  textarea.style.left = '-9999px'
  textarea.style.top = '-9999px'
  document.body.appendChild(textarea)
  try {
    textarea.focus()
    textarea.select()
    if (!document.execCommand('copy')) throw new Error('Clipboard copy failed')
  } finally {
    document.body.removeChild(textarea)
  }
}
