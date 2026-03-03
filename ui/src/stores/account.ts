import { ref } from 'vue'
import { defineStore } from 'pinia'
import storage from '@/utils/storage'

// 定义账号初始化数据
const initAccount = {
  id: '',
  name: '',
  email: '',
  avatar: '',
  last_login_ip: '',
  last_login_at: 0,
  created_at: 0,
}

export const useAccountStore = defineStore('account', () => {
  const account = ref(storage.get('account', initAccount))

  const update = (params: any) => {
    account.value = params
    storage.set('account', params)
  }

  const clear = () => {
    account.value = initAccount
    storage.remove('account')
  }

  return { account, update, clear }
})
