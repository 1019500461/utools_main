<template>
  <main class="min-h-screen bg-[radial-gradient(circle_at_top_left,#dbeafe,transparent_32%),linear-gradient(135deg,#f8fafc,#e2e8f0)]">
    <div class="mx-auto grid min-h-screen max-w-6xl place-items-center px-6 py-10">
      <section class="grid w-full max-w-4xl overflow-hidden rounded-lg bg-white/85 shadow-xl ring-1 ring-slate-200 md:grid-cols-[1.1fr_0.9fr]">
        <div class="hidden bg-slate-950 p-10 text-white md:block">
          <div class="flex h-full flex-col justify-between">
            <div>
              <p class="text-sm text-sky-300">utools-main</p>
              <h1 class="mt-4 text-3xl font-semibold">后台管理系统</h1>
              <p class="mt-4 text-sm leading-6 text-slate-300">
                复现参考项目的登录与角色管理核心流程，连接 PostgreSQL 后即可使用。
              </p>
            </div>
            <div class="rounded-md border border-white/10 bg-white/5 p-4 text-sm text-slate-300">
              默认账号：admin<br />
              默认密码：123456
            </div>
          </div>
        </div>

        <div class="p-8 md:p-10">
          <h2 class="text-2xl font-semibold text-slate-900">登录</h2>
          <p class="mt-2 text-sm text-slate-500">请输入管理员账号进入角色管理。</p>

          <n-form class="mt-8" :model="form" @submit.prevent="handleLogin">
            <n-form-item label="用户名">
              <n-input v-model:value="form.username" size="large" placeholder="admin" autofocus />
            </n-form-item>
            <n-form-item label="密码">
              <n-input
                v-model:value="form.password"
                size="large"
                type="password"
                show-password-on="mousedown"
                placeholder="123456"
                @keyup.enter="handleLogin"
              />
            </n-form-item>
            <n-button class="mt-2" type="primary" size="large" block :loading="loading" @click="handleLogin">
              登录
            </n-button>
          </n-form>
        </div>
      </section>
    </div>
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
    message.success('登录成功')
    router.push((route.query.redirect as string) || '/system/role')
  } finally {
    loading.value = false
  }
}
</script>
