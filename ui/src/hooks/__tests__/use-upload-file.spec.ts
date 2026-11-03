import { describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({ uploadImage: vi.fn(), uploadFile: vi.fn() }))
vi.mock('@/services/upload-file', () => mocks)

import { useUploadFile, useUploadImage } from '@/hooks/use-upload-file'

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

describe('useUploadFile', () => {
  it('does not log upload response data or errors', async () => {
    const response = { data: { file_id: 'private-file-id', name: 'private.txt' } }
    mocks.uploadFile.mockReset().mockResolvedValueOnce(response)
    const log = vi.spyOn(console, 'log').mockImplementation(() => {})
    const error = vi.spyOn(console, 'error').mockImplementation(() => {})
    const hook = useUploadFile()

    await hook.handleUploadFile(new File(['private contents'], 'private.txt'))
    mocks.uploadFile.mockRejectedValueOnce(new Error('private upload failure'))
    await expect(hook.handleUploadFile(new File(['private contents'], 'private.txt'))).rejects.toThrow(
      'private upload failure',
    )

    expect(hook.upload_file.value).toEqual(response.data)
    expect(log).not.toHaveBeenCalled()
    expect(error).not.toHaveBeenCalled()
    log.mockRestore()
    error.mockRestore()
  })
})
