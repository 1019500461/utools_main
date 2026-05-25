<template>
  <section>
    <div class="mb-5 flex flex-wrap items-center justify-between gap-3">
      <div>
        <h1 class="text-xl font-semibold text-slate-900">基金/ETF 监控</h1>
        <p class="mt-1 text-sm text-slate-500">列表仅展示关键行情，进入详情后设置回撤提醒。</p>
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
        :pagination="{ pageSize: 12 }"
      />
    </n-card>

    <n-modal v-model:show="createVisible" preset="card" title="新增标的" class="max-w-xl">
      <n-form ref="createFormRef" :model="createForm" label-placement="left" :label-width="96">
        <n-form-item label="代码" path="code" :rule="{ required: true, message: '请输入代码' }">
          <n-input v-model:value="createForm.code" placeholder="例如 510300" />
        </n-form-item>
        <n-form-item label="名称" path="name">
          <n-input v-model:value="createForm.name" placeholder="可选" />
        </n-form-item>
        <n-form-item label="统计范围" path="time_range">
          <n-select v-model:value="createForm.time_range" :options="timeRangeOptions" />
        </n-form-item>
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
        <n-tabs v-model:value="activeTab" type="line" animated>
          <n-tab-pane name="drawdown" tab="回撤提醒设置">
            <div class="grid gap-5 lg:grid-cols-[260px_1fr]">
              <aside class="border-r border-slate-100 pr-4">
                <div class="space-y-2 text-sm text-slate-500">
                  <p class="rounded bg-slate-100 px-3 py-2 font-medium text-slate-900">基金回撤提醒</p>
                  <p class="px-3 py-2">趋势反转提醒</p>
                  <p class="px-3 py-2">下跌抄底提醒</p>
                  <p class="px-3 py-2">上涨分批止盈</p>
                </div>
              </aside>

              <div class="space-y-5">
                <div class="flex items-start justify-between gap-4">
                  <div>
                    <h2 class="text-lg font-semibold text-slate-900">基金回撤提醒</h2>
                    <p class="mt-2 max-w-3xl text-sm leading-6 text-slate-500">
                      以统计周期内的历史高点为锚，当前价格接近预设回撤阈值时提醒；后续每下跌一个阶梯步长再次提醒。
                    </p>
                  </div>
                  <n-switch v-model:value="detailForm.is_active" />
                </div>

                <n-card size="small" title="历史 K 线" :bordered="false">
                  <div ref="klineRef" class="h-80 w-full" data-testid="etf-kline-chart"></div>
                </n-card>

                <n-card size="small" title="参数设置" :bordered="false">
                  <n-form :model="detailForm" label-placement="left" :label-width="104">
                    <div class="grid gap-3 lg:grid-cols-3">
                      <n-form-item label="统计周期">
                        <n-select v-model:value="detailForm.time_range" :options="timeRangeOptions" />
                      </n-form-item>
                      <n-form-item label="回撤阈值">
                        <n-input-number v-model:value="detailForm.x_drop_percent" :min="1" :max="95" :precision="2" class="w-full">
                          <template #suffix>%</template>
                        </n-input-number>
                      </n-form-item>
                      <n-form-item label="阶梯步长">
                        <n-input-number v-model:value="detailForm.y_step_percent" :min="1" :max="50" :precision="2" class="w-full">
                          <template #suffix>%</template>
                        </n-input-number>
                      </n-form-item>
                    </div>
                  </n-form>

                  <div class="mt-2 grid gap-3 text-sm md:grid-cols-4">
                    <InfoRow label="当前价格" :value="formatPrice(detail?.current_price)" />
                    <InfoRow label="区间高点" :value="formatPrice(detail?.peak_price)" value-class="text-red-600" />
                    <InfoRow label="触发价格" :value="formatPrice(detail?.trigger_price)" value-class="text-emerald-600" />
                    <InfoRow label="当前回撤" :value="formatPercent(getRetract(detail))" />
                  </div>

                  <n-alert v-if="getRangeWarning(detail)" class="mt-3" type="warning" :show-icon="false">
                    {{ getRangeWarning(detail) }}
                  </n-alert>

                  <div class="mt-5 flex justify-end">
                    <n-button type="primary" :loading="savingDetail" @click="saveDetailSettings">保存</n-button>
                  </div>
                </n-card>
              </div>
            </div>
          </n-tab-pane>

          <n-tab-pane name="history" tab="历史行情">
            <n-card size="small" :bordered="false">
              <div ref="historyKlineRef" class="h-96 w-full"></div>
            </n-card>
          </n-tab-pane>
        </n-tabs>
      </n-spin>
    </n-modal>
  </section>
</template>

<script setup lang="ts">
import * as echarts from 'echarts'
import { computed, defineComponent, h, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
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
  NTabPane,
  NTabs,
  NTag,
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
      h('div', { class: 'rounded bg-slate-50 px-3 py-2' }, [
        h('p', { class: 'text-xs text-slate-500' }, props.label),
        h('p', { class: ['mt-1 font-medium', props.valueClass] }, props.value),
      ])
  },
})

const message = useMessage()
const loading = ref(false)
const saving = ref(false)
const savingDetail = ref(false)
const syncingAll = ref(false)
const records = ref<EtfMonitorRecord[]>([])
const createVisible = ref(false)
const detailVisible = ref(false)
const detailLoading = ref(false)
const activeTab = ref('drawdown')
const detail = ref<EtfDetailRecord | null>(null)
const createFormRef = ref<FormInst | null>(null)
const klineRef = ref<HTMLDivElement | null>(null)
const historyKlineRef = ref<HTMLDivElement | null>(null)
let klineChart: echarts.ECharts | null = null
let historyKlineChart: echarts.ECharts | null = null

const createForm = reactive({
  code: '',
  name: '',
  time_range: '3y' as EtfTimeRange,
})

const detailForm = reactive({
  code: '',
  name: '',
  is_active: true,
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

const columns: DataTableColumns<EtfMonitorRecord> = [
  { title: '编码', key: 'code', width: 140, render: (row) => h('span', { class: 'font-medium text-slate-900' }, row.code) },
  { title: '当前价格', key: 'current_price', width: 140, render: (row) => formatPrice(row.current_price) },
  {
    title: '今日涨跌幅',
    key: 'change_percent',
    width: 140,
    render(row) {
      return h(NTag, { size: 'small', type: getChangeTagType(row.change_percent), bordered: false }, { default: () => formatPercent(row.change_percent) })
    },
  },
  {
    title: '操作',
    key: 'actions',
    width: 120,
    render(row) {
      return h(NSpace, null, {
        default: () => [
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

watch(activeTab, async () => {
  await nextTick()
  renderCharts()
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

function openCreate() {
  Object.assign(createForm, { code: '', name: '', time_range: '3y' })
  createVisible.value = true
}

async function saveCreate() {
  await createFormRef.value?.validate()
  saving.value = true
  try {
    await api.createEtf({
      code: createForm.code.trim(),
      name: createForm.name.trim() || undefined,
      time_range: createForm.time_range,
      x_drop: 0.15,
      y_step: 0.05,
    })
    message.success('新增成功')
    createVisible.value = false
    await loadList()
  } finally {
    saving.value = false
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

async function openDetail(row: EtfMonitorRecord) {
  detailVisible.value = true
  detailLoading.value = true
  activeTab.value = 'drawdown'
  detail.value = null
  disposeCharts()
  try {
    const res = await api.getEtfDetail({ code: row.code })
    detail.value = res.data
    fillDetailForm(res.data)
    await nextTick()
    renderCharts()
  } finally {
    detailLoading.value = false
  }
}

function fillDetailForm(data: EtfDetailRecord) {
  Object.assign(detailForm, {
    code: data.code,
    name: data.name || '',
    is_active: data.is_active ?? data.monitor ?? true,
    time_range: data.time_range,
    x_drop_percent: ratioToPercent(data.x_drop),
    y_step_percent: ratioToPercent(data.y_step),
  })
}

async function saveDetailSettings() {
  savingDetail.value = true
  try {
    await api.updateEtf({
      code: detailForm.code,
      name: detailForm.name || undefined,
      is_active: detailForm.is_active,
      monitor: detailForm.is_active,
      time_range: detailForm.time_range,
      x_drop: percentToRatio(detailForm.x_drop_percent),
      y_step: percentToRatio(detailForm.y_step_percent),
    })
    message.success('保存成功')
    const res = await api.getEtfDetail({ code: detailForm.code })
    detail.value = res.data
    fillDetailForm(res.data)
    await loadList()
    await nextTick()
    renderCharts()
  } finally {
    savingDetail.value = false
  }
}

function renderCharts() {
  if (!detail.value) return
  if (activeTab.value === 'drawdown') {
    renderKlineChart(klineRef.value, detail.value, 'drawdown')
  }
  if (activeTab.value === 'history') {
    renderKlineChart(historyKlineRef.value, detail.value, 'history')
  }
}

function renderKlineChart(container: HTMLDivElement | null, data: EtfDetailRecord, chartName: 'drawdown' | 'history') {
  if (!container) return
  const chart = chartName === 'drawdown' ? (klineChart ||= echarts.init(container)) : (historyKlineChart ||= echarts.init(container))
  const kline = data.kline || data.klines || []
  const markData = []
  if (typeof data.peak_price === 'number') {
    markData.push({ name: 'Peak', yAxis: data.peak_price, lineStyle: { color: '#dc2626', width: 1.5 } })
  }
  if (typeof data.trigger_price === 'number') {
    markData.push({ name: 'Trigger', yAxis: data.trigger_price, lineStyle: { color: '#16a34a', width: 1.5 } })
  }
  chart.setOption({
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
  historyKlineChart?.resize()
}

function disposeCharts() {
  klineChart?.dispose()
  historyKlineChart?.dispose()
  klineChart = null
  historyKlineChart = null
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

function getChangeTagType(value?: number | null) {
  if (typeof value !== 'number' || value === 0) return 'default'
  return value > 0 ? 'error' : 'success'
}
</script>
