<template>
  <img :src="imageUrl" :alt="alt" :width="size" :height="size" :class="className" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import openagentFull from '@/assets/images/openagent.png'
import openagentCharacter from '@/assets/images/openagent_character.png'
import openagentMini from '@/assets/images/openagent_mini.png'

interface Props {
  type?: 'character' | 'mini' | 'full'
  size?: number
  className?: string
}

const props = withDefaults(defineProps<Props>(), {
  type: 'full',
  size: 24,
  className: '',
})

const imageUrl = computed(() => {
  switch (props.type) {
    case 'character':
      return openagentCharacter
    case 'mini':
      return openagentMini
    case 'full':
    default:
      return openagentFull
  }
})

const alt = computed(() => {
  switch (props.type) {
    case 'character':
      return 'OpenAgent Character'
    case 'mini':
      return 'OpenAgent Mini'
    case 'full':
    default:
      return 'OpenAgent'
  }
})
</script>

