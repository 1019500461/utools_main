import { createRouter, createWebHistory } from 'vue-router'

import { useAuthStore } from './stores/auth'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      redirect: '/fund/etf',
    },
    {
      path: '/login',
      component: () => import('./views/LoginView.vue'),
      meta: { public: true },
    },
    {
      path: '/system',
      component: () => import('./views/AdminLayout.vue'),
      children: [
        {
          path: 'role',
          component: () => import('./views/RoleManageView.vue'),
        },
      ],
    },
    {
      path: '/account',
      component: () => import('./views/AdminLayout.vue'),
      children: [
        {
          path: 'profile',
          component: () => import('./views/ProfileView.vue'),
        },
      ],
    },
    {
      path: '/fund',
      component: () => import('./views/AdminLayout.vue'),
      children: [
        {
          path: 'etf',
          component: () => import('./views/EtfMonitorView.vue'),
        },
      ],
    },
  ],
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.token) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  if (to.path === '/login' && auth.token) {
    return '/fund/etf'
  }
  return true
})
