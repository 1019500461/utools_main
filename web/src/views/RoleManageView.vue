<template>
  <section class="page-card">
    <div class="mb-6 flex flex-wrap items-center justify-between gap-3">
      <div>
        <h1 class="text-2xl font-semibold text-slate-900">角色列表</h1>
        <p class="mt-2 text-sm text-slate-500">管理角色信息，并设置菜单和接口权限。</p>
      </div>
      <n-button type="error" @click="openCreate">
        <template #icon><Icon icon="material-symbols:add" /></template>
        新建角色
      </n-button>
    </div>

    <n-card :bordered="false" class="mb-4">
      <div class="flex flex-wrap items-center gap-4">
        <span class="font-medium text-slate-700">角色名</span>
        <n-input v-model:value="query.role_name" clearable class="max-w-xs" placeholder="请输入角色名" @keyup.enter="loadRoles" />
        <n-button @click="resetQuery">重置</n-button>
        <n-button type="error" @click="loadRoles">搜索</n-button>
      </div>
    </n-card>

    <n-card :bordered="false">
      <n-data-table
        remote
        :columns="columns"
        :data="roles"
        :loading="loading"
        :pagination="pagination"
        :row-key="(row) => row.id"
        @update:page="handlePageChange"
        @update:page-size="handlePageSizeChange"
      />
    </n-card>

    <n-modal v-model:show="modalVisible" preset="card" :title="modalTitle" class="max-w-lg">
      <n-form ref="formRef" :model="form" label-placement="left" label-align="left" :label-width="90">
        <n-form-item label="角色名称" path="name" :rule="{ required: true, message: '请输入角色名称' }">
          <n-input v-model:value="form.name" placeholder="请输入角色名称" />
        </n-form-item>
        <n-form-item label="角色描述" path="desc">
          <n-input v-model:value="form.desc" type="textarea" placeholder="请输入角色描述" />
        </n-form-item>
      </n-form>
      <template #footer>
        <div class="flex justify-end gap-2">
          <n-button @click="modalVisible = false">取消</n-button>
          <n-button type="primary" :loading="saving" @click="saveRole">保存</n-button>
        </div>
      </template>
    </n-modal>

    <n-drawer v-model:show="authDrawerVisible" :width="560" placement="right">
      <n-drawer-content title="设置权限">
        <div class="mb-4 grid grid-cols-[1fr_auto] gap-4">
          <n-input v-model:value="treePattern" clearable placeholder="筛选权限" />
          <n-button type="primary" :loading="savingAuth" @click="saveAuthorized">确定</n-button>
        </div>
        <n-tabs type="line" animated>
          <n-tab-pane name="menus" tab="菜单权限">
            <n-tree
              checkable
              block-line
              default-expand-all
              key-field="id"
              label-field="name"
              :data="menuTree"
              :pattern="treePattern"
              :show-irrelevant-nodes="false"
              :checked-keys="checkedMenuIds"
              @update:checked-keys="(keys) => (checkedMenuIds = keys as number[])"
            />
          </n-tab-pane>
          <n-tab-pane name="apis" tab="接口权限">
            <n-tree
              checkable
              cascade
              block-line
              default-expand-all
              key-field="unique_id"
              label-field="summary"
              :data="apiTree"
              :pattern="treePattern"
              :show-irrelevant-nodes="false"
              :checked-keys="checkedApiIds"
              @update:checked-keys="(keys) => (checkedApiIds = keys as string[])"
            />
          </n-tab-pane>
        </n-tabs>
      </n-drawer-content>
    </n-drawer>
  </section>
</template>

<script setup lang="ts">
import { Icon } from '@iconify/vue'
import { computed, h, onMounted, reactive, ref } from 'vue'
import {
  NButton,
  NCard,
  NDataTable,
  NDrawer,
  NDrawerContent,
  NForm,
  NFormItem,
  NInput,
  NModal,
  NPopconfirm,
  NSpace,
  NTabPane,
  NTabs,
  NTag,
  NTree,
  useMessage,
  type DataTableColumns,
  type FormInst,
  type PaginationProps,
} from 'naive-ui'

import { api, type ApiRecord, type MenuRecord, type RoleRecord } from '../api'

const message = useMessage()
const loading = ref(false)
const saving = ref(false)
const savingAuth = ref(false)
const roles = ref<RoleRecord[]>([])
const query = reactive({ role_name: '' })
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)
const modalVisible = ref(false)
const modalMode = ref<'create' | 'edit'>('create')
const formRef = ref<FormInst | null>(null)
const form = reactive({ id: 0, name: '', desc: '' })
const authDrawerVisible = ref(false)
const currentRoleId = ref(0)
const menus = ref<MenuRecord[]>([])
const apis = ref<ApiRecord[]>([])
const checkedMenuIds = ref<number[]>([])
const checkedApiIds = ref<string[]>([])
const treePattern = ref('')

const modalTitle = computed(() => (modalMode.value === 'create' ? '新建角色' : '编辑角色'))
const pagination = computed<PaginationProps>(() => ({
  page: page.value,
  pageSize: pageSize.value,
  itemCount: total.value,
  showSizePicker: true,
  pageSizes: [10, 20, 50],
}))

const menuTree = computed(() => menus.value)
const apiTree = computed(() => {
  const groups = new Map<string, { unique_id: string; summary: string; children: ApiRecord[] }>()
  for (const item of apis.value) {
    const key = item.tags || '接口'
    if (!groups.has(key)) {
      groups.set(key, { unique_id: key, summary: key, children: [] })
    }
    groups.get(key)?.children.push(item)
  }
  return Array.from(groups.values())
})

const columns: DataTableColumns<RoleRecord> = [
  {
    title: '角色名',
    key: 'name',
    align: 'center',
    render(row) {
      return h(NTag, { type: 'info' }, { default: () => row.name })
    },
  },
  { title: '角色描述', key: 'desc', align: 'center' },
  {
    title: '创建日期',
    key: 'created_at',
    align: 'center',
    render(row) {
      return row.created_at ? new Date(row.created_at).toLocaleDateString() : '-'
    },
  },
  {
    title: '操作',
    key: 'actions',
    align: 'center',
    width: 280,
    render(row) {
      return h(NSpace, { justify: 'center' }, {
        default: () => [
          h(NButton, { size: 'small', type: 'primary', onClick: () => openEdit(row) }, { default: () => '编辑' }),
          h(
            NPopconfirm,
            { positiveText: '确定', negativeText: '取消', onPositiveClick: () => deleteRole(row) },
            {
              trigger: () => h(NButton, { size: 'small', type: 'error' }, { default: () => '删除' }),
              default: () => `确定删除角色「${row.name}」吗？`,
            }
          ),
          h(NButton, { size: 'small', type: 'info', onClick: () => openAuthorized(row) }, { default: () => '设置权限' }),
        ],
      })
    },
  },
]

onMounted(loadRoles)

async function loadRoles() {
  loading.value = true
  try {
    const res = await api.getRoleList({ page: page.value, page_size: pageSize.value, role_name: query.role_name })
    roles.value = res.data
    total.value = res.total || 0
  } finally {
    loading.value = false
  }
}

function resetQuery() {
  query.role_name = ''
  page.value = 1
  loadRoles()
}

function handlePageChange(nextPage: number) {
  page.value = nextPage
  loadRoles()
}

function handlePageSizeChange(nextPageSize: number) {
  pageSize.value = nextPageSize
  page.value = 1
  loadRoles()
}

function openCreate() {
  modalMode.value = 'create'
  Object.assign(form, { id: 0, name: '', desc: '' })
  modalVisible.value = true
}

function openEdit(row: RoleRecord) {
  modalMode.value = 'edit'
  Object.assign(form, { id: row.id, name: row.name, desc: row.desc || '' })
  modalVisible.value = true
}

async function saveRole() {
  await formRef.value?.validate()
  saving.value = true
  try {
    if (modalMode.value === 'create') {
      await api.createRole({ name: form.name.trim(), desc: form.desc })
      message.success('创建成功')
    } else {
      await api.updateRole({ id: form.id, name: form.name.trim(), desc: form.desc })
      message.success('更新成功')
    }
    modalVisible.value = false
    await loadRoles()
  } finally {
    saving.value = false
  }
}

async function deleteRole(row: RoleRecord) {
  await api.deleteRole({ role_id: row.id })
  message.success('删除成功')
  await loadRoles()
}

async function openAuthorized(row: RoleRecord) {
  currentRoleId.value = row.id
  treePattern.value = ''
  const [menuRes, apiRes, authRes] = await Promise.all([api.getMenus(), api.getApis(), api.getRoleAuthorized({ id: row.id })])
  menus.value = menuRes.data
  apis.value = apiRes.data
  checkedMenuIds.value = authRes.data.menus.map((item) => item.id)
  checkedApiIds.value = authRes.data.apis.map((item) => item.unique_id)
  authDrawerVisible.value = true
}

async function saveAuthorized() {
  savingAuth.value = true
  try {
    const apiInfos = apis.value
      .filter((item) => checkedApiIds.value.includes(item.unique_id))
      .map((item) => ({ path: item.path, method: item.method }))
    await api.updateRoleAuthorized({
      id: currentRoleId.value,
      menu_ids: checkedMenuIds.value,
      api_infos: apiInfos,
    })
    const authRes = await api.getRoleAuthorized({ id: currentRoleId.value })
    checkedMenuIds.value = authRes.data.menus.map((item) => item.id)
    checkedApiIds.value = authRes.data.apis.map((item) => item.unique_id)
    message.success('权限保存成功')
    authDrawerVisible.value = false
  } finally {
    savingAuth.value = false
  }
}
</script>
