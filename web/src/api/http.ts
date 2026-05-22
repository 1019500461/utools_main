import axios from 'axios'
import { createDiscreteApi } from 'naive-ui'

import { router } from '../router'
import { useAuthStore } from '../stores/auth'

const { message } = createDiscreteApi(['message'])

export const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 15000,
})

http.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.token) {
    config.headers.Authorization = `Bearer ${auth.token}`
  }
  return config
})

http.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const status = error.response?.status
    const detail = error.response?.data?.detail
    const msg = typeof detail === 'string' ? detail : error.response?.data?.msg || '请求失败'

    if (status === 401) {
      useAuthStore().logout()
      router.push('/login')
    }
    message.error(msg)
    return Promise.reject(error)
  }
)
