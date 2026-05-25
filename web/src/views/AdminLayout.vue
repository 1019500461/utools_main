<template>
  <n-layout class="min-h-screen">
    <n-layout-header bordered class="flex h-14 items-center justify-between px-5">
      <div class="flex items-center gap-3">
        <div class="grid size-8 place-items-center rounded bg-slate-900 text-sm font-semibold text-white">U</div>
        <div>
          <p class="text-sm font-semibold text-slate-900">utools-main</p>
          <p class="text-xs text-slate-500">后台管理</p>
        </div>
      </div>
      <n-button secondary @click="handleLogout">退出登录</n-button>
    </n-layout-header>

    <n-layout has-sider class="min-h-[calc(100vh-56px)]">
      <n-layout-sider bordered :width="220" class="bg-white">
        <n-menu :value="$route.path" :options="menuOptions" @update:value="handleMenuSelect" />
      </n-layout-sider>
      <n-layout-content class="bg-slate-50 p-6">
        <router-view />
      </n-layout-content>
    </n-layout>
  </n-layout>
</template>

<script setup lang="ts">
import { h } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { NButton, NLayout, NLayoutContent, NLayoutHeader, NLayoutSider, NMenu } from 'naive-ui'

import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const menuOptions = [
  {
    label: () => h(RouterLink, { to: '/system/role' }, { default: () => '角色管理' }),
    key: '/system/role',
  },
  {
    label: () => h(RouterLink, { to: '/fund/etf' }, { default: () => '基金/ETF 监控' }),
    key: '/fund/etf',
  },
]

function handleMenuSelect(key: string) {
  router.push(key)
}

function handleLogout() {
  auth.logout()
  router.push('/login')
}
</script>
