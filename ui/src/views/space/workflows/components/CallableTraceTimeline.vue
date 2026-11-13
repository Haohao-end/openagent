<script setup lang="ts">
import SharedCallableTraceTimeline from '@/components/chat/CallableTraceTimeline.vue'

defineProps<{ events: unknown[] }>()
</script>

<template>
  <SharedCallableTraceTimeline :events="events" />
</template>
