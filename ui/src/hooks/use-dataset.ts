import { ref } from 'vue'
import {
  createDataset,
  createDocuments,
  createSegment,
  deleteDataset,
  deleteDocument,
  deleteSegment,
  generateIconPreview,
  getDataset,
  getDatasetQueries,
  getDatasetsWithPage,
  getDocument,
  getDocumentsStatus,
  getDocumentsWithPage,
  getSegment,
  getSegmentsWithPage,
  hit,
  regenerateIcon,
  updateDataset,
  updateDocumentEnabled,
  updateDocumentName,
  updateSegment,
  updateSegmentEnabled,
} from '@/services/dataset'
import { Form, Message, Modal } from '@arco-design/web-vue'
import type {
  CreateDocumentsRequest,
  CreateSegmentRequest,
  GetDocumentsWithPageRequest,
  HitRequest,
  UpdateSegmentRequest,
} from '@/models/dataset'
import { getErrorMessage } from '@/utils/error'

export const useGetDatasetsWithPage = () => {
  // 1.定义数据，涵盖数据是否加载，知识库列表以及分页器
  const loading = ref(false)
  const datasets = ref<Record<string, any>[]>([])
  const defaultPaginator = {
    current_page: 1,
    page_size: 20,
    total_page: 0,
    total_record: 0,
  }
  const paginator = ref(defaultPaginator)

  // 2.定义加载数据的函数
  const loadDatasets = async (init: boolean = false, search_word: string = '') => {
    // 2.1 判断是否是初始化，如果是的话则先初始化分页器
    if (init) {
      paginator.value = defaultPaginator
    } else if (paginator.value.current_page > paginator.value.total_page) {
      return
    }

    // 2.2 加载更多数据并更新数据状态
    try {
      // 2.3 调用接口获取响应数据
      loading.value = true
      const resp = await getDatasetsWithPage(
        paginator.value.current_page,
        paginator.value.page_size,
        search_word,
      )
      const data = resp.data

      // 2.4 更新分页器
      paginator.value = data.paginator

      // 2.5 判断是否存在更多数据
      if (paginator.value.current_page <= paginator.value.total_page) {
        paginator.value.current_page += 1
      }

      // 2.6 追加或者是覆盖数据
      if (init) {
        datasets.value = data.list
      } else {
        datasets.value.push(...data.list)
      }
    } finally {
      loading.value = false
    }
  }

  return { loading, datasets, paginator, loadDatasets }
}

export const useDeleteDataset = () => {
  const handleDelete = (dataset_id: string, callback?: () => void) => {
    Modal.warning({
      title: '要删除知识库吗?',
      content:
        '删除知识库后，关联该知识库的应用将无法再使用该知识库，所有的提示配置和文档都将被永久删除',
      hideCancel: false,
      onOk: async () => {
        try {
          // 1.点击确定后向API接口发起请求
          const resp = await deleteDataset(dataset_id)
          Message.success(resp.message)
        } finally {
          // 2.调用callback函数指定回调功能
          callback && callback()
        }
      },
    })
  }

  return { handleDelete }
}

export const useCreateOrUpdateDataset = () => {
  // 1.定义新增和更新需要使用的数据
  const loading = ref(false)
  const defaultForm = {
    fileList: [] as any,
    icon: '',
    name: '',
    description: '',
  }
  const form = ref(defaultForm)
  const formRef = ref<InstanceType<typeof Form>>()
  const showUpdateModal = ref(false)

  // 2.定义更新showUpdateModal函数
  const updateShowUpdateModal = (new_value: boolean, callback?: () => void) => {
    showUpdateModal.value = new_value
    callback && callback()
  }

  // 3.定义表单提交函数
  const saveDataset = async (dataset_id?: string) => {
    try {
      loading.value = true
      if (dataset_id !== undefined && dataset_id !== '') {
        const resp = await updateDataset(dataset_id, {
          icon: form.value.icon,
          name: form.value.name,
          description: form.value.description,
        })
        Message.success(resp.message)
      } else {
        const resp = await createDataset({
          icon: form.value.icon,
          name: form.value.name,
          description: form.value.description,
        })
        Message.success(resp.message)
      }
    } finally {
      loading.value = false
    }
  }

  return { loading, form, formRef, saveDataset, showUpdateModal, updateShowUpdateModal }
}

export const useGetDataset = () => {
  // 1.定义获取知识库详情的数据
  const loading = ref(false)
  const dataset = ref<Record<string, any>>({})

  // 2.定义加载数据函数
  const loadDataset = async (dataset_id: string) => {
    try {
      loading.value = true
      const resp = await getDataset(dataset_id)
      dataset.value = resp.data
    } finally {
      loading.value = false
    }
  }

  return { loading, dataset, loadDataset }
}

export const useGetDocumentsWithPage = () => {
  // 1.定义获取文档列表的数据结构
  const loading = ref(false)
  const documents = ref<Record<string, any>[]>([])
  const defaultPaginator = {
    current_page: 1,
    page_size: 20,
    total_page: 0,
    total_record: 0,
  }
  const paginator = ref(defaultPaginator)

  // 2.加载文档列表数据
  const loadDocuments = async (
    dataset_id: string,
    req: GetDocumentsWithPageRequest = {
      current_page: 1,
      page_size: 20,
      search_word: '',
    },
  ) => {
    try {
      // 2.1 调用接口获取响应数据
      loading.value = true
      const resp = await getDocumentsWithPage(dataset_id, req)
      const data = resp.data

      // 2.2 对于表格式+分页器实现的分页，可以直接填充数据进行替换
      paginator.value = data.paginator
      documents.value = data.list
    } finally {
      loading.value = false
    }
  }

  return { loading, documents, paginator, loadDocuments }
}

export const useDeleteDocument = () => {
  const handleDelete = (dataset_id: string, document_id: string, callback?: () => void) => {
    Modal.warning({
      title: '要删除该文档吗?',
      content:
        '删除文档后，知识库/向量数据库将无法检索到该文档，如需暂时关闭该文档的检索，可以选择禁用功能',
      hideCancel: false,
      onOk: async () => {
        try {
          // 1.点击确定后向API接口发起请求
          const resp = await deleteDocument(dataset_id, document_id)
          Message.success(resp.message)
          callback && callback()
        } catch (error: unknown) {
          Message.error(getErrorMessage(error, '删除文档失败，请稍后重试'))
          throw error
        }
      },
    })
  }

  return { handleDelete }
}

export const useUpdateDocumentEnabled = () => {
  const handleUpdate = async (
    dataset_id: string,
    document_id: string,
    enabled: boolean,
    callback?: () => void,
  ) => {
    try {
      const resp = await updateDocumentEnabled(dataset_id, document_id, enabled)
      Message.success(resp.message)
      callback && callback()
    } catch (error: unknown) {
      Message.error(getErrorMessage(error, '更新文档状态失败，请稍后重试'))
      throw error
    }
  }

  return { handleUpdate }
}

export const useGetDocument = () => {
  // 1.定义hooks所需的基础数据
  const loading = ref(false)
  const document = ref<Record<string, any>>({})

  // 2.定义加载文档函数
  const loadDocument = async (dataset_id: string, document_id: string) => {
    try {
      loading.value = true
      const resp = await getDocument(dataset_id, document_id)
      document.value = resp.data
    } finally {
      loading.value = false
    }
  }

  return { loading, document, loadDocument }
}

export const useGetSegmentsWithPage = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)
  const segments = ref<Record<string, any>>([])
  const defaultPaginator = {
    current_page: 1,
    page_size: 20,
    total_page: 0,
    total_record: 0,
  }
  const paginator = ref(defaultPaginator)

  // 2.定义加载数据函数
  const loadSegments = async (
    dataset_id: string,
    document_id: string,
    init: boolean = false,
    search_word: string = '',
  ) => {
    // 2.1 判断是否是初始化，如果是的话则先初始化分页器
    if (init) {
      paginator.value = defaultPaginator
    } else if (paginator.value.current_page > paginator.value.total_page) {
      return
    }

    // 2.2 加载数据并更新
    try {
      // 2.3 调用接口获取响应数据
      loading.value = true
      const resp = await getSegmentsWithPage(dataset_id, document_id, {
        current_page: paginator.value.current_page,
        page_size: paginator.value.page_size,
        search_word: search_word,
      })
      const data = resp.data

      // 2.4 更新分页器
      paginator.value = data.paginator

      // 2.5 判断是否存在更多数据
      if (paginator.value.current_page <= paginator.value.total_page) {
        paginator.value.current_page += 1
      }

      // 2.6 追加或者是覆盖数据
      if (init) {
        segments.value = data.list
      } else {
        segments.value.push(...data.list)
      }
    } finally {
      loading.value = false
    }
  }

  return { loading, segments, paginator, loadSegments }
}

export const useDeleteSegment = () => {
  const handleDelete = async (
    dataset_id: string,
    document_id: string,
    segment_id: string,
    callback?: () => void,
  ) => {
    Modal.warning({
      title: '要删除该文档片段吗?',
      content:
        '删除文档文档后，知识库/向量数据库将无法检索到该文档，如需暂时关闭该文档的检索，可以选择禁用功能。',
      hideCancel: false,
      onOk: async () => {
        try {
          // 1.点击确定后向API接口发起请求
          const resp = await deleteSegment(dataset_id, document_id, segment_id)
          Message.success(resp.message)
          callback && callback()
        } catch (error: unknown) {
          Message.error(getErrorMessage(error, '删除文档片段失败，请稍后重试'))
          throw error
        }
      },
    })
  }

  return { handleDelete }
}

export const useUpdateSegmentEnabled = () => {
  const handleUpdate = async (
    dataset_id: string,
    document_id: string,
    segment_id: string,
    enabled: boolean,
    callback?: () => void,
  ) => {
    try {
      const resp = await updateSegmentEnabled(dataset_id, document_id, segment_id, enabled)
      Message.success(resp.message)
      callback && callback()
    } catch (error: unknown) {
      Message.error(getErrorMessage(error, '更新文档片段状态失败，请稍后重试'))
      throw error
    }
  }

  return { handleUpdate }
}

export const useGetDatasetQueries = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)
  const queries = ref<Record<string, any>[]>([])

  // 2.定义加载数据函数
  const loadDatasetQueries = async (dataset_id: string) => {
    try {
      loading.value = true
      const resp = await getDatasetQueries(dataset_id)
      queries.value = resp.data
    } finally {
      loading.value = false
    }
  }

  return { loading, queries, loadDatasetQueries }
}

export const useHit = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)
  const hits = ref<Record<string, any>[]>([])

  // 2.定义召回测试处理器
  const handleHit = async (dataset_id: string, req: HitRequest) => {
    try {
      loading.value = true
      const resp = await hit(dataset_id, req)
      hits.value = resp.data
    } finally {
      loading.value = false
    }
  }

  return { loading, hits, handleHit }
}

export const useCreateSegment = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)

  // 2.定义新增片段处理器
  const handleCreateSegment = async (
    dataset_id: string,
    document_id: string,
    req: CreateSegmentRequest,
  ) => {
    try {
      loading.value = true
      const resp = await createSegment(dataset_id, document_id, req)
      Message.success(resp.message)
    } finally {
      loading.value = false
    }
  }

  return { loading, handleCreateSegment }
}

export const useUpdateSegment = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)

  // 2.定义更新片段处理器
  const handleUpdateSegment = async (
    dataset_id: string,
    document_id: string,
    segment_id: string,
    req: UpdateSegmentRequest,
  ) => {
    try {
      loading.value = true
      const resp = await updateSegment(dataset_id, document_id, segment_id, req)
      Message.success(resp.message)
    } finally {
      loading.value = false
    }
  }

  return { loading, handleUpdateSegment }
}

export const useGetSegment = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)
  const segment = ref<Record<string, any>>({})

  // 2.定义加载数据处理器
  const loadSegment = async (dataset_id: string, document_id: string, segment_id: string) => {
    try {
      loading.value = true
      const resp = await getSegment(dataset_id, document_id, segment_id)
      segment.value = resp.data
    } finally {
      loading.value = false
    }
  }

  return { loading, segment, loadSegment }
}

export const useCreateDocuments = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)
  const create_documents_result = ref<Record<string, any>>({})

  // 2.定义创建文档列表处理器
  const handleCreateDocuments = async (dataset_id: string, req: CreateDocumentsRequest) => {
    try {
      loading.value = true
      const resp = await createDocuments(dataset_id, req)
      create_documents_result.value = resp.data
    } finally {
      loading.value = false
    }
  }

  return { loading, create_documents_result, handleCreateDocuments }
}

export const useGetDocumentsStatus = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)
  const documents_status_result = ref<Record<string, any>[]>([])

  // 2.定义加载数据函数
  const loadDocumentsStatus = async (dataset_id: string, batch: string) => {
    try {
      loading.value = true
      const resp = await getDocumentsStatus(dataset_id, batch)
      documents_status_result.value = resp.data
    } finally {
      loading.value = false
    }
  }

  return { loading, documents_status_result, loadDocumentsStatus }
}

export const useUpdateDocumentName = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)

  // 2.定义更新文档名字处理器
  const handleUpdateDocumentName = async (
    dataset_id: string,
    document_id: string,
    name: string,
  ) => {
    try {
      loading.value = true
      const resp = await updateDocumentName(dataset_id, document_id, name)
      Message.success(resp.message)
    } catch (error: unknown) {
      Message.error(getErrorMessage(error, '重命名文档失败，请稍后重试'))
      throw error
    } finally {
      loading.value = false
    }
  }

  return { loading, handleUpdateDocumentName }
}

export const useRegenerateIcon = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)
  const icon = ref<string>('')

  // 2.定义重新生成图标函数
  const handleRegenerateIcon = async (dataset_id: string) => {
    try {
      loading.value = true
      const resp = await regenerateIcon(dataset_id)
      icon.value = resp.data.icon
      return resp.data.icon
    } catch (error: unknown) {
      let errorMessage = '重新生成图标失败，请稍后重试'
      const normalizedMessage = getErrorMessage(error, '')
      if (normalizedMessage.includes('API_KEY')) {
        errorMessage = '图标生成服务暂时不可用，请联系管理员配置 API Key'
      }
      Message.error(errorMessage)
      throw error
    } finally {
      loading.value = false
    }
  }

  return { loading, icon, handleRegenerateIcon }
}

export const useGenerateIconPreview = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)
  const icon = ref<string>('')

  // 2.定义生成图标预览函数
  const handleGenerateIconPreview = async (name: string, description: string) => {
    try {
      loading.value = true
      const resp = await generateIconPreview(name, description)
      icon.value = resp.data.icon
      return resp.data.icon
    } catch (error: unknown) {
      Message.error(getErrorMessage(error, '生成图标失败，请稍后重试或手动上传图标'))
      throw error
    } finally {
      loading.value = false
    }
  }

  return { loading, icon, handleGenerateIconPreview }
}
