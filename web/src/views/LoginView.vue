<template>
  <main class="login-shell">
    <section class="login-card">
      <div class="login-illustration" aria-hidden="true">
        <div class="board">
          <div class="board-card card-a"></div>
          <div class="board-card card-b"></div>
          <div class="board-card card-c"></div>
          <div class="person"></div>
        </div>
      </div>

      <div class="login-panel">
        <div class="mb-8 flex items-center justify-center gap-3">
          <div class="grid size-12 place-items-center rounded-2xl bg-red-500 text-xl font-bold text-white shadow-lg shadow-red-200">
            U
          </div>
          <h1 class="text-3xl font-semibold text-slate-800">utools-main</h1>
        </div>

        <n-form :model="form" @submit.prevent="handleLogin">
          <n-form-item>
            <n-input
              v-model:value="form.username"
              size="large"
              placeholder="admin"
              autofocus
              :maxlength="32"
            />
          </n-form-item>
          <n-form-item>
            <n-input
              v-model:value="form.password"
              size="large"
              type="password"
              show-password-on="mousedown"
              placeholder="123456"
              :maxlength="128"
              @keyup.enter="handleLogin"
            />
          </n-form-item>
          <n-button class="mt-2 h-12 text-base" type="error" size="large" block :loading="loading" @click="handleLogin">
            登录
          </n-button>
        </n-form>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NButton, NForm, NFormItem, NInput, useMessage } from 'naive-ui'

import { api } from '../api'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const message = useMessage()
const loading = ref(false)
const form = reactive({
  username: 'admin',
  password: '123456',
})

async function handleLogin() {
  if (!form.username || !form.password) {
    message.warning('请输入用户名和密码')
    return
  }

  loading.value = true
  try {
    const res = await api.login({ username: form.username, password: form.password })
    auth.setToken(res.data.access_token)
    auth.setUsername(res.data.username)
    const userInfo = await api.getUserInfo()
    auth.setUserInfo(userInfo.data)
    message.success('登录成功')
    router.push((route.query.redirect as string) || '/system/user')
  } finally {
    loading.value = false
  }
}
</script>
