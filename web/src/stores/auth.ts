import { defineStore } from 'pinia'

const TOKEN_KEY = 'utools-main-token'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem(TOKEN_KEY) || '',
    username: '',
    email: '',
    isSuperuser: false,
  }),
  actions: {
    setToken(token: string) {
      this.token = token
      localStorage.setItem(TOKEN_KEY, token)
    },
    setUsername(username: string) {
      this.username = username
    },
    setUserInfo(user: { username?: string; email?: string; is_superuser?: boolean }) {
      this.username = user.username || this.username
      this.email = user.email || ''
      this.isSuperuser = Boolean(user.is_superuser)
    },
    logout() {
      this.token = ''
      this.username = ''
      this.email = ''
      this.isSuperuser = false
      localStorage.removeItem(TOKEN_KEY)
    },
  },
})
