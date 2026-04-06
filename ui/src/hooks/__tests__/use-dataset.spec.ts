import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  useDeleteDocument,
  useDeleteSegment,
  useUpdateDocumentEnabled,
  useUpdateDocumentName,
  useUpdateSegmentEnabled,
} from '@/hooks/use-dataset'

const mocks = vi.hoisted(() => ({
  createDataset: vi.fn(),
  createDocuments: vi.fn(),
  createSegment: vi.fn(),
  deleteDataset: vi.fn(),
  deleteDocument: vi.fn(),
  deleteSegment: vi.fn(),
  generateIconPreview: vi.fn(),
  getDataset: vi.fn(),
  getDatasetQueries: vi.fn(),
  getDatasetsWithPage: vi.fn(),
  getDocument: vi.fn(),
  getDocumentsStatus: vi.fn(),
  getDocumentsWithPage: vi.fn(),
  getSegment: vi.fn(),
  getSegmentsWithPage: vi.fn(),
  hit: vi.fn(),
  regenerateIcon: vi.fn(),
  updateDataset: vi.fn(),
  updateDocumentEnabled: vi.fn(),
  updateDocumentName: vi.fn(),
  updateSegment: vi.fn(),
  updateSegmentEnabled: vi.fn(),
  modalWarning: vi.fn(),
  messageSuccess: vi.fn(),
  messageError: vi.fn(),
}))

vi.mock('@/services/dataset', () => ({
  createDataset: mocks.createDataset,
  createDocuments: mocks.createDocuments,
  createSegment: mocks.createSegment,
  deleteDataset: mocks.deleteDataset,
  deleteDocument: mocks.deleteDocument,
  deleteSegment: mocks.deleteSegment,
  generateIconPreview: mocks.generateIconPreview,
  getDataset: mocks.getDataset,
  getDatasetQueries: mocks.getDatasetQueries,
  getDatasetsWithPage: mocks.getDatasetsWithPage,
  getDocument: mocks.getDocument,
  getDocumentsStatus: mocks.getDocumentsStatus,
  getDocumentsWithPage: mocks.getDocumentsWithPage,
  getSegment: mocks.getSegment,
  getSegmentsWithPage: mocks.getSegmentsWithPage,
  hit: mocks.hit,
  regenerateIcon: mocks.regenerateIcon,
  updateDataset: mocks.updateDataset,
  updateDocumentEnabled: mocks.updateDocumentEnabled,
  updateDocumentName: mocks.updateDocumentName,
  updateSegment: mocks.updateSegment,
  updateSegmentEnabled: mocks.updateSegmentEnabled,
}))

vi.mock('@arco-design/web-vue', () => ({
  Form: class {},
  Message: {
    success: mocks.messageSuccess,
    error: mocks.messageError,
  },
  Modal: {
    warning: mocks.modalWarning,
  },
}))

describe('use-dataset action callbacks', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('only invokes document enabled callback after a successful update', async () => {
    const callback = vi.fn()
    const { handleUpdate } = useUpdateDocumentEnabled()

    mocks.updateDocumentEnabled.mockResolvedValueOnce({ message: 'ok' })
    await handleUpdate('dataset-1', 'document-1', true, callback)

    expect(callback).toHaveBeenCalledTimes(1)
    expect(mocks.messageSuccess).toHaveBeenCalledWith('ok')

    callback.mockClear()
    mocks.updateDocumentEnabled.mockRejectedValueOnce(new Error('toggle failed'))

    await expect(handleUpdate('dataset-1', 'document-1', false, callback)).rejects.toThrow(
      'toggle failed',
    )

    expect(callback).not.toHaveBeenCalled()
    expect(mocks.messageError).toHaveBeenCalledWith('toggle failed')
  })

  it('only invokes document delete callback after a successful delete', async () => {
    const callback = vi.fn()
    const { handleDelete } = useDeleteDocument()

    handleDelete('dataset-1', 'document-1', callback)
    const modalConfig = mocks.modalWarning.mock.calls[0]?.[0]
    expect(modalConfig).toBeTruthy()

    mocks.deleteDocument.mockResolvedValueOnce({ message: 'deleted' })
    await modalConfig.onOk()

    expect(callback).toHaveBeenCalledTimes(1)
    expect(mocks.messageSuccess).toHaveBeenCalledWith('deleted')

    callback.mockClear()
    mocks.deleteDocument.mockRejectedValueOnce(new Error('delete failed'))

    await expect(modalConfig.onOk()).rejects.toThrow('delete failed')
    expect(callback).not.toHaveBeenCalled()
    expect(mocks.messageError).toHaveBeenCalledWith('delete failed')
  })

  it('only invokes segment enabled callback after a successful update', async () => {
    const callback = vi.fn()
    const { handleUpdate } = useUpdateSegmentEnabled()

    mocks.updateSegmentEnabled.mockResolvedValueOnce({ message: 'ok' })
    await handleUpdate('dataset-1', 'document-1', 'segment-1', true, callback)

    expect(callback).toHaveBeenCalledTimes(1)
    expect(mocks.messageSuccess).toHaveBeenCalledWith('ok')

    callback.mockClear()
    mocks.updateSegmentEnabled.mockRejectedValueOnce(new Error('segment toggle failed'))

    await expect(
      handleUpdate('dataset-1', 'document-1', 'segment-1', false, callback),
    ).rejects.toThrow('segment toggle failed')

    expect(callback).not.toHaveBeenCalled()
    expect(mocks.messageError).toHaveBeenCalledWith('segment toggle failed')
  })

  it('only invokes segment delete callback after a successful delete', async () => {
    const callback = vi.fn()
    const { handleDelete } = useDeleteSegment()

    handleDelete('dataset-1', 'document-1', 'segment-1', callback)
    const modalConfig = mocks.modalWarning.mock.calls[0]?.[0]
    expect(modalConfig).toBeTruthy()

    mocks.deleteSegment.mockResolvedValueOnce({ message: 'deleted' })
    await modalConfig.onOk()

    expect(callback).toHaveBeenCalledTimes(1)
    expect(mocks.messageSuccess).toHaveBeenCalledWith('deleted')

    callback.mockClear()
    mocks.deleteSegment.mockRejectedValueOnce(new Error('segment delete failed'))

    await expect(modalConfig.onOk()).rejects.toThrow('segment delete failed')
    expect(callback).not.toHaveBeenCalled()
    expect(mocks.messageError).toHaveBeenCalledWith('segment delete failed')
  })

  it('surfaces document rename failures to the caller', async () => {
    const { handleUpdateDocumentName } = useUpdateDocumentName()

    mocks.updateDocumentName.mockRejectedValueOnce(new Error('rename failed'))

    await expect(
      handleUpdateDocumentName('dataset-1', 'document-1', 'new-name'),
    ).rejects.toThrow('rename failed')
    expect(mocks.messageError).toHaveBeenCalledWith('rename failed')
  })
})
