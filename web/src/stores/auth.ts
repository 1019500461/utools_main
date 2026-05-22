import { defineStore } from 'pinia'

const TOKEN_KEY = 'utools-main-token'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem(TOKEN_KEY) || '',
    username: '',
  }),
  actions: {
    setToken(token: string) {
      this.token = token
      localStorage.setItem(TOKEN_KEY, token)
    },
    setUsername(username: string) {
      this.username = username
    },
    logout() {
      this.token = ''
      this.username = ''
      localStorage.removeItem(TOKEN_KEY)
    },
  },
})
