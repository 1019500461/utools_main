import { createRouter, createWebHistory } from 'vue-router'

import { useAuthStore } from './stores/auth'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      redirect: '/system/role',
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
  ],
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.token) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  if (to.path === '/login' && auth.token) {
    return '/system/role'
  }
  return true
})
