<template>
  <n-layout has-sider class="min-h-screen bg-[#f5f6fb]">
    <n-layout-sider
      bordered
      collapse-mode="width"
      :collapsed="collapsed"
      :collapsed-width="72"
      :width="220"
      class="bg-white"
    >
      <div class="flex h-16 items-center gap-3 border-b border-slate-100 px-5">
        <div class="grid size-9 place-items-center rounded-xl bg-red-500 font-bold text-white">U</div>
        <span v-if="!collapsed" class="text-lg font-semibold text-red-500">utools-main</span>
      </div>
      <n-menu :value="$route.path" :collapsed="collapsed" :collapsed-width="72" :options="menuOptions" @update:value="handleMenuSelect" />
    </n-layout-sider>

    <n-layout>
      <n-layout-header bordered class="flex h-16 items-center justify-between bg-white px-5">
        <div class="flex items-center gap-4">
          <n-button quaternary circle @click="collapsed = !collapsed">
            <template #icon>
              <Icon icon="material-symbols:menu" />
            </template>
          </n-button>
          <div class="flex items-center gap-2 text-base text-slate-600">
            <Icon :icon="currentMeta.icon" class="text-xl" />
            <span>{{ currentMeta.group }}</span>
            <span class="text-slate-300">/</span>
            <span class="font-medium text-slate-900">{{ currentMeta.label }}</span>
          </div>
        </div>

        <n-dropdown :options="userOptions" @select="handleUserAction">
          <button class="flex items-center gap-3 rounded-full px-2 py-1 hover:bg-slate-100">
            <n-avatar round :size="36" color="#ef4444">{{ avatarText }}</n-avatar>
            <span class="font-medium text-slate-700">{{ auth.username || 'admin' }}</span>
          </button>
        </n-dropdown>
      </n-layout-header>

      <n-layout-content class="min-h-[calc(100vh-64px)] bg-[#f5f6fb] p-6">
        <router-view />
      </n-layout-content>
    </n-layout>
  </n-layout>
</template>

<script setup lang="ts">
import { Icon } from '@iconify/vue'
import { computed, h, onMounted, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { NAvatar, NButton, NDropdown, NLayout, NLayoutContent, NLayoutHeader, NLayoutSider, NMenu } from 'naive-ui'

import { api } from '../api'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const collapsed = ref(false)

const menuOptions = [
  {
    label: '工作台',
    key: 'dashboard',
    icon: () => h(Icon, { icon: 'material-symbols:monitor-outline' }),
    children: [
      {
        label: () => h(RouterLink, { to: '/fund/etf' }, { default: () => '基金/ETF 监控' }),
        key: '/fund/etf',
        icon: () => h(Icon, { icon: 'material-symbols:query-stats' }),
      },
    ],
  },
  {
    label: '系统管理',
    key: 'system',
    icon: () => h(Icon, { icon: 'material-symbols:settings-outline' }),
    children: [
      {
        label: () => h(RouterLink, { to: '/system/user' }, { default: () => '用户管理' }),
        key: '/system/user',
        icon: () => h(Icon, { icon: 'material-symbols:person-outline' }),
      },
      {
        label: () => h(RouterLink, { to: '/system/role' }, { default: () => '角色管理' }),
        key: '/system/role',
        icon: () => h(Icon, { icon: 'material-symbols:group-outline' }),
      },
    ],
  },
  {
    label: () => h(RouterLink, { to: '/account/profile' }, { default: () => '个人中心' }),
    key: '/account/profile',
    icon: () => h(Icon, { icon: 'material-symbols:account-circle-outline' }),
  },
]

const routeMeta: Record<string, { group: string; label: string; icon: string }> = {
  '/system/user': { group: '系统管理', label: '用户管理', icon: 'material-symbols:person-outline' },
  '/system/role': { group: '系统管理', label: '角色管理', icon: 'material-symbols:group-outline' },
  '/fund/etf': { group: '工作台', label: '基金/ETF 监控', icon: 'material-symbols:query-stats' },
  '/account/profile': { group: '账号', label: '个人中心', icon: 'material-symbols:account-circle-outline' },
}

const currentMeta = computed(() => routeMeta[route.path] || { group: '后台管理', label: '控制台', icon: 'material-symbols:dashboard' })
const avatarText = computed(() => (auth.username || 'U').slice(0, 1).toUpperCase())
const userOptions = [
  { label: '个人中心', key: 'profile' },
  { label: '退出登录', key: 'logout' },
]

onMounted(async () => {
  if (!auth.username) {
    const res = await api.getUserInfo()
    auth.setUserInfo(res.data)
  }
})

function handleMenuSelect(key: string) {
  router.push(key)
}

function handleUserAction(key: string) {
  if (key === 'profile') {
    router.push('/account/profile')
    return
  }
  auth.logout()
  router.push('/login')
}
</script>
