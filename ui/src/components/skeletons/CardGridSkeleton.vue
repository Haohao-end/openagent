<script setup lang="ts">
const props = defineProps({
  count: { type: Number, default: 8, required: false },
})
</script>

<template>
  <a-row :gutter="[20, 20]" class="flex-1">
    <a-col v-for="idx in props.count" :key="idx" :span="6">
      <div class="rounded-lg border border-gray-200 bg-white p-4">
        <div class="flex items-center gap-3 mb-4">
          <div class="skeleton-shimmer h-10 w-10 rounded-lg flex-shrink-0" />
          <div class="flex-1 flex flex-col gap-2">
            <div class="skeleton-shimmer h-4 w-28 rounded" />
            <div class="skeleton-shimmer h-3 w-24 rounded" />
          </div>
          <div class="skeleton-shimmer h-5 w-5 rounded" />
        </div>
        <div class="flex flex-col gap-2 mb-4">
          <div class="skeleton-shimmer h-3 w-full rounded" />
          <div class="skeleton-shimmer h-3 w-[92%] rounded" />
          <div class="skeleton-shimmer h-3 w-[76%] rounded" />
          <div class="skeleton-shimmer h-3 w-[85%] rounded" />
        </div>
        <div class="flex items-center gap-2">
          <div class="skeleton-shimmer h-4 w-4 rounded-full" />
          <div class="skeleton-shimmer h-3 w-32 rounded" />
        </div>
      </div>
    </a-col>
  </a-row>
</template>

<style scoped>
.skeleton-shimmer {
  position: relative;
  overflow: hidden;
  background: linear-gradient(100deg, #eef2f7 30%, #f8fbff 42%, #eef2f7 55%);
  background-size: 220% 100%;
  animation: skeleton-shimmer 1.45s ease-in-out infinite;
}

@keyframes skeleton-shimmer {
  0% {
    background-position: 100% 0;
  }
  100% {
    background-position: -100% 0;
  }
}
</style>
