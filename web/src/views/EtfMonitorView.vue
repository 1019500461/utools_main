<template>
  <section>
    <div class="mb-5 flex flex-wrap items-center justify-between gap-3">
      <div>
        <h1 class="text-xl font-semibold text-slate-900">基金/ETF 监控</h1>
        <p class="mt-1 text-sm text-slate-500">管理监控标的，查看历史 K 线、分时走势和触发价格。</p>
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

    <n-modal v-model:show="createVisible" preset="card" title="新增标的" class="max-w-xl">
      <n-form ref="formRef" :model="form" label-placement="left" :label-width="96">
        <n-form-item label="代码" path="code" :rule="{ required: true, message: '请输入代码' }">
          <n-input v-model:value="form.code" placeholder="例如 510300" />
        </n-form-item>
        <n-form-item label="名称" path="name">
          <n-input v-model:value="form.name" placeholder="可选，后端可自动补全时可留空" />
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
          <n-button @click="createVisible = false">取消</n-button>
          <n-button type="primary" :loading="saving" @click="saveCreate">保存</n-button>
        </div>
      </template>
    </n-modal>

    <n-modal v-model:show="detailVisible" preset="card" :title="detailTitle" class="max-w-6xl">
      <n-spin :show="detailLoading">
        <div class="grid gap-4 lg:grid-cols-[1fr_280px]">
          <div class="space-y-4">
            <n-card size="small" title="历史 K 线" :bordered="false">
              <div ref="klineRef" class="h-80 w-full"></div>
            </n-card>
            <n-card size="small" title="分时走势" :bordered="false">
              <div ref="intradayRef" class="h-64 w-full"></div>
            </n-card>
          </div>
          <div class="space-y-4">
            <n-card size="small" title="监控数据" :bordered="false">
              <div class="space-y-3 text-sm">
                <div class="flex justify-between gap-3">
                  <span class="text-slate-500">当前价格</span>
                  <span class="font-medium text-slate-900">{{ formatPrice(detail?.current_price) }}</span>
                </div>
                <div class="flex justify-between gap-3">
                  <span class="text-slate-500">区间高点</span>
                  <span class="font-medium text-red-600">{{ formatPrice(detail?.peak_price) }}</span>
                </div>
                <div class="flex justify-between gap-3">
                  <span class="text-slate-500">触发价格</span>
                  <span class="font-medium text-emerald-600">{{ formatPrice(detail?.trigger_price) }}</span>
                </div>
                <div class="flex justify-between gap-3">
                  <span class="text-slate-500">当前回撤</span>
                  <span class="font-medium text-slate-900">{{ formatPercent(getRetract(detail)) }}</span>
                </div>
                <n-alert v-if="getRangeWarning(detail)" type="warning" :show-icon="false">
                  {{ getRangeWarning(detail) }}
                </n-alert>
              </div>
            </n-card>
            <n-card size="small" title="基本面" :bordered="false">
              <div class="space-y-3 text-sm">
                <div class="flex justify-between gap-3">
                  <span class="text-slate-500">资产规模</span>
                  <span class="font-medium text-slate-900">{{ fundamental?.aum || '暂无数据' }}</span>
                </div>
                <div class="flex justify-between gap-3">
                  <span class="text-slate-500">最新估值</span>
                  <span class="font-medium text-slate-900">{{ fundamental?.valuation || '暂无数据' }}</span>
                </div>
                <div>
                  <p class="mb-2 text-slate-500">核心持仓</p>
                  <div v-if="holdings.length" class="space-y-2">
                    <div v-for="item in holdings" :key="item.name" class="flex justify-between gap-3">
                      <span class="truncate text-slate-900">{{ item.name }}</span>
                      <span class="shrink-0 text-slate-500">{{ item.percent ?? '-' }}</span>
                    </div>
                  </div>
                  <n-empty v-else size="small" description="暂无数据" />
                </div>
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
import { computed, h, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import {
  NAlert,
  NButton,
  NCard,
  NDataTable,
  NEmpty,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NModal,
  NSelect,
  NSpace,
  NSpin,
  NSwitch,
  NTag,
  useMessage,
  type DataTableColumns,
  type FormInst,
} from 'naive-ui'

import { api, type EtfDetailRecord, type EtfMonitorRecord, type EtfTimeRange } from '../api'

const message = useMessage()
const loading = ref(false)
const saving = ref(false)
const syncingAll = ref(false)
const syncingCodes = ref<string[]>([])
const detailLoading = ref(false)
const records = ref<EtfMonitorRecord[]>([])
const createVisible = ref(false)
const detailVisible = ref(false)
const detail = ref<EtfDetailRecord | null>(null)
const formRef = ref<FormInst | null>(null)
const klineRef = ref<HTMLDivElement | null>(null)
const intradayRef = ref<HTMLDivElement | null>(null)
let klineChart: echarts.ECharts | null = null
let intradayChart: echarts.ECharts | null = null

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

const detailTitle = computed(() => {
  if (!detail.value) return '标的详情'
  return `${detail.value.name || detail.value.code} ${detail.value.code}`
})

const fundamental = computed(() => detail.value?.fundamental || detail.value?.fundamentals || null)
const holdings = computed(() => fundamental.value?.holdings || [])

const columns: DataTableColumns<EtfMonitorRecord> = [
  {
    title: '代码',
    key: 'code',
    width: 110,
    render(row) {
      return h('span', { class: 'font-medium text-slate-900' }, row.code)
    },
  },
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
  {
    title: '当前价格',
    key: 'current_price',
    width: 120,
    render(row) {
      return formatPrice(row.current_price)
    },
  },
  {
    title: '今日涨跌',
    key: 'change_percent',
    width: 130,
    render(row) {
      return h(
        NTag,
        { size: 'small', type: getChangeTagType(row.change_percent), bordered: false },
        { default: () => formatPercent(row.change_percent) }
      )
    },
  },
  {
    title: '当前回撤',
    key: 'retract',
    width: 130,
    render(row) {
      return formatPercent(getRetract(row))
    },
  },
  {
    title: '监控',
    key: 'monitor',
    width: 100,
    render(row) {
      return h(NSwitch, {
        value: isMonitoring(row),
        loading: loading.value,
        onClick: (event: MouseEvent) => event.stopPropagation(),
        'onUpdate:value': (value: boolean) => updateActive(row, value),
      })
    },
  },
  {
    title: '操作',
    key: 'actions',
    width: 180,
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
  Object.assign(form, { code: '', name: '', time_range: '3y', x_drop_percent: 15, y_step_percent: 5 })
  createVisible.value = true
}

async function saveCreate() {
  await formRef.value?.validate()
  saving.value = true
  try {
    await api.createEtf({
      code: form.code.trim(),
      name: form.name.trim() || undefined,
      time_range: form.time_range,
      x_drop: percentToRatio(form.x_drop_percent),
      y_step: percentToRatio(form.y_step_percent),
    })
    message.success('新增成功')
    createVisible.value = false
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
    renderCharts()
  } finally {
    detailLoading.value = false
  }
}

function renderCharts() {
  if (!detail.value) return
  renderKlineChart(detail.value)
  renderIntradayChart(detail.value)
}

function renderKlineChart(data: EtfDetailRecord) {
  if (!klineRef.value) return
  klineChart ||= echarts.init(klineRef.value)
  const kline = data.kline || data.klines || []
  const dates = kline.map((item) => item.date)
  const values = kline.map((item) => [item.open, item.close, item.low, item.high])
  const markData = []
  if (typeof data.peak_price === 'number') {
    markData.push({
      name: 'peak',
      yAxis: data.peak_price,
      label: { formatter: 'peak' },
      lineStyle: { color: '#dc2626', width: 1.5 },
    })
  }
  if (typeof data.trigger_price === 'number') {
    markData.push({
      name: 'trigger',
      yAxis: data.trigger_price,
      label: { formatter: 'trigger' },
      lineStyle: { color: '#16a34a', width: 1.5 },
    })
  }

  klineChart.setOption({
    animation: false,
    grid: { left: 48, right: 28, top: 24, bottom: 42 },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: dates, boundaryGap: true, axisLine: { lineStyle: { color: '#cbd5e1' } } },
    yAxis: { scale: true, axisLine: { lineStyle: { color: '#cbd5e1' } }, splitLine: { lineStyle: { color: '#e2e8f0' } } },
    dataZoom: [{ type: 'inside' }, { type: 'slider', height: 18, bottom: 10 }],
    series: [
      {
        type: 'candlestick',
        data: values,
        itemStyle: { color: '#ef4444', color0: '#10b981', borderColor: '#dc2626', borderColor0: '#059669' },
        markLine: { symbol: 'none', data: markData },
      },
    ],
  })
}

function renderIntradayChart(data: EtfDetailRecord) {
  if (!intradayRef.value) return
  intradayChart ||= echarts.init(intradayRef.value)
  const intraday = data.intraday || data.minutes || []
  intradayChart.setOption({
    animation: false,
    grid: { left: 48, right: 28, top: 24, bottom: 28 },
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: intraday.map((item) => item.time),
      axisLine: { lineStyle: { color: '#cbd5e1' } },
    },
    yAxis: { type: 'value', scale: true, splitLine: { lineStyle: { color: '#e2e8f0' } } },
    series: [
      {
        type: 'line',
        smooth: true,
        showSymbol: false,
        data: intraday.map((item) => item.price),
        lineStyle: { color: '#2563eb', width: 2 },
        areaStyle: { color: 'rgba(37, 99, 235, 0.08)' },
      },
    ],
  })
}

function resizeCharts() {
  klineChart?.resize()
  intradayChart?.resize()
}

function disposeCharts() {
  klineChart?.dispose()
  intradayChart?.dispose()
  klineChart = null
  intradayChart = null
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

function formatPrice(value?: number | null) {
  return typeof value === 'number' ? value.toFixed(3) : '-'
}

function formatPercent(value?: number | null) {
  return typeof value === 'number' ? `${(value * 100).toFixed(2)}%` : '-'
}

function getChangeTagType(value?: number | null) {
  if (typeof value !== 'number' || value === 0) return 'default'
  return value > 0 ? 'error' : 'success'
}
</script>
