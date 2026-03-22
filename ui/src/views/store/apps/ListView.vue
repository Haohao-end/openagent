<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  useAddBuiltinAppToSpace,
  useGetBuiltinAppCategories,
  useGetBuiltinApps,
} from '@/hooks/use-builtin-app'
import { formatTimestampShort } from '@/utils/time-formatter'

// 1.定义页面所需数据
const category = ref('all')
const search_word = ref('')
const { categories, loadBuiltinAppCategories } = useGetBuiltinAppCategories()
const { loading: getBuiltinAppsLoading, apps, loadBuiltinApps } = useGetBuiltinApps()
const { handleAddBuiltinAppToSpace } = useAddBuiltinAppToSpace()
const filterApps = computed(() => {
  return apps.value.filter((item) => {
    // 分别检索分类信息+搜索词，只有同时符合的时候才返回数据
    const matchCategory = category.value === 'all' || item.category === category.value
    const matchSearchWord =
      search_word.value === '' || item.name.toLowerCase().includes(search_word.value)

    return matchCategory && matchSearchWord
  })
})

onMounted(() => {
  loadBuiltinAppCategories()
  loadBuiltinApps()
})
</script>

<template>
  <a-spin :loading="getBuiltinAppsLoading" class="block h-full w-full">
    <div class="p-6 flex flex-col">
      <!-- 顶层标题 -->
      <div class="flex items-center justify-between mb-6">
        <!-- 左侧标题 -->
        <div class="flex items-center gap-2">
          <a-avatar :size="32" class="bg-blue-700">
            <icon-common :size="18" />
          </a-avatar>
          <div class="text-lg font-medium text-gray-900">应用广场</div>
        </div>
      </div>
      <!-- 应用分类+搜索框 -->
      <div class="flex items-center justify-between mb-6">
        <!-- 左侧分类 -->
        <div class="flex items-center gap-2">
          <a-button
            :type="category === 'all' ? 'secondary' : 'text'"
            class="rounded-lg !text-gray-700 px-3"
            @click="category = 'all'"
          >
            全部
          </a-button>
          <a-button
            v-for="item in categories"
            :key="item.category"
            :type="category === item.category ? 'secondary' : 'text'"
            class="rounded-lg !text-gray-700 px-3"
            @click="category = item.category"
          >
            {{ item.name }}
          </a-button>
        </div>
        <!-- 右侧搜索 -->
        <a-input-search
          v-model="search_word"
          placeholder="请输入应用名称"
          class="w-[240px] bg-white rounded-lg border-gray-300"
        />
      </div>
      <!-- 底部应用列表 -->
      <a-row :gutter="[20, 20]" class="flex-1">
        <!-- 有数据的UI状态 -->
        <a-col v-for="app in filterApps" :key="app.id" :span="6">
          <a-card hoverable class="cursor-pointer rounded-lg">
            <!-- 顶部应用名称 -->
            <div class="flex items-center gap-3 mb-3">
              <!-- 左侧图标 -->
              <a-avatar :size="40" shape="square" :image-url="app.icon" />
              <!-- 右侧App信息 -->
              <div class="flex flex-1 justify-between">
                <div class="flex flex-col">
                  <div class="text-base text-gray-900 font-bold">{{ app.name }}</div>
                  <div class="text-xs text-gray-500 line-clamp-1">
                    {{ app.model_config.provider }} · {{ app.model_config.model }}
                  </div>
                </div>
                <!-- 操作按钮 -->
                <a-dropdown position="br">
                  <a-button type="text" size="small" class="rounded-lg !text-gray-700">
                    <template #icon>
                      <icon-more />
                    </template>
                  </a-button>
                  <template #content>
                    <a-doption @click="async () => await handleAddBuiltinAppToSpace(app.id)">
                      添加到工作区
                    </a-doption>
                  </template>
                </a-dropdown>
              </div>
            </div>
            <!-- App的描述信息 -->
            <div class="leading-[18px] text-gray-500 h-[72px] line-clamp-4 mb-2 break-all">
              {{ app.description }}
            </div>
            <!-- 应用的归属者信息 -->
            <div class="flex items-center gap-1.5">
              <a-avatar :size="18" class="bg-blue-700">
                <icon-user />
              </a-avatar>
              <div class="text-xs text-gray-400">
                发布时间
                {{ formatTimestampShort(app.created_at) }}
              </div>
            </div>
          </a-card>
        </a-col>
        <!-- 没数据的UI状态 -->
        <a-col v-if="filterApps.length === 0" :span="24">
          <a-empty
            description="没有可用的内置Agent智能体"
            class="h-[400px] flex flex-col items-center justify-center"
          />
        </a-col>
      </a-row>
    </div>
  </a-spin>
</template>

<style scoped></style>
