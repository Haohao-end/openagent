import { ref } from 'vue'
import { getCurrentUser, updateAvatar, updateName, updatePassword } from '@/services/account'
import { Message } from '@arco-design/web-vue'

export const useGetCurrentUser = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)
  const current_user = ref<Record<string, any>>({})

  // 2.定义加载数据处理器
  const loadCurrentUser = async () => {
    try {
      loading.value = true
      const resp = await getCurrentUser()
      current_user.value = resp.data
    } finally {
      loading.value = false
    }
  }

  return { loading, current_user, loadCurrentUser }
}

export const useUpdateAvatar = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)

  // 2.定义更新头像处理器
  const handleUpdateAvatar = async (avatar: string) => {
    try {
      loading.value = true
      const resp = await updateAvatar(avatar)
      Message.success(resp.message)
    } finally {
      loading.value = false
    }
  }

  return { loading, handleUpdateAvatar }
}

export const useUpdateName = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)

  // 2.定义更新名字处理器
  const handleUpdateName = async (name: string) => {
    try {
      loading.value = true
      await updateName(name)
    } finally {
      loading.value = false
    }
  }

  return { loading, handleUpdateName }
}

export const useUpdatePassword = () => {
  // 1.定义hooks所需数据
  const loading = ref(false)

  // 2.定义更新密码处理器
  const handleUpdatePassword = async (password: string) => {
    try {
      loading.value = true
      const resp = await updatePassword(password)
      Message.success(resp.message)
    } finally {
      loading.value = false
    }
  }

  return { loading, handleUpdatePassword }
}
