<script setup lang="ts">
import { useRoute } from 'vue-router'

const route = useRoute()
</script>

<template>
  <router-view v-slot="{ Component }">
    <component
      :is="Component"
      :key="route.name === 'web-apps-index' ? String(route.params.token) : undefined"
    />
  </router-view>
</template>

<style scoped></style>
