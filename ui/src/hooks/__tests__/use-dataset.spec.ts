import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  useDeleteDocument,
  useDeleteSegment,
  useGetDataset,
  useGetDatasetsWithPage,
  useGetDocument,
  useGetDocumentsWithPage,
  useGetSegmentsWithPage,
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

type DocumentsPageResponse = {
  data: {
    paginator: { current_page: number; page_size: number; total_page: number; total_record: number }
    list: { id: string }[]
  }
}

type DatasetsPageResponse = {
  data: {
    paginator: { current_page: number; page_size: number; total_page: number; total_record: number }
    list: { id: string }[]
  }
}

type SegmentsPageResponse = {
  data: {
    paginator: { current_page: number; page_size: number; total_page: number; total_record: number }
    list: { id: string }[]
  }
}

const createDeferred = <T,>() => {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise
  })
  return { promise, resolve }
}

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

describe('useGetDataset', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('keeps an older route response from replacing the latest dataset', async () => {
    const olderResponse = createDeferred<{ data: { id: string } }>()
    const newerResponse = createDeferred<{ data: { id: string } }>()
    mocks.getDataset.mockReturnValueOnce(olderResponse.promise).mockReturnValueOnce(newerResponse.promise)

    const { dataset, loading, loadDataset } = useGetDataset()
    const olderRequest = loadDataset('dataset-a')
    const newerRequest = loadDataset('dataset-b')

    olderResponse.resolve({ data: { id: 'dataset-a' } })
    await olderRequest
    expect(dataset.value).toEqual({})
    expect(loading.value).toBe(true)

    newerResponse.resolve({ data: { id: 'dataset-b' } })
    await newerRequest
    expect(dataset.value.id).toBe('dataset-b')
    expect(loading.value).toBe(false)
  })
})

describe('useGetDocument', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('keeps the latest document detail after overlapping requests', async () => {
    const olderResponse = createDeferred<{ data: { id: string } }>()
    const newerResponse = createDeferred<{ data: { id: string } }>()
    mocks.getDocument.mockReturnValueOnce(olderResponse.promise).mockReturnValueOnce(newerResponse.promise)

    const { document, loading, loadDocument } = useGetDocument()
    const olderRequest = loadDocument('dataset-1', 'document-a')
    const newerRequest = loadDocument('dataset-1', 'document-b')

    newerResponse.resolve({ data: { id: 'document-b' } })
    await newerRequest
    olderResponse.resolve({ data: { id: 'document-a' } })
    await olderRequest

    expect(document.value.id).toBe('document-b')
    expect(loading.value).toBe(false)
  })
})

describe('useGetDocumentsWithPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('ignores an older page response after a newer request completes', async () => {
    const olderResponse = createDeferred<DocumentsPageResponse>()
    const newerResponse = createDeferred<DocumentsPageResponse>()
    mocks.getDocumentsWithPage
      .mockReturnValueOnce(olderResponse.promise)
      .mockReturnValueOnce(newerResponse.promise)

    const { documents, loadDocuments } = useGetDocumentsWithPage()
    const olderRequest = loadDocuments('dataset-1', {
      current_page: 1,
      page_size: 20,
      search_word: 'old',
    })
    const newerRequest = loadDocuments('dataset-1', {
      current_page: 1,
      page_size: 20,
      search_word: 'new',
    })

    newerResponse.resolve({
      data: {
        paginator: { current_page: 1, page_size: 20, total_page: 1, total_record: 1 },
        list: [{ id: 'new-result' }],
      },
    })
    await newerRequest
    olderResponse.resolve({
      data: {
        paginator: { current_page: 1, page_size: 20, total_page: 1, total_record: 1 },
        list: [{ id: 'old-result' }],
      },
    })
    await olderRequest

    expect(documents.value).toEqual([{ id: 'new-result' }])
  })

  it('keeps loading while the latest page request is pending', async () => {
    const olderResponse = createDeferred<DocumentsPageResponse>()
    const newerResponse = createDeferred<DocumentsPageResponse>()
    mocks.getDocumentsWithPage
      .mockReturnValueOnce(olderResponse.promise)
      .mockReturnValueOnce(newerResponse.promise)

    const { loading, loadDocuments } = useGetDocumentsWithPage()
    const olderRequest = loadDocuments('dataset-1')
    const newerRequest = loadDocuments('dataset-1', {
      current_page: 1,
      page_size: 20,
      search_word: 'new',
    })

    olderResponse.resolve({
      data: {
        paginator: { current_page: 1, page_size: 20, total_page: 1, total_record: 1 },
        list: [{ id: 'old-result' }],
      },
    })
    await olderRequest
    expect(loading.value).toBe(true)

    newerResponse.resolve({
      data: {
        paginator: { current_page: 1, page_size: 20, total_page: 1, total_record: 1 },
        list: [{ id: 'new-result' }],
      },
    })
    await newerRequest
    expect(loading.value).toBe(false)
  })
})

describe('useGetDatasetsWithPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('ignores an older search response after a newer search completes', async () => {
    const olderResponse = createDeferred<DatasetsPageResponse>()
    const newerResponse = createDeferred<DatasetsPageResponse>()
    mocks.getDatasetsWithPage
      .mockReturnValueOnce(olderResponse.promise)
      .mockReturnValueOnce(newerResponse.promise)

    const { datasets, loadDatasets } = useGetDatasetsWithPage()
    const olderRequest = loadDatasets(true, 'old')
    const newerRequest = loadDatasets(true, 'new')

    newerResponse.resolve({
      data: {
        paginator: { current_page: 1, page_size: 20, total_page: 1, total_record: 1 },
        list: [{ id: 'new-result' }],
      },
    })
    await newerRequest
    olderResponse.resolve({
      data: {
        paginator: { current_page: 1, page_size: 20, total_page: 1, total_record: 1 },
        list: [{ id: 'old-result' }],
      },
    })
    await olderRequest

    expect(datasets.value).toEqual([{ id: 'new-result' }])
  })

  it('keeps loading while the latest search is pending', async () => {
    const olderResponse = createDeferred<DatasetsPageResponse>()
    const newerResponse = createDeferred<DatasetsPageResponse>()
    mocks.getDatasetsWithPage
      .mockReturnValueOnce(olderResponse.promise)
      .mockReturnValueOnce(newerResponse.promise)

    const { loading, loadDatasets } = useGetDatasetsWithPage()
    const olderRequest = loadDatasets(true, 'old')
    const newerRequest = loadDatasets(true, 'new')

    olderResponse.resolve({
      data: {
        paginator: { current_page: 1, page_size: 20, total_page: 1, total_record: 1 },
        list: [{ id: 'old-result' }],
      },
    })
    await olderRequest

    expect(loading.value).toBe(true)

    newerResponse.resolve({
      data: {
        paginator: { current_page: 1, page_size: 20, total_page: 1, total_record: 1 },
        list: [{ id: 'new-result' }],
      },
    })
    await newerRequest

    expect(loading.value).toBe(false)
  })
})

describe('useGetSegmentsWithPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('ignores an older segment search response after the latest request completes', async () => {
    const olderResponse = createDeferred<SegmentsPageResponse>()
    const newerResponse = createDeferred<SegmentsPageResponse>()
    mocks.getSegmentsWithPage
      .mockReturnValueOnce(olderResponse.promise)
      .mockReturnValueOnce(newerResponse.promise)

    const { segments, loadSegments } = useGetSegmentsWithPage()
    const olderRequest = loadSegments('dataset-1', 'document-1', true, 'old')
    const newerRequest = loadSegments('dataset-1', 'document-1', true, 'new')

    newerResponse.resolve({
      data: {
        paginator: { current_page: 1, page_size: 20, total_page: 1, total_record: 1 },
        list: [{ id: 'new-result' }],
      },
    })
    await newerRequest
    olderResponse.resolve({
      data: {
        paginator: { current_page: 1, page_size: 20, total_page: 1, total_record: 1 },
        list: [{ id: 'old-result' }],
      },
    })
    await olderRequest

    expect(segments.value).toEqual([{ id: 'new-result' }])
  })

  it('keeps loading while the latest segment request is pending', async () => {
    const olderResponse = createDeferred<SegmentsPageResponse>()
    const newerResponse = createDeferred<SegmentsPageResponse>()
    mocks.getSegmentsWithPage
      .mockReturnValueOnce(olderResponse.promise)
      .mockReturnValueOnce(newerResponse.promise)

    const { loading, loadSegments } = useGetSegmentsWithPage()
    const olderRequest = loadSegments('dataset-1', 'document-1', true, 'old')
    const newerRequest = loadSegments('dataset-1', 'document-1', true, 'new')

    olderResponse.resolve({
      data: {
        paginator: { current_page: 1, page_size: 20, total_page: 1, total_record: 1 },
        list: [{ id: 'old-result' }],
      },
    })
    await olderRequest
    expect(loading.value).toBe(true)

    newerResponse.resolve({
      data: {
        paginator: { current_page: 1, page_size: 20, total_page: 1, total_record: 1 },
        list: [{ id: 'new-result' }],
      },
    })
    await newerRequest
    expect(loading.value).toBe(false)
  })
})
