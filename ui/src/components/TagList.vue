<script setup lang="ts">
import { computed } from 'vue'
import type { AppTags } from '@/services/tag'

type DisplayTag = {
  dimension: string
  name: string
}

interface Props {
  tags?: AppTags | Record<string, string | string[] | null | undefined>
  maxDisplay?: number
}

const props = withDefaults(defineProps<Props>(), {
  tags: () => ({}),
  maxDisplay: 3,
})

const dimensionPriority: Record<string, number> = {
  scene: 0,
  ability: 1,
  tech: 2,
  industry: 3,
}

const dimensionClassMap: Record<string, string> = {
  scene: 'tag-item--scene',
  ability: 'tag-item--ability',
  tech: 'tag-item--tech',
  industry: 'tag-item--industry',
}

const normalizeTagValues = (value: string | string[] | null | undefined): string[] => {
  if (Array.isArray(value)) return value
  if (typeof value === 'string') return [value]
  return []
}

const allTags = computed<DisplayTag[]>(() => {
  const seen = new Set<string>()

  return Object.entries(props.tags ?? {})
    .sort(([leftDimension], [rightDimension]) => {
      const leftPriority = dimensionPriority[leftDimension] ?? Number.MAX_SAFE_INTEGER
      const rightPriority = dimensionPriority[rightDimension] ?? Number.MAX_SAFE_INTEGER

      if (leftPriority !== rightPriority) return leftPriority - rightPriority
      return leftDimension.localeCompare(rightDimension, 'zh-CN')
    })
    .flatMap(([dimension, values]) =>
      normalizeTagValues(values).flatMap((value) => {
        const name = value.trim()
        if (!name || seen.has(name)) return []
        seen.add(name)
        return [{ dimension, name }]
      }),
    )
})

const visibleTags = computed(() => {
  if (props.maxDisplay <= 0) return []
  return allTags.value.slice(0, props.maxDisplay)
})

const tooltipText = computed(() => allTags.value.map((tag) => tag.name).join(' / '))

const getTagClass = (dimension: string) => dimensionClassMap[dimension] ?? 'tag-item--default'
</script>

<template>
  <div v-if="visibleTags.length > 0" class="tag-list" :title="tooltipText">
    <span
      v-for="tag in visibleTags"
      :key="`${tag.dimension}-${tag.name}`"
      class="tag-item"
      :class="getTagClass(tag.dimension)"
    >
      {{ tag.name }}
    </span>
  </div>
</template>

<style scoped>
.tag-list {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.tag-item {
  display: inline-flex;
  align-items: center;
  max-width: 100%;
  padding: 0 8px;
  height: 20px;
  border-radius: 9999px;
  border: 1px solid transparent;
  font-size: 12px;
  line-height: 20px;
  white-space: nowrap;
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease,
    background-color 0.2s ease;
}

.tag-item:hover {
  transform: translateY(-1px);
}

.tag-item--scene {
  background: #eff6ff;
  border-color: #dbeafe;
  color: #1d4ed8;
}

.tag-item--ability {
  background: #ecfdf5;
  border-color: #d1fae5;
  color: #047857;
}

.tag-item--tech {
  background: #f8fafc;
  border-color: #e2e8f0;
  color: #334155;
}

.tag-item--industry {
  background: #fffbeb;
  border-color: #fde68a;
  color: #b45309;
}

.tag-item--default {
  background: #f9fafb;
  border-color: #e5e7eb;
  color: #4b5563;
}
</style>
