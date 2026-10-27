import { afterEach, describe, expect, it, vi } from 'vitest'
import { copyTextToClipboard } from '../clipboard'

afterEach(() => {
  vi.unstubAllGlobals()
})

const useFallbackCopy = (succeeds: boolean) => {
  vi.stubGlobal('navigator', {})
  const original = Object.getOwnPropertyDescriptor(document, 'execCommand')
  const execute = vi.fn(() => succeeds)
  Object.defineProperty(document, 'execCommand', { configurable: true, value: execute })
  return {
    execute,
    restore: () => {
      if (original) Object.defineProperty(document, 'execCommand', original)
      else Reflect.deleteProperty(document, 'execCommand')
    },
  }
}

describe('copyTextToClipboard fallback', () => {
  it('falls back when the modern clipboard API rejects the write', async () => {
    const original = Object.getOwnPropertyDescriptor(document, 'execCommand')
    const execute = vi.fn(() => true)
    const writeText = vi.fn().mockRejectedValue(new Error('NotAllowedError'))
    vi.stubGlobal('navigator', { clipboard: { writeText } })
    Object.defineProperty(document, 'execCommand', { configurable: true, value: execute })

    try {
      await expect(copyTextToClipboard('error details')).resolves.toBeUndefined()
      expect(writeText).toHaveBeenCalledWith('error details')
      expect(execute).toHaveBeenCalledWith('copy')
      expect(document.querySelector('textarea')).toBeNull()
    } finally {
      if (original) Object.defineProperty(document, 'execCommand', original)
      else Reflect.deleteProperty(document, 'execCommand')
    }
  })

  it('reports a rejected legacy copy instead of silently succeeding', async () => {
    const { execute, restore } = useFallbackCopy(false)
    try {
      await expect(copyTextToClipboard('error details')).rejects.toThrow('Clipboard copy failed')
      expect(execute).toHaveBeenCalledWith('copy')
      expect(document.querySelector('textarea')).toBeNull()
    } finally {
      restore()
    }
  })

  it('removes its temporary textarea after a successful legacy copy', async () => {
    const { execute, restore } = useFallbackCopy(true)
    try {
      await expect(copyTextToClipboard('error details')).resolves.toBeUndefined()
      expect(execute).toHaveBeenCalledWith('copy')
      expect(document.querySelector('textarea')).toBeNull()
    } finally {
      restore()
    }
  })

  it('fails explicitly when neither clipboard API nor DOM is available', async () => {
    vi.stubGlobal('navigator', {})
    vi.stubGlobal('document', undefined)
    await expect(copyTextToClipboard('text')).rejects.toThrow('Clipboard is unavailable')
  })
})
