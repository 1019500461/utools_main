<template>
  <section class="page-card">
    <div class="mb-6 flex flex-wrap items-center justify-between gap-3">
      <div>
        <h1 class="text-2xl font-semibold text-slate-900">用户列表</h1>
        <p class="mt-2 text-sm text-slate-500">管理后台用户、角色、启用状态和默认密码。</p>
      </div>
      <n-button type="error" @click="openCreate">
        <template #icon><Icon icon="material-symbols:add" /></template>
        新建用户
      </n-button>
    </div>

    <n-card :bordered="false" class="mb-4">
      <div class="flex flex-wrap items-center gap-4">
        <span class="font-medium text-slate-700">名称</span>
        <n-input v-model:value="query.username" clearable class="max-w-xs" placeholder="请输入用户名称" @keyup.enter="loadUsers" />
        <span class="font-medium text-slate-700">邮箱</span>
        <n-input v-model:value="query.email" clearable class="max-w-xs" placeholder="请输入邮箱" @keyup.enter="loadUsers" />
        <n-button @click="resetQuery">重置</n-button>
        <n-button type="error" @click="loadUsers">搜索</n-button>
      </div>
    </n-card>

    <n-card :bordered="false">
      <n-data-table
        remote
        :columns="columns"
        :data="users"
        :loading="loading"
        :pagination="pagination"
        :row-key="(row) => row.id"
        @update:page="handlePageChange"
        @update:page-size="handlePageSizeChange"
      />
    </n-card>

    <n-modal v-model:show="modalVisible" preset="card" :title="modalTitle" class="max-w-xl">
      <n-form ref="formRef" :model="form" label-placement="left" label-align="left" :label-width="90">
        <n-form-item label="用户名称" path="username" :rule="{ required: true, message: '请输入用户名称' }">
          <n-input v-model:value="form.username" placeholder="请输入用户名称" />
        </n-form-item>
        <n-form-item label="邮箱" path="email" :rule="{ required: true, message: '请输入邮箱' }">
          <n-input v-model:value="form.email" placeholder="请输入邮箱" />
        </n-form-item>
        <n-form-item v-if="modalMode === 'create'" label="密码" path="password">
          <n-input v-model:value="form.password" type="password" show-password-on="mousedown" placeholder="默认 123456" />
        </n-form-item>
        <n-form-item label="用户角色">
          <n-select v-model:value="form.role_ids" multiple :options="roleOptions" placeholder="请选择角色" />
        </n-form-item>
        <n-form-item label="超级用户">
          <n-switch v-model:value="form.is_superuser" />
        </n-form-item>
        <n-form-item label="启用">
          <n-switch v-model:value="form.is_active" />
        </n-form-item>
      </n-form>
      <template #footer>
        <div class="flex justify-end gap-2">
          <n-button @click="modalVisible = false">取消</n-button>
          <n-button type="primary" :loading="saving" @click="saveUser">保存</n-button>
        </div>
      </template>
    </n-modal>
  </section>
</template>

<script setup lang="ts">
import { Icon } from '@iconify/vue'
import { computed, h, onMounted, reactive, ref } from 'vue'
import {
  NButton,
  NCard,
  NDataTable,
  NForm,
  NFormItem,
  NInput,
  NModal,
  NPopconfirm,
  NSelect,
  NSpace,
  NSwitch,
  NTag,
  useMessage,
  type DataTableColumns,
  type FormInst,
  type PaginationProps,
  type SelectOption,
} from 'naive-ui'

import { api, type RoleRecord, type UserRecord } from '../api'

const message = useMessage()
const loading = ref(false)
const saving = ref(false)
const users = ref<UserRecord[]>([])
const roles = ref<RoleRecord[]>([])
const query = reactive({ username: '', email: '' })
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)
const modalVisible = ref(false)
const modalMode = ref<'create' | 'edit'>('create')
const formRef = ref<FormInst | null>(null)
const form = reactive({
  id: 0,
  username: '',
  email: '',
  password: '123456',
  role_ids: [] as number[],
  is_active: true,
  is_superuser: false,
})

const modalTitle = computed(() => (modalMode.value === 'create' ? '新建用户' : '编辑用户'))
const roleOptions = computed<SelectOption[]>(() => roles.value.map((role) => ({ label: role.name, value: role.id })))
const pagination = computed<PaginationProps>(() => ({
  page: page.value,
  pageSize: pageSize.value,
  itemCount: total.value,
  showSizePicker: true,
  pageSizes: [10, 20, 50],
}))

const columns: DataTableColumns<UserRecord> = [
  {
    title: '头像',
    key: 'avatar',
    align: 'center',
    render(row) {
      return h('div', { class: 'mx-auto grid size-10 place-items-center rounded-full bg-red-500 font-semibold text-white' }, row.username.slice(0, 1).toUpperCase())
    },
  },
  { title: '名称', key: 'username', align: 'center' },
  {
    title: '邮箱',
    key: 'email',
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    title: '用户角色',
    key: 'roles',
    align: 'center',
    render(row) {
      return h(NSpace, { justify: 'center' }, {
        default: () => row.roles.map((role) => h(NTag, { type: 'info', size: 'small' }, { default: () => role.name })),
      })
    },
  },
  {
    title: '超级用户',
    key: 'is_superuser',
    align: 'center',
    render(row) {
      return row.is_superuser ? h(NTag, { type: 'info' }, { default: () => '是' }) : '-'
    },
  },
  {
    title: '上次登录时间',
    key: 'last_login',
    align: 'center',
    render(row) {
      return row.last_login ? new Date(row.last_login).toLocaleString() : '-'
    },
  },
  {
    title: '启用',
    key: 'is_active',
    align: 'center',
    render(row) {
      return h(NSwitch, {
        value: row.is_active,
        onUpdateValue: (value: boolean) => toggleUserActive(row, value),
      })
    },
  },
  {
    title: '操作',
    key: 'actions',
    align: 'center',
    width: 300,
    render(row) {
      return h(NSpace, { justify: 'center' }, {
        default: () => [
          h(NButton, { size: 'small', type: 'primary', onClick: () => openEdit(row) }, { default: () => '编辑' }),
          h(
            NPopconfirm,
            { positiveText: '确定', negativeText: '取消', onPositiveClick: () => resetPassword(row) },
            {
              trigger: () => h(NButton, { size: 'small', type: 'warning' }, { default: () => '重置密码' }),
              default: () => `确定把「${row.username}」的密码重置为 123456 吗？`,
            }
          ),
          h(
            NPopconfirm,
            { positiveText: '确定', negativeText: '取消', onPositiveClick: () => deleteUser(row) },
            {
              trigger: () => h(NButton, { size: 'small', type: 'error' }, { default: () => '删除' }),
              default: () => `确定删除用户「${row.username}」吗？`,
            }
          ),
        ],
      })
    },
  },
]

onMounted(async () => {
  await Promise.all([loadRoles(), loadUsers()])
})

async function loadRoles() {
  const res = await api.getRoleList({ page: 1, page_size: 100 })
  roles.value = res.data
}

async function loadUsers() {
  loading.value = true
  try {
    const res = await api.getUserList({
      page: page.value,
      page_size: pageSize.value,
      username: query.username,
      email: query.email,
    })
    users.value = res.data
    total.value = res.total || 0
  } finally {
    loading.value = false
  }
}

function resetQuery() {
  query.username = ''
  query.email = ''
  page.value = 1
  loadUsers()
}

function handlePageChange(nextPage: number) {
  page.value = nextPage
  loadUsers()
}

function handlePageSizeChange(nextPageSize: number) {
  pageSize.value = nextPageSize
  page.value = 1
  loadUsers()
}

function openCreate() {
  modalMode.value = 'create'
  Object.assign(form, {
    id: 0,
    username: '',
    email: '',
    password: '123456',
    role_ids: roles.value.length ? [roles.value[0].id] : [],
    is_active: true,
    is_superuser: false,
  })
  modalVisible.value = true
}

function openEdit(row: UserRecord) {
  modalMode.value = 'edit'
  Object.assign(form, {
    id: row.id,
    username: row.username,
    email: row.email,
    password: '123456',
    role_ids: row.roles.map((role) => role.id),
    is_active: row.is_active,
    is_superuser: row.is_superuser,
  })
  modalVisible.value = true
}

async function saveUser() {
  await formRef.value?.validate()
  saving.value = true
  try {
    if (modalMode.value === 'create') {
      await api.createUser({
        username: form.username.trim(),
        email: form.email.trim(),
        password: form.password || '123456',
        role_ids: form.role_ids,
        is_active: form.is_active,
        is_superuser: form.is_superuser,
      })
      message.success('创建成功')
    } else {
      await api.updateUser({
        id: form.id,
        username: form.username.trim(),
        email: form.email.trim(),
        role_ids: form.role_ids,
        is_active: form.is_active,
        is_superuser: form.is_superuser,
      })
      message.success('更新成功')
    }
    modalVisible.value = false
    await loadUsers()
  } finally {
    saving.value = false
  }
}

async function toggleUserActive(row: UserRecord, value: boolean) {
  await api.updateUser({
    id: row.id,
    username: row.username,
    email: row.email,
    role_ids: row.roles.map((role) => role.id),
    is_active: value,
    is_superuser: row.is_superuser,
  })
  message.success(value ? '用户已启用' : '用户已禁用')
  await loadUsers()
}

async function resetPassword(row: UserRecord) {
  await api.resetPassword({ user_id: row.id })
  message.success('密码已重置为 123456')
}

async function deleteUser(row: UserRecord) {
  await api.deleteUser({ user_id: row.id })
  message.success('删除成功')
  await loadUsers()
}
</script>
