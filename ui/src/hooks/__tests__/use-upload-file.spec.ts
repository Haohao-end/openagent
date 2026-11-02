import { describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({ uploadImage: vi.fn() }))
vi.mock('@/services/upload-file', () => ({ uploadImage: mocks.uploadImage, uploadFile: vi.fn() }))

import { useUploadImage } from '@/hooks/use-upload-file'

const deferred = () => {
  let resolve!: (value: any) => void
  const promise = new Promise<any>(done => { resolve = done })
  return { promise, resolve }
}

describe('useUploadImage', () => {
  it('keeps the latest upload while an earlier upload finishes', async () => {
    const older = deferred()
    const newer = deferred()
    mocks.uploadImage.mockReset().mockReturnValueOnce(older.promise).mockReturnValueOnce(newer.promise)
    const { image_url, loading, handleUploadImage } = useUploadImage()
    const oldRequest = handleUploadImage(new File(['old'], 'old.png'))
    const newRequest = handleUploadImage(new File(['new'], 'new.png'))

    older.resolve({ data: { image_url: 'old.png' } })
    await oldRequest
    expect(image_url.value).toBe('')
    expect(loading.value).toBe(true)

    newer.resolve({ data: { image_url: 'new.png' } })
    await newRequest
    expect(image_url.value).toBe('new.png')
    expect(loading.value).toBe(false)
  })
})
