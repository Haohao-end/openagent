<template>
  <div class="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-full max-w-5xl px-4">
    <div class="flex items-center">
      <div class="relative w-1/2">
        <img class="w-full" src="@/assets/images/403.png" alt="403" />
        <img
          class="absolute left-[220px] top-[17px] h-[120px] w-[120px] animate-[cloudLeft_2s_linear_forwards] [animation-delay:1s]"
          src="@/assets/images/404_cloud.png"
          alt="cloud"
        />
        <img
          class="absolute left-[420px] top-[10px] h-[120px] w-[128px] animate-[cloudMid_2s_linear_forwards] [animation-delay:1.2s]"
          src="@/assets/images/404_cloud.png"
          alt="cloud"
        />
        <img
          class="absolute left-[500px] top-[100px] h-[120px] w-[144px] animate-[cloudRight_2s_linear_forwards] [animation-delay:1s]"
          src="@/assets/images/404_cloud.png"
          alt="cloud"
        />
      </div>

      <div class="w-1/2 pl-8 space-y-4">
        <div class="animate-[slideUp_0.5s_ease-out_forwards] text-3xl font-bold text-blue-500 opacity-0">OOPS!</div>
        <div class="animate-[slideUp_0.5s_ease-out_forwards] [animation-delay:0.1s] text-sm text-blue-400 opacity-0">
          前往
          <a
            class="text-blue-500  cursor-pointer"
            @click="goHome"
          >
            AI Agent首页
          </a>
        </div>
        <div class="animate-[slideUp_0.5s_ease-out_forwards] [animation-delay:0.2s] text-xl font-bold text-gray-400 opacity-0">
          {{ message }}
        </div>
        <div class="animate-[slideUp_0.5s_ease-out_forwards] [animation-delay:0.3s] text-sm text-gray-400 opacity-0">
          对不起 您暂时没有权限访问该页面
        </div>
        <button
          class="mt-4 animate-[slideUp_0.5s_ease-out_forwards] [animation-delay:0.5s] rounded-full bg-blue-500 px-6 py-2 text-white opacity-0"
          @click="goHome"
        >
          返回首页
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'

const router = useRouter()
const message = '您可能没有访问该页面的权限...'

function goHome() {
  router.push('/home')
}
</script>

<style scoped>
@keyframes cloudLeft {
  0% {
    top: 17px;
    left: 220px;
    opacity: 0;
  }
  20% {
    top: 33px;
    left: 188px;
    opacity: 1;
  }
  80% {
    top: 81px;
    left: 92px;
    opacity: 1;
  }
  100% {
    top: 97px;
    left: 60px;
    opacity: 0;
  }
}

@keyframes cloudMid {
  0% {
    top: 10px;
    left: 420px;
    opacity: 0;
  }
  20% {
    top: 40px;
    left: 360px;
    opacity: 1;
  }
  70% {
    top: 130px;
    left: 180px;
    opacity: 1;
  }
  100% {
    top: 160px;
    left: 120px;
    opacity: 0;
  }
}

@keyframes cloudRight {
  0% {
    top: 100px;
    left: 500px;
    opacity: 0;
  }
  20% {
    top: 120px;
    left: 460px;
    opacity: 1;
  }
  80% {
    top: 180px;
    left: 340px;
    opacity: 1;
  }
  100% {
    top: 200px;
    left: 300px;
    opacity: 0;
  }
}

@keyframes slideUp {
  0% {
    transform: translateY(60px);
    opacity: 0;
  }
  100% {
    transform: translateY(0);
    opacity: 1;
  }
}
</style>
