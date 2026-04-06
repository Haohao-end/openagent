<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
 useDeleteDocument,
 useGetDataset,
 useGetDocumentsWithPage,
 useUpdateDocumentEnabled,
} from '@/hooks/use-dataset'
import UpdateDocumentNameModal from '@/views/space/datasets/documents/components/UpdateDocumentNameModal.vue'
import HitTestingModal from '@/views/space/datasets/documents/components/HitTestingModal.vue'
import { formatTimestampLong } from '@/utils/time-formatter'

type DocumentRecord = Record<string, any>

const route = useRoute()
const router = useRouter()
const hitModalVisible = ref(false)
const updateDocumentNameModalVisible = ref(false)
const updateDocumentID = ref('')
const searchInput = ref('')
const updatingDocumentId = ref('')
const { dataset, loadDataset } = useGetDataset()
const { loading, documents, paginator, loadDocuments } = useGetDocumentsWithPage()
const { handleDelete } = useDeleteDocument()
const { handleUpdate: handleUpdateEnabled } = useUpdateDocumentEnabled()

const datasetId = computed(() => String(route.params?.dataset_id ?? ''))
const searchWord = computed(() => String(route.query?.search_word ?? ''))
const req = computed(() => {
 return {
 current_page: Number(route.query?.current_page ??1),
 page_size: Number(route.query?.page_size ??20),
 search_word: searchWord.value,
 }
})
const hasActiveSearch = computed(() => searchWord.value.trim() !== '')
const sortedDocuments = computed(() => {
 return [...documents.value].sort((left, right) => {
 const createdAtDiff = Number(right.created_at ??0) - Number(left.created_at ??0)
 if (createdAtDiff !==0) return createdAtDiff
 return String(right.id ?? '').localeCompare(String(left.id ?? ''))
 })
})

const updateRouteQuery = async (patch: Record<string, string | number | undefined>) => {
 const nextQuery = {
 ...route.query,
 ...patch,
 } as Record<string, string | number | undefined>

 Object.keys(nextQuery).forEach((key) => {
 const value = nextQuery[key]
 if (value === '' || value === undefined) {
 delete nextQuery[key]
 }
 })

 await router.push({
 path: route.path,
 query: nextQuery,
 })
}

const getProcessingStatusLabel = (status: string) => {
 const normalizedStatus = String(status || '').toLowerCase()

 if (normalizedStatus === 'completed') return '已完成'
 if (normalizedStatus === 'error') return '处理失败'
 if (['parsing', 'splitting', 'indexing', 'processing'].includes(normalizedStatus)) return '处理中'
 if (['waiting', 'pending', 'queued'].includes(normalizedStatus)) return '待处理'
 return '处理中'
}

const getProcessingStatusClass = (status: string) => {
 const normalizedStatus = String(status || '').toLowerCase()

 if (normalizedStatus === 'completed') return 'bg-emerald-50 text-emerald-700 border-emerald-200'
 if (normalizedStatus === 'error') return 'bg-red-50 text-red-700 border-red-200'
 if (['waiting', 'pending', 'queued'].includes(normalizedStatus)) {
 return 'bg-slate-100 text-slate-600 border-slate-200'
 }
 return 'bg-amber-50 text-amber-700 border-amber-200'
}

const getAvailabilityLabel = (record: DocumentRecord) => {
 if (record.status !== 'completed') return '不可切换'
 return record.enabled ? '可用' : '已禁用'
}

const getAvailabilityClass = (record: DocumentRecord) => {
 if (record.status !== 'completed') return 'bg-slate-100 text-slate-500 border-slate-200'
 if (record.enabled) return 'bg-sky-50 text-sky-700 border-sky-200'
 return 'bg-slate-100 text-slate-600 border-slate-200'
}

const handleSearch = async (value: string) => {
 await updateRouteQuery({
 search_word: value.trim(),
 current_page:1,
 page_size: req.value.page_size,
 })
}

const handlePageChange = async (page: number) => {
 await updateRouteQuery({
 current_page: page,
 page_size: req.value.page_size,
 search_word: searchWord.value || undefined,
 })
}

const handlePageSizeChange = async (pageSize: number) => {
 await updateRouteQuery({
 current_page:1,
 page_size: pageSize,
 search_word: searchWord.value || undefined,
 })
}

const handleDocumentEnabledChange = async (
 record: DocumentRecord,
 value: boolean,
) => {
 if (updatingDocumentId.value) return

 updatingDocumentId.value = String(record.id)
 try {
 await handleUpdateEnabled(datasetId.value, String(record.id), value, () => {
 const targetDocument = documents.value.find((item) => String(item.id) === String(record.id))
 if (targetDocument) {
 targetDocument.enabled = value
 }
 })
 } finally {
 updatingDocumentId.value = ''
 }
}

const getDisplayIndex = (rowIndex: number) => {
 return (req.value.current_page -1) * req.value.page_size + rowIndex +1
}

watch(
 searchWord,
 (value) => {
 searchInput.value = value
 },
 { immediate: true },
)

watch(
 datasetId,
 (value) => {
 if (!value) return
 void loadDataset(value)
 },
 { immediate: true },
)

watch(
 () => [datasetId.value, req.value.current_page, req.value.page_size, req.value.search_word] as const,
 ([value]) => {
 if (!value) return
 void loadDocuments(value, req.value)
 },
 { immediate: true },
)
</script>

<template>
 <div class="scrollbar-w-none h-full min-h-0 overflow-y-auto bg-slate-50 px-6 py-6 pb-10">
 <div
 class="flex min-h-full flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"
 >
 <div class="border-b border-slate-200 px-5 py-4">
 <div class="flex flex-col gap-2">
 <div class="flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
 <div class="flex min-w-0 items-start gap-3">
 <router-link :to="{ name: 'space-datasets-list' }">
 <a-button size="mini" type="text" class="mt-1 !text-slate-600">
 <template #icon>
 <icon-left />
 </template>
 </a-button>
 </router-link>
 <a-avatar :size="52" shape="square" class="rounded-xl" :image-url="dataset.icon" />
 <div class="min-w-0 flex-1 space-y-2">
 <a-skeleton-line v-if="!dataset?.name" :widths="[160]" />
 <div v-else class="line-clamp-1 text-xl font-semibold tracking-tight text-slate-900">
 {{ dataset.name }}
 </div>
 <div class="flex flex-wrap items-center gap-2">
 <a-tag class="!m-0 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-0.5 text-slate-600">
 {{ dataset.character_count ||0 }} 字符
 </a-tag>
 <a-tag class="!m-0 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-0.5 text-slate-600">
 {{ dataset.hit_count }} 命中
 </a-tag>
 <a-tag class="!m-0 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-0.5 text-slate-600">
 {{ dataset.related_app_count }}关联应用
 </a-tag>
 </div>
 </div>
 </div>
 <div class="flex flex-col gap-2 lg:items-end">
 <div class="flex flex-wrap items-center justify-end gap-3">
 <a-button class="rounded-xl border-slate-200 bg-white px-4 !text-slate-700" @click="hitModalVisible = true">
 召回测试
 </a-button>
 <router-link
 :to="{
 name: 'space-datasets-documents-create',
 params: { dataset_id: datasetId },
 }"
 >
 <a-button type="primary" class="rounded-xl px-4">添加文件</a-button>
 </router-link>
 </div>
 <div
 class="relative h-8 w-[220px] max-w-full self-end rounded-xl border border-slate-300 bg-white transition focus-within:border-sky-400 focus-within:shadow-sm hover:border-slate-400"
 >
  <input
  v-model="searchInput"
  type="text"
  placeholder="搜索文档"
  class="h-full w-full border-0 bg-transparent pl-3 pr-9 text-sm text-slate-700 outline-none placeholder:text-slate-400"
  @keydown.enter="handleSearch(searchInput)"
  />
  <button
  type="button"
  class="absolute right-1.5 top-1/2 inline-flex h-5 w-5 -translate-y-1/2 items-center justify-center rounded-full text-slate-500 transition hover:bg-slate-100 hover:text-sky-600"
  @click="handleSearch(searchInput)"
  >
 <svg
 class="h-4 w-4"
 viewBox="0 0 20 20"
 fill="none"
 xmlns="http://www.w3.org/2000/svg"
 aria-hidden="true"
 >
 <path
 d="M8.75 3.75a5 5 0 1 0 0 10a5 5 0 0 0 0-10Zm0-1.5a6.5 6.5 0 1 1 0 13a6.5 6.5 0 0 1 0-13Zm4.56 11.12a.75.75 0 0 1 1.06 0l2.41 2.41a.75.75 0 1 1-1.06 1.06l-2.41-2.41a.75.75 0 0 1 0-1.06Z"
 fill="currentColor"
  />
  </svg>
  </button>
 </div>
 </div>
 </div>
 </div>
 </div>

 <div class="min-h-0 flex-1 pb-4">
 <a-table
 row-key="id"
 hoverable
 :pagination="{
 total: paginator.total_record,
 current: paginator.current_page,
 defaultCurrent:1,
 pageSize: paginator.page_size,
 defaultPageSize:20,
 showTotal: true,
 showPageSize: true,
 pageSizeOptions: [10,20,50,100],
 }"
 :loading="loading"
 :data="sortedDocuments"
 :bordered="{ wrapper: false }"
 @page-change="handlePageChange"
 @page-size-change="handlePageSizeChange"
 >
 <template #columns>
 <a-table-column
 title="编号"
 data-index="position"
 align="center"
 :width="80"
 header-cell-class="!bg-slate-100 text-slate-700"
 cell-class="bg-transparent text-slate-700"
 >
 <template #cell="{ rowIndex }">
 <div class="font-mono text-sm font-semibold text-slate-500">
 {{ getDisplayIndex(rowIndex) }}
 </div>
 </template>
 </a-table-column>
 <a-table-column
 title="文档"
 data-index="name"
 align="center"
 :width="320"
 header-cell-class="!bg-slate-100 text-slate-700"
 cell-class="bg-transparent text-slate-700"
 >
  <template #cell="{ record }">
 <div class="mx-auto min-w-0 max-w-[240px] text-center">
  <router-link
  :to="{
  name: 'space-datasets-documents-segments-list',
 params: {
 dataset_id: datasetId,
 document_id: record.id as string,
 },
 }"
 class="block truncate font-medium text-slate-800 transition hover:text-sky-700"
  >
  {{ record.name }}
  </router-link>
 </div>
 </template>
 </a-table-column>
 <a-table-column
 title="字符数"
 data-index="character_count"
 align="center"
 :width="110"
 header-cell-class="!bg-slate-100 text-slate-700"
 cell-class="bg-transparent text-slate-700"
 >
 <template #cell="{ record }">
 {{ (record.character_count /1000).toFixed(1) }}k
 </template>
 </a-table-column>
<a-table-column
 title="召回次数"
 data-index="hit_count"
 align="center"
 :width="110"
 header-cell-class="!bg-slate-100 text-slate-700"
 cell-class="bg-transparent text-slate-700"
 >
 <template #cell="{ record }">
 <span class="text-sm text-slate-600">
 {{ record.hit_count === null || record.hit_count === undefined || record.hit_count === '' ? '-' : record.hit_count }}
 </span>
 </template>
 </a-table-column>
 <a-table-column
 title="处理状态"
 data-index="status"
 align="center"
 :width="140"
 header-cell-class="!bg-slate-100 text-slate-700"
 cell-class="bg-transparent text-slate-700"
 >
 <template #cell="{ record }">
 <a-tooltip v-if="record.status === 'error' && record.error" :content="record.error">
 <div
 class="mx-auto inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold"
 :class="getProcessingStatusClass(record.status)"
 >
 {{ getProcessingStatusLabel(record.status) }}
 </div>
 </a-tooltip>
 <div
 v-else
 class="mx-auto inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold"
 :class="getProcessingStatusClass(record.status)"
 >
 {{ getProcessingStatusLabel(record.status) }}
 </div>
 </template>
 </a-table-column>
 <a-table-column
 title="启用状态"
 data-index="enabled"
 align="center"
 :width="130"
 header-cell-class="!bg-slate-100 text-slate-700"
 cell-class="bg-transparent text-slate-700"
 >
 <template #cell="{ record }">
 <div
 class="mx-auto inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold"
 :class="getAvailabilityClass(record)"
 >
 {{ getAvailabilityLabel(record) }}
 </div>
 </template>
 </a-table-column>
 <a-table-column
 title="上传时间"
 data-index="created_at"
 align="center"
 :width="180"
 header-cell-class="!bg-slate-100 text-slate-700"
 cell-class="bg-transparent text-slate-700"
 >
 <template #cell="{ record }">
 <div class="text-center text-sm text-slate-600">
 {{ formatTimestampLong(record.created_at) }}
 </div>
 </template>
 </a-table-column>
 <a-table-column
 title="操作"
 data-index="operator"
 align="center"
 :width="220"
 header-cell-class="!bg-slate-100 text-slate-700"
 cell-class="bg-transparent text-slate-700"
 >
 <template #cell="{ record }">
 <div class="flex items-center justify-center gap-2">
 <button
 type="button"
 class="inline-flex h-8 items-center gap-2 rounded-full border px-1.5 pr-3 transition"
 :class="
 record.status !== 'completed'
 ? 'cursor-not-allowed border-slate-200 bg-slate-100 text-slate-400'
 : record.enabled
 ? 'border-sky-200 bg-sky-50 text-sky-700 hover:bg-sky-100'
 : 'border-slate-300 bg-white text-slate-600 hover:bg-slate-50'
 "
 :disabled="record.status !== 'completed' || updatingDocumentId === record.id"
 @click="handleDocumentEnabledChange(record, !record.enabled)"
 >
 <span
 class="relative h-5 w-9 rounded-full transition"
 :class="
 record.status !== 'completed'
 ? 'bg-slate-300'
 : record.enabled
 ? 'bg-sky-500'
 : 'bg-slate-300'
 "
 >
 <span
 class="absolute top-0.5 h-4 w-4 rounded-full bg-white shadow-sm transition"
 :class="record.enabled && record.status === 'completed' ? 'left-4' : 'left-0.5'"
 />
 </span>
 <span class="text-xs font-medium">
 {{ updatingDocumentId === record.id ? '切换中' : record.status !== 'completed' ? '不可切换' : record.enabled ? '已启用' : '已禁用' }}
 </span>
 </button>
 <a-dropdown position="br">
 <a-button type="text" size="mini" class="rounded-lg !text-slate-600">
 <template #icon>
 <icon-more />
 </template>
 </a-button>
 <template #content>
 <a-doption
 @click="
 () => {
 updateDocumentNameModalVisible = true
 updateDocumentID = record.id
 }
 "
 >
 重命名
 </a-doption>
 <a-doption
 class="!text-red-700"
 @click="
 () =>
 handleDelete(datasetId, record.id, () => {
 void loadDocuments(datasetId, req)
 void loadDataset(datasetId)
 })
 "
 >
 删除
 </a-doption>
 </template>
 </a-dropdown>
 </div>
 </template>
 </a-table-column>
 </template>

 <template #empty>
 <a-empty :description="hasActiveSearch ? '没有匹配的文档结果' : '当前知识库还没有文档'" />
 </template>
 </a-table>
 </div>
 </div>

 <update-document-name-modal
 :document_id="updateDocumentID"
 :dataset_id="datasetId"
 v-model:visible="updateDocumentNameModalVisible"
 :on-after-update="() => loadDocuments(datasetId, req)"
 />
 <hit-testing-modal v-model:visible="hitModalVisible" :dataset_id="datasetId" />
 </div>
</template>

<style scoped>
:deep(.arco-table-pagination) {
 padding: 16px 20px 20px;
}
</style>
