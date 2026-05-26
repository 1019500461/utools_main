<template>
  <section class="max-w-2xl">
    <div class="mb-5">
      <h1 class="text-xl font-semibold text-slate-900">个人中心</h1>
      <p class="mt-1 text-sm text-slate-500">配置 ETF 观察提醒的接收邮箱。</p>
    </div>

    <n-card :bordered="false">
      <n-spin :show="loading">
        <n-form :model="form" label-placement="left" :label-width="104">
          <n-form-item label="用户名">
            <n-input :value="form.username" disabled />
          </n-form-item>
          <n-form-item
            label="通知邮箱"
            path="email"
            :rule="{ required: true, message: '请输入通知邮箱' }"
          >
            <n-input v-model:value="form.email" placeholder="用于接收观察提醒邮件" />
          </n-form-item>
        </n-form>

        <div class="mt-4 flex justify-end gap-2">
          <n-button :loading="testingEmail" @click="testEmail">测试发送邮件</n-button>
          <n-button type="primary" :loading="saving" @click="saveProfile">保存</n-button>
        </div>
      </n-spin>
    </n-card>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { NButton, NCard, NForm, NFormItem, NInput, NSpin, useMessage } from 'naive-ui'

import { api } from '../api'

const message = useMessage()
const loading = ref(false)
const saving = ref(false)
const testingEmail = ref(false)

const form = reactive({
  username: '',
  email: '',
})

onMounted(() => {
  loadProfile()
})

async function loadProfile() {
  loading.value = true
  try {
    const res = await api.getUserInfo()
    form.username = res.data.username || ''
    form.email = res.data.email || ''
  } finally {
    loading.value = false
  }
}

async function saveProfile() {
  saving.value = true
  try {
    const res = await api.updateProfile({ email: form.email.trim() })
    form.email = res.data.email || ''
    message.success('通知邮箱已保存')
  } finally {
    saving.value = false
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
