<template>
  <section class="page-card">
    <div class="mb-6">
      <h1 class="text-2xl font-semibold text-slate-900">个人中心</h1>
      <p class="mt-2 text-sm text-slate-500">维护账号资料、通知邮箱和登录密码。</p>
    </div>

    <n-card :bordered="false">
      <n-spin :show="loading">
        <n-tabs type="line" animated>
          <n-tab-pane name="profile" tab="修改信息">
            <n-form ref="profileFormRef" class="mt-6 max-w-xl" :model="profileForm" label-placement="left" :label-width="100">
              <n-form-item label="头像">
                <n-avatar round :size="76" color="#ef4444">{{ avatarText }}</n-avatar>
              </n-form-item>
              <n-form-item label="用户姓名" path="username" :rule="{ required: true, message: '请输入用户姓名' }">
                <n-input v-model:value="profileForm.username" placeholder="请输入用户姓名" />
              </n-form-item>
              <n-form-item label="邮箱" path="email" :rule="{ required: true, message: '请输入邮箱' }">
                <n-input v-model:value="profileForm.email" placeholder="请输入邮箱" />
              </n-form-item>
              <div class="ml-[100px] mt-4 flex gap-3">
                <n-button type="primary" :loading="savingProfile" @click="saveProfile">修改</n-button>
                <n-button :loading="testingEmail" @click="testEmail">测试发送邮件</n-button>
              </div>
            </n-form>
          </n-tab-pane>

          <n-tab-pane name="password" tab="修改密码">
            <n-form ref="passwordFormRef" class="mt-6 max-w-xl" :model="passwordForm" label-placement="left" :label-width="120">
              <n-form-item label="旧密码" path="old_password" :rule="{ required: true, message: '请输入旧密码' }">
                <n-input
                  v-model:value="passwordForm.old_password"
                  type="password"
                  show-password-on="mousedown"
                  placeholder="请输入旧密码"
                />
              </n-form-item>
              <n-form-item label="新密码" path="new_password" :rule="{ required: true, message: '请输入新密码' }">
                <n-input
                  v-model:value="passwordForm.new_password"
                  type="password"
                  show-password-on="mousedown"
                  placeholder="请输入新密码"
                />
              </n-form-item>
              <n-form-item label="确认密码" path="confirm_password" :rule="{ required: true, message: '请再次输入新密码' }">
                <n-input
                  v-model:value="passwordForm.confirm_password"
                  type="password"
                  show-password-on="mousedown"
                  placeholder="请再次输入新密码"
                />
              </n-form-item>
              <div class="ml-[120px] mt-4">
                <n-button type="primary" :loading="savingPassword" @click="savePassword">修改</n-button>
              </div>
            </n-form>
          </n-tab-pane>
        </n-tabs>
      </n-spin>
    </n-card>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { NAvatar, NButton, NCard, NForm, NFormItem, NInput, NSpin, NTabPane, NTabs, useMessage, type FormInst } from 'naive-ui'

import { api } from '../api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const message = useMessage()
const loading = ref(false)
const savingProfile = ref(false)
const savingPassword = ref(false)
const testingEmail = ref(false)
const profileFormRef = ref<FormInst | null>(null)
const passwordFormRef = ref<FormInst | null>(null)

const profileForm = reactive({
  username: '',
  email: '',
})

const passwordForm = reactive({
  old_password: '',
  new_password: '',
  confirm_password: '',
})

const avatarText = computed(() => (profileForm.username || 'U').slice(0, 1).toUpperCase())

onMounted(loadProfile)

async function loadProfile() {
  loading.value = true
  try {
    const res = await api.getUserInfo()
    profileForm.username = res.data.username || ''
    profileForm.email = res.data.email || ''
    auth.setUserInfo(res.data)
  } finally {
    loading.value = false
  }
}

async function saveProfile() {
  await profileFormRef.value?.validate()
  savingProfile.value = true
  try {
    const res = await api.updateProfile({
      username: profileForm.username.trim(),
      email: profileForm.email.trim(),
    })
    profileForm.username = res.data.username || ''
    profileForm.email = res.data.email || ''
    auth.setUserInfo(res.data)
    message.success('修改成功')
  } finally {
    savingProfile.value = false
  }
}

async function savePassword() {
  await passwordFormRef.value?.validate()
  if (passwordForm.new_password !== passwordForm.confirm_password) {
    message.error('两次输入的新密码不一致')
    return
  }
  savingPassword.value = true
  try {
    await api.updatePassword({ ...passwordForm })
    Object.assign(passwordForm, { old_password: '', new_password: '', confirm_password: '' })
    message.success('密码修改成功')
  } finally {
    savingPassword.value = false
  }
}

async function testEmail() {
  testingEmail.value = true
  try {
    const res = await api.testNotificationEmail()
    message.success(`测试邮件已发送到 ${res.data.recipient}`)
  } finally {
    testingEmail.value = false
  }
}
</script>
