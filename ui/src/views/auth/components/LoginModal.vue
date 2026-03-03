<script setup lang="ts">
import LoginForm from './LoginForm.vue'

const props = defineProps({
  visible: { type: Boolean, required: true },
})

const emits = defineEmits(['update:visible', 'success'])

const handleCancel = () => emits('update:visible', false)

const handleSuccess = () => {
  emits('update:visible', false)
  emits('success')
}
</script>

<template>
  <a-modal
    :visible="props.visible"
    :footer="false"
    hide-title
    :width="560"
    :closable="false"
    :mask-closable="true"
    modal-class="rounded-xl overflow-hidden"
    unmount-on-close
    @cancel="handleCancel"
  >
    <login-form :embedded="true" :redirect-after-login="false" @success="handleSuccess" />
  </a-modal>
</template>

<style scoped></style>
