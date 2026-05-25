<template>
  <section>
    <div class="mb-5 flex flex-wrap items-center justify-between gap-3">
      <div>
        <h1 class="text-xl font-semibold text-slate-900">基金/ETF 监控</h1>
        <p class="mt-1 text-sm text-slate-500">管理监控标的，查看历史 K 线和触发价格。</p>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <n-button :loading="syncingAll" @click="syncAll">手动同步</n-button>
        <n-button type="primary" @click="openCreate">新增标的</n-button>
      </div>
    </div>

    <n-card :bordered="false">
      <n-data-table
        :columns="columns"
        :data="records"
        :loading="loading"
        :row-key="(row) => row.code"
        :row-props="rowProps"
        :pagination="{ pageSize: 12 }"
      />
    </n-card>

    <n-modal v-model:show="formVisible" preset="card" :title="formTitle" class="max-w-xl">
      <n-form ref="formRef" :model="form" label-placement="left" :label-width="96">
        <n-form-item label="代码" path="code" :rule="{ required: true, message: '请输入代码' }">
          <n-input v-model:value="form.code" :disabled="formMode === 'edit'" placeholder="例如 510300" />
        </n-form-item>
        <n-form-item label="名称" path="name">
          <n-input v-model:value="form.name" placeholder="可选" />
        </n-form-item>
        <n-form-item label="统计范围" path="time_range">
          <n-select v-model:value="form.time_range" :options="timeRangeOptions" />
        </n-form-item>
        <div class="grid gap-3 md:grid-cols-2">
          <n-form-item label="回撤阈值" path="x_drop_percent">
            <n-input-number v-model:value="form.x_drop_percent" :min="1" :max="95" :precision="2" class="w-full">
              <template #suffix>%</template>
            </n-input-number>
          </n-form-item>
          <n-form-item label="阶梯步长" path="y_step_percent">
            <n-input-number v-model:value="form.y_step_percent" :min="1" :max="50" :precision="2" class="w-full">
              <template #suffix>%</template>
            </n-input-number>
          </n-form-item>
        </div>
      </n-form>
      <template #footer>
        <div class="flex justify-end gap-2">
          <n-button @click="formVisible = false">取消</n-button>
          <n-button type="primary" :loading="saving" @click="saveForm">保存</n-button>
        </div>
      </template>
    </n-modal>

    <n-modal v-model:show="detailVisible" preset="card" :title="detailTitle" class="max-w-6xl">
      <n-spin :show="detailLoading">
        <div class="grid gap-4 lg:grid-cols-[1fr_280px]">
          <n-card size="small" title="历史 K 线" :bordered="false">
            <div ref="klineRef" class="h-96 w-full" data-testid="etf-kline-chart"></div>
          </n-card>
          <div>
            <n-card size="small" title="监控数据" :bordered="false">
              <div class="space-y-3 text-sm">
                <InfoRow label="当前价格" :value="formatPrice(detail?.current_price)" />
                <InfoRow label="区间高点" :value="formatPrice(detail?.peak_price)" value-class="text-red-600" />
                <InfoRow label="触发价格" :value="formatPrice(detail?.trigger_price)" value-class="text-emerald-600" />
                <InfoRow label="当前回撤" :value="formatPercent(getRetract(detail))" />
                <n-alert v-if="getRangeWarning(detail)" type="warning" :show-icon="false">
                  {{ getRangeWarning(detail) }}
                </n-alert>
              </div>
            </n-card>
          </div>
        </div>
      </n-spin>
    </n-modal>
  </section>
</template>

<script setup lang="ts">
import * as echarts from 'echarts'
import { computed, defineComponent, h, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import {
  NAlert,
  NButton,
  NCard,
  NDataTable,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NModal,
  NSelect,
  NSpace,
  NSpin,
  NSwitch,
  useMessage,
  type DataTableColumns,
  type FormInst,
} from 'naive-ui'

import { api, type EtfDetailRecord, type EtfMonitorRecord, type EtfTimeRange } from '../api'

const InfoRow = defineComponent({
  props: {
    label: { type: String, required: true },
    value: { type: String, required: true },
    valueClass: { type: String, default: 'text-slate-900' },
  },
  setup(props) {
    return () =>
      h('div', { class: 'flex justify-between gap-3' }, [
        h('span', { class: 'text-slate-500' }, props.label),
        h('span', { class: ['font-medium', props.valueClass] }, props.value),
      ])
  },
})

const message = useMessage()
const loading = ref(false)
const saving = ref(false)
const syncingAll = ref(false)
const syncingCodes = ref<string[]>([])
const detailLoading = ref(false)
const records = ref<EtfMonitorRecord[]>([])
const formVisible = ref(false)
const formMode = ref<'create' | 'edit'>('create')
const detailVisible = ref(false)
const detail = ref<EtfDetailRecord | null>(null)
const formRef = ref<FormInst | null>(null)
const klineRef = ref<HTMLDivElement | null>(null)
let klineChart: echarts.ECharts | null = null

const form = reactive({
  code: '',
  name: '',
  time_range: '3y' as EtfTimeRange,
  x_drop_percent: 15,
  y_step_percent: 5,
})

const timeRangeOptions = [
  { label: '近 3 年', value: '3y' },
  { label: '近 5 年', value: '5y' },
  { label: '成立以来', value: 'all' },
]

const formTitle = computed(() => (formMode.value === 'create' ? '新增标的' : '编辑标的'))
const detailTitle = computed(() => {
  if (!detail.value) return '标的详情'
  return `${detail.value.name || detail.value.code} ${detail.value.code}`
})
const columns: DataTableColumns<EtfMonitorRecord> = [
  { title: '代码', key: 'code', width: 110, render: (row) => h('span', { class: 'font-medium text-slate-900' }, row.code) },
  {
    title: '名称',
    key: 'name',
    minWidth: 160,
    render(row) {
      const warning = getRangeWarning(row)
      return h('div', { class: 'space-y-1' }, [
        h('div', { class: 'text-slate-900' }, row.name || '-'),
        warning ? h('div', { class: 'text-xs text-amber-600' }, warning) : null,
      ])
    },
  },
  { title: '当前价格', key: 'current_price', width: 120, render: (row) => formatPrice(row.current_price) },
  { title: '当前回撤', key: 'retract', width: 130, render: (row) => formatPercent(getRetract(row)) },
  {
    title: '监控',
    key: 'monitor',
    width: 100,
    render(row) {
      return h(NSwitch, {
        value: isMonitoring(row),
        onClick: (event: MouseEvent) => event.stopPropagation(),
        'onUpdate:value': (value: boolean) => updateActive(row, value),
      })
    },
  },
  {
    title: '操作',
    key: 'actions',
    width: 240,
    render(row) {
      return h(NSpace, null, {
        default: () => [
          h(
            NButton,
            {
              size: 'small',
              secondary: true,
              loading: syncingCodes.value.includes(row.code),
              onClick: (event: MouseEvent) => {
                event.stopPropagation()
                syncOne(row.code)
              },
            },
            { default: () => '同步' }
          ),
          h(
            NButton,
            {
              size: 'small',
              secondary: true,
              onClick: (event: MouseEvent) => {
                event.stopPropagation()
                openEdit(row)
              },
            },
            { default: () => '编辑' }
          ),
          h(
            NButton,
            {
              size: 'small',
              type: 'primary',
              secondary: true,
              onClick: (event: MouseEvent) => {
                event.stopPropagation()
                openDetail(row)
              },
            },
            { default: () => '详情' }
          ),
        ],
      })
    },
  },
]

onMounted(() => {
  loadList()
  window.addEventListener('resize', resizeCharts)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeCharts)
  disposeCharts()
})

async function loadList() {
  loading.value = true
  try {
    const res = await api.getEtfList()
    records.value = res.data || []
  } finally {
    loading.value = false
  }
}

function rowProps(row: EtfMonitorRecord) {
  return {
    class: 'cursor-pointer',
    onClick: () => openDetail(row),
  }
}

function openCreate() {
  formMode.value = 'create'
  Object.assign(form, { code: '', name: '', time_range: '3y', x_drop_percent: 15, y_step_percent: 5 })
  formVisible.value = true
}

function openEdit(row: EtfMonitorRecord) {
  formMode.value = 'edit'
  Object.assign(form, {
    code: row.code,
    name: row.name || '',
    time_range: row.time_range,
    x_drop_percent: ratioToPercent(row.x_drop),
    y_step_percent: ratioToPercent(row.y_step),
  })
  formVisible.value = true
}

async function saveForm() {
  await formRef.value?.validate()
  saving.value = true
  try {
    const payload = {
      code: form.code.trim(),
      name: form.name.trim() || undefined,
      time_range: form.time_range,
      x_drop: percentToRatio(form.x_drop_percent),
      y_step: percentToRatio(form.y_step_percent),
    }
    if (formMode.value === 'create') {
      await api.createEtf(payload)
      message.success('新增成功')
    } else {
      await api.updateEtf(payload)
      message.success('保存成功')
    }
    formVisible.value = false
    await loadList()
  } finally {
    saving.value = false
  }
}

async function updateActive(row: EtfMonitorRecord, value: boolean) {
  const previous = isMonitoring(row)
  setMonitoring(row, value)
  try {
    await api.updateEtf({ code: row.code, is_active: value, monitor: value })
    message.success(value ? '监控已开启' : '监控已关闭')
  } catch (error) {
    setMonitoring(row, previous)
    throw error
  }
}

async function syncAll() {
  syncingAll.value = true
  try {
    await api.syncEtf()
    message.success('同步任务已完成')
    await loadList()
  } finally {
    syncingAll.value = false
  }
}

async function syncOne(code: string) {
  syncingCodes.value = [...syncingCodes.value, code]
  try {
    await api.syncEtf({ code })
    message.success(`${code} 同步完成`)
    await loadList()
  } finally {
    syncingCodes.value = syncingCodes.value.filter((item) => item !== code)
  }
}

async function openDetail(row: EtfMonitorRecord) {
  detailVisible.value = true
  detailLoading.value = true
  detail.value = null
  disposeCharts()
  try {
    const res = await api.getEtfDetail({ code: row.code })
    detail.value = res.data
    await nextTick()
    renderKlineChart(res.data)
  } finally {
    detailLoading.value = false
  }
}

function renderKlineChart(data: EtfDetailRecord) {
  if (!klineRef.value) return
  klineChart ||= echarts.init(klineRef.value)
  const kline = data.kline || data.klines || []
  const markData = []
  if (typeof data.peak_price === 'number') {
    markData.push({ name: 'Peak', yAxis: data.peak_price, lineStyle: { color: '#dc2626', width: 1.5 } })
  }
  if (typeof data.trigger_price === 'number') {
    markData.push({ name: 'Trigger', yAxis: data.trigger_price, lineStyle: { color: '#16a34a', width: 1.5 } })
  }
  klineChart.setOption({
    animation: false,
    grid: { left: 48, right: 28, top: 24, bottom: 42 },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: kline.map((item) => item.date), boundaryGap: true },
    yAxis: { scale: true, splitLine: { lineStyle: { color: '#e2e8f0' } } },
    dataZoom: [{ type: 'inside' }, { type: 'slider', height: 18, bottom: 10 }],
    series: [
      {
        type: 'candlestick',
        data: kline.map((item) => [item.open, item.close, item.low, item.high]),
        itemStyle: { color: '#ef4444', color0: '#10b981', borderColor: '#dc2626', borderColor0: '#059669' },
        markLine: { symbol: 'none', data: markData },
      },
    ],
  })
}

function resizeCharts() {
  klineChart?.resize()
}

function disposeCharts() {
  klineChart?.dispose()
  klineChart = null
}

function isMonitoring(row: EtfMonitorRecord) {
  return typeof row.monitor === 'boolean' ? row.monitor : row.is_active
}

function setMonitoring(row: EtfMonitorRecord, value: boolean) {
  row.monitor = value
  row.is_active = value
}

function getRetract(row?: EtfMonitorRecord | EtfDetailRecord | null) {
  return row?.retract ?? row?.current_retract ?? null
}

function getRangeWarning(row?: EtfMonitorRecord | EtfDetailRecord | null) {
  return row?.range_warning || row?.range_notice || null
}

function percentToRatio(value: number | null) {
  return Number(((value || 0) / 100).toFixed(6))
}

function ratioToPercent(value: number | null | undefined) {
  return Number(((value || 0) * 100).toFixed(2))
}

function formatPrice(value?: number | null) {
  return typeof value === 'number' ? value.toFixed(3) : '-'
}

function formatPercent(value?: number | null) {
  return typeof value === 'number' ? `${(value * 100).toFixed(2)}%` : '-'
}
</script>
