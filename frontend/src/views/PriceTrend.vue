<template>
  <div class="price-trend">
    <!-- 顶部筛选 -->
    <div class="filter-bar">
      <div class="filter-title">
        <el-icon :size="20" color="#409EFF"><TrendCharts /></el-icon>
        <span>物料单价趋势分析</span>
        <el-tag type="info" size="small" style="margin-left:8px">滚动13个月</el-tag>
      </div>
      <div class="filter-controls">
        <OrgFilter ref="orgFilterRef" @change="onOrgFilterChange" />
      </div>
    </div>

    <!-- 搜索卡片 -->
    <el-card class="search-card" shadow="never">
      <div class="search-header">
        <div class="search-left">
          <span class="search-title">自定义物料查询</span>
        </div>
        <div class="search-right">
          <el-autocomplete
            v-model="searchKeyword"
            :fetch-suggestions="handleSearch"
            placeholder="输入物料编码或名称搜索..."
            style="width: 360px"
            :trigger-on-focus="false"
            clearable
            @select="handleSelect"
            @clear="clearCustom"
            value-key="material_code"
          >
            <template #default="{ item }">
              <div class="search-item">
                <span class="search-code">{{ stripLeadingZeros(item.material_code) }}</span>
                <span class="search-name">{{ item.material_name }}</span>
                <span class="search-amt">¥{{ formatMoney(item.total_amount_cny) }}</span>
              </div>
            </template>
          </el-autocomplete>
        </div>
      </div>
    </el-card>

    <!-- 自定义物料趋势（搜索选中后展示） -->
    <el-card v-if="customTrend" class="custom-chart-card" shadow="hover">
      <template #header>
        <div class="chart-card-header">
          <div class="chart-title-area">
            <el-icon color="#E6A23C"><Star /></el-icon>
            <span class="chart-title">{{ customTrend.material_name }}</span>
            <el-tag size="small">{{ stripLeadingZeros(customTrend.material_code) }}</el-tag>
            <el-tag size="small" type="info">{{ customTrend.order_currency || '-' }}</el-tag>
            <span class="chart-subtitle" v-if="customTrend.specification">{{ customTrend.specification }}</span>
          </div>
          <div class="chart-stats">
            <span>总采购额: <b>¥{{ formatMoney(customTrend.total_amount_cny) }}</b></span>
            <span>总笔数: <b>{{ customTrend.total_orders }}</b></span>
          </div>
          <el-button :icon="Close" circle size="small" @click="clearCustom" />
        </div>
      </template>
      <v-chart :option="buildChartOption(customTrend, true)" autoresize style="height: 300px" />
      <div class="card-scroll-bar">
        <el-button size="small" text :disabled="getCardOffset('custom_' + customTrend.material_code) >= 60" @click="scrollCustomCard(-3)">
          <el-icon><ArrowLeft /></el-icon>
        </el-button>
        <el-tag size="small" type="info" effect="plain" class="card-range-tag">{{ getCardRangeLabel('custom_' + customTrend.material_code) }}</el-tag>
        <el-button size="small" text :disabled="getCardOffset('custom_' + customTrend.material_code) <= 0" @click="scrollCustomCard(3)">
          <el-icon><ArrowRight /></el-icon>
        </el-button>
        <el-button v-if="getCardOffset('custom_' + customTrend.material_code) !== 0" size="small" text type="warning" class="reset-btn" @click="resetCustomCardScroll">最新</el-button>
      </div>
    </el-card>

    <!-- TOP 20 物料趋势网格 -->
    <div class="section-header" v-if="!topLoading">
      <span class="section-title">采购金额 TOP 20 物料单价走势</span>
      <el-tag type="info" size="small">滚动13个月 · 每个卡片可独立前后切换3个月</el-tag>
    </div>

    <div v-if="topLoading" class="loading-area">
      <el-skeleton :rows="6" animated />
      <el-skeleton :rows="6" animated style="margin-top:16px" />
    </div>

    <div v-else class="chart-grid">
      <el-card
        v-for="(trend, idx) in topTrends"
        :key="trend.material_code"
        class="chart-card"
        shadow="hover"
      >
        <template #header>
          <div class="mini-header">
            <div class="mini-title">
              <span class="rank-badge">#{{ idx + 1 }}</span>
              <span class="mini-name" :title="trend.material_name">{{ trend.material_name }}</span>
              <el-tag size="small" type="info" style="margin-left:4px">{{ stripLeadingZeros(trend.material_code) }}</el-tag>
            </div>
          </div>
        </template>
        <v-chart :option="buildChartOption(trend, false)" autoresize style="height: 220px" />
        <div class="card-scroll-bar">
          <el-button size="small" text :disabled="getCardOffset(trend.material_code) >= 60" @click="scrollCard(trend.material_code, -3)">
            <el-icon><ArrowLeft /></el-icon>
          </el-button>
          <el-tag size="small" type="info" effect="plain" class="card-range-tag">{{ getCardRangeLabel(trend.material_code) }}</el-tag>
          <el-button size="small" text :disabled="getCardOffset(trend.material_code) <= 0" @click="scrollCard(trend.material_code, 3)">
            <el-icon><ArrowRight /></el-icon>
          </el-button>
          <el-button v-if="getCardOffset(trend.material_code) !== 0" size="small" text type="warning" class="reset-btn" @click="resetCardScroll(trend.material_code)">最新</el-button>
          <span class="mini-amt">¥{{ formatMoney(trend.total_amount_cny) }}</span>
        </div>
      </el-card>
    </div>

    <el-empty v-if="!topLoading && topTrends.length === 0" description="暂无物料趋势数据" />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  GridComponent,
  MarkLineComponent,
} from 'echarts/components'
import VChart from 'vue-echarts'
import { TrendCharts, Star, Close, ArrowLeft, ArrowRight } from '@element-plus/icons-vue'
import { searchMaterials, getMaterialTrend, getTopMaterialTrends } from '../api/priceTrend'
import OrgFilter from '../components/OrgFilter.vue'
import { stripLeadingZeros } from '../utils/format'

use([CanvasRenderer, LineChart, TitleComponent, TooltipComponent, GridComponent, MarkLineComponent])

// ========== 筛选状态 ==========
const orgFilterRef = ref(null)
const orgFilter = reactive({
  level: 'all',
  companyCodes: [],
  companyName: ''
})
function getExtraParams() {
  const extra = {}
  if (orgFilter.companyCodes.length > 0) extra.company_codes = orgFilter.companyCodes
  return extra
}

// ========== 卡片独立滚动控制 ==========
const cardOffsets = reactive({})  // material_code -> offset（月份偏移量，0=最新）

function getCardOffset(code) {
  return cardOffsets[code] || 0
}

function calcEndMonth(offset) {
  if (!offset || offset <= 0) return null
  const now = new Date()
  const d = new Date(now.getFullYear(), now.getMonth() - offset, 1)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

function getCardRangeLabel(code) {
  const offset = getCardOffset(code)
  const endMonth = calcEndMonth(offset)
  let endYear, endMo
  if (!endMonth) {
    const now = new Date()
    endYear = now.getFullYear()
    endMo = now.getMonth() + 1
  } else {
    const parts = endMonth.split('-')
    endYear = parseInt(parts[0])
    endMo = parseInt(parts[1])
  }
  let startMo = endMo - 12
  let startYear = endYear
  while (startMo <= 0) { startMo += 12; startYear -= 1 }
  return `${startYear}-${String(startMo).padStart(2, '0')}~${endYear}-${String(endMo).padStart(2, '0')}`
}

async function scrollCard(code, delta) {
  const current = getCardOffset(code)
  const newOffset = Math.max(0, Math.min(60, current - delta))
  cardOffsets[code] = newOffset
  // 重新加载该卡片数据
  try {
    const extra = getExtraParams()
    const endMonth = calcEndMonth(newOffset)
    if (endMonth) extra.end_month = endMonth
    const data = await getMaterialTrend(code, 13, extra)
    if (data && !data.error) {
      // 替换 topTrends 中对应的卡片
      const idx = topTrends.value.findIndex(t => t.material_code === code)
      if (idx !== -1) topTrends.value[idx] = data
    }
  } catch (e) {
    console.error('卡片滚动加载失败:', e)
  }
}

function resetCardScroll(code) {
  cardOffsets[code] = 0
  ;(async () => {
    try {
      const extra = getExtraParams()
      const data = await getMaterialTrend(code, 13, extra)
      if (data && !data.error) {
        const idx = topTrends.value.findIndex(t => t.material_code === code)
        if (idx !== -1) topTrends.value[idx] = data
      }
    } catch (e) { console.error(e) }
  })()
}

function onOrgFilterChange(payload) {
  orgFilter.level = payload.level
  orgFilter.companyCodes = payload.companyCodes || []
  orgFilter.companyName = payload.companyName || ''
  refreshAll()
}

function refreshAll() {
  // 重置所有卡片偏移
  Object.keys(cardOffsets).forEach(k => delete cardOffsets[k])
  loadTopTrends()
  if (customTrend.value?.material_code) {
    reloadCustomTrend()
  }
}

async function reloadCustomTrend() {
  if (!customTrend.value?.material_code) return
  try {
    const extra = getExtraParams()
    const data = await getMaterialTrend(customTrend.value.material_code, 13, extra)
    if (data && !data.error) customTrend.value = data
    else customTrend.value = null
  } catch (e) {
    console.error('重新加载自定义物料趋势失败:', e)
  }
}

// 自定义物料卡片滚动
async function scrollCustomCard(delta) {
  if (!customTrend.value?.material_code) return
  const code = customTrend.value.material_code
  const key = 'custom_' + code
  const current = getCardOffset(key)
  const newOffset = Math.max(0, Math.min(60, current - delta))
  cardOffsets[key] = newOffset
  try {
    const extra = getExtraParams()
    const endMonth = calcEndMonth(newOffset)
    if (endMonth) extra.end_month = endMonth
    const data = await getMaterialTrend(code, 13, extra)
    if (data && !data.error) customTrend.value = data
  } catch (e) {
    console.error('自定义卡片滚动加载失败:', e)
  }
}

function resetCustomCardScroll() {
  if (!customTrend.value?.material_code) return
  const key = 'custom_' + customTrend.value.material_code
  cardOffsets[key] = 0
  ;(async () => {
    try {
      const extra = getExtraParams()
      const data = await getMaterialTrend(customTrend.value.material_code, 13, extra)
      if (data && !data.error) customTrend.value = data
    } catch (e) { console.error(e) }
  })()
}

// ========== 搜索 ==========
const searchKeyword = ref('')
const customTrend = ref(null)

async function handleSearch(query, cb) {
  if (!query || query.length < 1) { cb([]); return }
  try {
    const extra = getExtraParams()
    const data = await searchMaterials(query, 15, extra)
    cb(data || [])
  } catch {
    cb([])
  }
}

async function handleSelect(item) {
  searchKeyword.value = item.material_code
  try {
    const extra = getExtraParams()
    const data = await getMaterialTrend(item.material_code, 13, extra)
    if (data && !data.error) customTrend.value = data
  } catch (e) {
    console.error('获取趋势失败:', e)
  }
}

function clearCustom() {
  customTrend.value = null
  searchKeyword.value = ''
}

// ========== TOP 20 ==========
const topLoading = ref(false)
const topTrends = ref([])

async function loadTopTrends() {
  topLoading.value = true
  try {
    const extra = getExtraParams()
    const data = await getTopMaterialTrends(20, 13, extra)
    topTrends.value = data || []
  } catch (e) {
    console.error('加载TOP物料趋势失败:', e)
  } finally {
    topLoading.value = false
  }
}

// ========== 图表构建 ==========
function buildChartOption(trend, isLarge) {
  const monthly = trend.monthly || []
  const labels = monthly.map(m => m.label)
  const prices = monthly.map(m => m.avg_order_price)

  // 计算平均线
  const validPrices = prices.filter(p => p > 0)
  const avgPrice = validPrices.length > 0
    ? validPrices.reduce((a, b) => a + b, 0) / validPrices.length
    : 0

  return {
    tooltip: {
      trigger: 'axis',
      formatter(params) {
        const p = params[0]
        const m = monthly[p.dataIndex]
        if (!m) return ''
        return `<b>${m.label}</b><br/>
          加权均价(CNY): <b>${m.avg_order_price.toFixed(4)}</b><br/>
          采购量: ${m.quantity.toFixed(2)} ${trend.unit || ''}<br/>
          金额(CNY): ¥${m.amount_cny.toLocaleString()}<br/>
          笔数: ${m.order_count}`
      }
    },
    grid: {
      top: isLarge ? 20 : 10,
      right: isLarge ? 30 : 16,
      bottom: 28,
      left: isLarge ? 60 : 48,
    },
    xAxis: {
      type: 'category',
      data: labels,
      axisLabel: {
        fontSize: isLarge ? 12 : 10,
        rotate: labels.length > 10 ? 30 : 0,
        formatter(v) { return v.substring(5) }  // 只显示 MM
      },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      axisLabel: { fontSize: isLarge ? 11 : 9, formatter: v => v >= 1000 ? (v/1000).toFixed(1)+'k' : v.toFixed(2) },
      splitLine: { lineStyle: { type: 'dashed', color: '#e8e8e8' } },
    },
    series: [{
      type: 'line',
      data: prices,
      smooth: true,
      symbol: 'circle',
      symbolSize: isLarge ? 8 : 5,
      lineStyle: { width: 2, color: '#409EFF' },
      itemStyle: { color: '#409EFF' },
      areaStyle: {
        color: {
          type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(64,158,255,0.25)' },
            { offset: 1, color: 'rgba(64,158,255,0.02)' },
          ]
        }
      },
      markLine: avgPrice > 0 ? {
        silent: true,
        symbol: 'none',
        lineStyle: { type: 'dashed', color: '#E6A23C', width: 1 },
        data: [{ yAxis: avgPrice, label: { formatter: `均值 ${avgPrice.toFixed(2)}`, fontSize: 9, color: '#E6A23C' } }],
      } : undefined,
    }]
  }
}

// ========== 格式化 ==========
function formatMoney(v) {
  if (!v) return '0'
  return Number(v).toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 0 })
}

// ========== 初始化 ==========
onMounted(() => { loadTopTrends() })
</script>

<style scoped>
.price-trend { padding: 0; }

.filter-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #fff;
  padding: 16px 20px;
  border-radius: 8px;
  margin-bottom: 16px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
  flex-wrap: wrap;
  gap: 12px;
}
.filter-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  display: flex;
  align-items: center;
  gap: 8px;
}
.filter-controls {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}

.search-card { margin-bottom: 16px; }
.search-header { display: flex; align-items: center; justify-content: space-between; }
.search-left { display: flex; align-items: center; gap: 8px; }
.search-title { font-size: 16px; font-weight: 600; color: #303133; }

.search-item { display: flex; align-items: center; gap: 8px; width: 100%; }
.search-code { font-family: monospace; color: #409EFF; font-weight: 500; min-width: 80px; }
.search-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.search-amt { color: #909399; font-size: 12px; white-space: nowrap; }

/* 自定义图表卡片 */
.custom-chart-card { margin-bottom: 16px; border-left: 3px solid #E6A23C; }
.chart-card-header { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.chart-title-area { display: flex; align-items: center; gap: 6px; flex: 1; min-width: 0; }
.chart-title { font-size: 15px; font-weight: 600; color: #303133; }
.chart-subtitle { font-size: 12px; color: #909399; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.chart-stats { display: flex; gap: 16px; font-size: 13px; color: #606266; }
.chart-stats b { color: #303133; }

/* 区块标题 */
.section-header { display: flex; align-items: center; gap: 8px; margin: 20px 0 12px; flex-wrap: wrap; }
.section-title { font-size: 15px; font-weight: 600; color: #303133; }

/* 图表网格 - 2列 */
.chart-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.chart-card { min-width: 0; }
.chart-card :deep(.el-card__header) { padding: 10px 14px; }
.chart-card :deep(.el-card__body) { padding: 8px 12px 12px; }

.mini-header { display: flex; justify-content: space-between; align-items: center; }
.mini-title { display: flex; align-items: center; gap: 6px; min-width: 0; flex: 1; }
.rank-badge {
  display: inline-flex; align-items: center; justify-content: center;
  width: 22px; height: 22px; border-radius: 4px; font-size: 11px; font-weight: 700;
  background: #ecf5ff; color: #409EFF; flex-shrink: 0;
}
.chart-card:nth-child(-n+3) .rank-badge { background: #fdf6ec; color: #E6A23C; }
.mini-name { font-size: 13px; font-weight: 500; color: #303133; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* 卡片滚动控制条 */
.card-scroll-bar {
  display: flex; align-items: center; gap: 6px; margin-top: 8px;
  justify-content: flex-start;
  padding-top: 8px;
  border-top: 1px dashed #ebeef5;
}
.card-scroll-bar :deep(.el-button) { padding: 2px 6px; font-size: 14px; }
.card-range-tag { font-size: 11px; padding: 0 6px; height: 20px; line-height: 20px; }
.reset-btn { font-size: 11px; padding: 2px 4px; }
.mini-amt { font-size: 12px; color: #909399; white-space: nowrap; margin-left: auto; }

.loading-area { padding: 20px 0; }

:deep(.el-card__body) { padding: 12px 16px; }
</style>
