<script setup lang="ts">
withDefaults(defineProps<{
  text?: string
  fallback?: string
}>(), {
  text: '',
  fallback: '暂无描述',
})
</script>

<template>
  <div class="text-sm text-gray-600 h-[60px] line-clamp-3">
    {{ text || fallback }}
  </div>
</template>

<style scoped>
.line-clamp-3 {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
