<template>
  <div class="dashboard">
    <!-- 顶部筛选 -->
    <div class="filter-bar">
      <div class="filter-title">
        <el-icon><DataLine /></el-icon>
        <span>采购概览看板</span>
      </div>
      <div class="filter-controls">
        <el-select v-model="fiscalYear" placeholder="选择财年" style="width: 120px" @change="loadData">
          <el-option
            v-for="y in yearOptions"
            :key="y"
            :label="`${y}年`"
            :value="y"
          />
        </el-select>
        <OrgFilter ref="orgFilterRef" @change="onOrgFilterChange" />
        <MaterialFilter
          :company-codes="orgFilter.companyCodes"
          @change="onMaterialFilterChange"
        />
        <el-button type="primary" :icon="Refresh" @click="loadData" :loading="loading">刷新数据</el-button>
        <el-button type="success" plain @click="goPurchaseRecords">查看采购明细</el-button>
      </div>
    </div>

    <!-- KPI 卡片 -->
    <div class="kpi-row" v-if="kpis">
      <div class="kpi-card kpi-blue">
        <div class="kpi-label">采购总额 (CNY)</div>
        <div class="kpi-value">{{ formatMoney(kpis.total_cny) }}</div>
        <div class="kpi-extra">
          <span v-if="kpis.yoy" :class="kpis.yoy.yoy_rate >= 0 ? 'rate-up' : 'rate-down'">
            <el-icon>
              <CaretTop v-if="kpis.yoy.yoy_rate >= 0" />
              <CaretBottom v-else />
            </el-icon>
            {{ Math.abs(kpis.yoy.yoy_rate).toFixed(1) }}%
          </span>
          <span class="kpi-sub">{{ kpis.yoy?.warning || '较上一年' }}</span>
        </div>
      </div>

      <div class="kpi-card kpi-green">
        <div class="kpi-label">采购笔数</div>
        <div class="kpi-value">{{ kpis.order_count.toLocaleString() }}</div>
        <div class="kpi-extra">
          <span class="kpi-sub">单笔均价 {{ formatMoney(kpis.avg_per_order) }}</span>
        </div>
      </div>

      <div class="kpi-card kpi-orange">
        <div class="kpi-label">物料数 / 供应商数</div>
        <div class="kpi-value">{{ kpis.material_count.toLocaleString() }} / {{ kpis.supplier_count }}</div>
        <div class="kpi-extra">
          <span class="kpi-sub">
            <template v-if="orgFilter.companyName">{{ orgFilter.companyName }}</template>
            <template v-else-if="orgFilter.companyCodes.length > 0">已选 {{ orgFilter.companyCodes.length }} 家公司</template>
            <template v-else>覆盖 {{ kpis.company_count }} 家公司</template>
          </span>
        </div>
      </div>

      <div class="kpi-card kpi-purple">
        <div class="kpi-label">订单币种</div>
        <div class="kpi-value">{{ kpis.currency_count }}</div>
        <div class="kpi-extra">
          <span class="kpi-sub">含 CNY / IDR / USD / SGD / JPY</span>
        </div>
      </div>
    </div>

    <!-- 第一行：月度趋势 + 事业部占比 -->
    <el-row :gutter="20" class="chart-row">
      <el-col :xs="24" :lg="24">
        <div class="chart-card">
          <div class="chart-header">
            <h3>月度采购趋势（CNY）</h3>
            <span class="sub">柱形=金额 / 折线=笔数</span>
          </div>
          <v-chart :option="monthlyOption" autoresize style="height: 360px" />
        </div>
      </el-col>
    </el-row>

    <!-- 第二行：组织下钻占比 + 物料类别分布 -->
    <el-row :gutter="20" class="chart-row">
      <el-col :xs="24" :lg="14">
        <div class="chart-card">
          <OrgDrillChart
            :filters="drillChartFilters"
            :org-hierarchy="orgHierarchyData"
            :user-company-codes="userCompanyCodes"
          />
        </div>
      </el-col>
      <el-col :xs="24" :lg="10">
        <div class="chart-card">
          <div class="chart-header">
            <h3>物料类别分布（CNY）</h3>
            <span class="sub">WGBEZ 中文名称</span>
          </div>
          <v-chart :option="categoryOption" autoresize style="height: 420px" />
        </div>
      </el-col>
    </el-row>

    <!-- 第三行：物料大类分布（环形图） -->
    <el-row :gutter="20" class="chart-row">
      <el-col :span="24">
        <div class="chart-card">
          <div class="chart-header">
            <h3>物料大类分布（CNY）</h3>
            <span class="sub">来自物料大类维护表</span>
          </div>
          <v-chart :option="majorCategoryOption" autoresize style="height: 420px" />
        </div>
      </el-col>
    </el-row>

    <!-- 第四行：供应商 TOP + 物料 TOP -->
    <el-row :gutter="20" class="chart-row">
      <el-col :xs="24" :lg="12">
        <div class="chart-card">
          <div class="chart-header">
            <h3>供应商 TOP 10（CNY）</h3>
            <span class="sub">点击供应商查看其前十大物料</span>
          </div>
          <v-chart
            :option="supplierOption"
            autoresize
            style="height: 440px"
            @click="handleSupplierClick"
          />
        </div>
      </el-col>
      <el-col :xs="24" :lg="12">
        <div class="chart-card">
          <div class="chart-header">
            <h3>物料 TOP 10（CNY）</h3>
            <span class="sub">点击物料查看其前十大供应商</span>
          </div>
          <v-chart
            :option="materialOption"
            autoresize
            style="height: 440px"
            @click="handleMaterialClick"
          />
        </div>
      </el-col>
    </el-row>


    <!-- 采购用途 + 公司月度热力图 -->
    <el-row :gutter="20" class="chart-row">
      <el-col :xs="24" :lg="10">
        <div class="chart-card">
          <div class="chart-header">
            <h3>采购用途分布（CNY）</h3>
            <span class="sub">purchase_purpose</span>
          </div>
          <v-chart :option="purposeOption" autoresize style="height: 400px" />
        </div>
      </el-col>
      <el-col :xs="24" :lg="14">
        <div class="chart-card">
          <div class="chart-header">
            <h3>公司 × 月度热力图（CNY）</h3>
            <span class="sub">金额深浅表示采购规模</span>
          </div>
          <v-chart :option="companyMonthOption" autoresize style="height: 400px" />
        </div>
      </el-col>
    </el-row>

    <!-- 供应商下钻弹窗 -->
    <el-dialog v-model="supplierDrillVisible" :title="`供应商：${supplierDrillName} — 前十大物料`" width="700px">
      <el-table :data="supplierDrillData" stripe size="small" v-loading="supplierDrillLoading">
        <el-table-column type="index" label="排名" width="60" align="center" />
        <el-table-column label="物料编码" width="120">
          <template #default="{ row }">{{ stripLeadingZeros(row.material_code) }}</template>
        </el-table-column>
        <el-table-column prop="material_name" label="物料名称" min-width="280" show-overflow-tooltip />
        <el-table-column prop="amount_cny" label="采购金额 (CNY)" width="160" align="right">
          <template #default="{ row }">{{ formatMoney(row.amount_cny) }}</template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!-- 物料下钻弹窗 -->
    <el-dialog v-model="materialDrillVisible" :title="`物料：${stripLeadingZeros(materialDrillCode)} — 供应商分析`" width="780px">
      <el-tabs v-model="materialDrillActiveTab" @tab-change="onMaterialDrillTabChange">
        <el-tab-pane label="前十大供应商" name="suppliers">
          <el-table :data="materialDrillData" stripe size="small" v-loading="materialDrillLoading">
            <el-table-column type="index" label="排名" width="60" align="center" />
            <el-table-column prop="supplier_name" label="供应商名称" min-width="360" show-overflow-tooltip />
            <el-table-column prop="amount_cny" label="采购金额 (CNY)" width="160" align="right">
              <template #default="{ row }">{{ formatMoney(row.amount_cny) }}</template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="供应商比价" name="comparison">
          <div v-loading="priceComparisonLoading">
            <template v-if="priceComparisonData">
              <div class="comparison-summary">
                <div class="cmp-card">
                  <div class="cmp-label">加权均价</div>
                  <div class="cmp-value">{{ formatNum(priceComparisonData.avg_price) }}</div>
                </div>
                <div class="cmp-card">
                  <div class="cmp-label">最低均价</div>
                  <div class="cmp-value" style="color:#67c23a">{{ formatNum(priceComparisonData.min_price) }}</div>
                </div>
                <div class="cmp-card">
                  <div class="cmp-label">供应商数</div>
                  <div class="cmp-value">{{ priceComparisonData.suppliers?.length || 0 }}</div>
                </div>
                <div class="cmp-card">
                  <div class="cmp-label">降本潜力</div>
                  <div class="cmp-value" style="color:#E6A23C">{{ formatMoney(priceComparisonData.savings_potential) }}</div>
                </div>
              </div>
              <el-table :data="priceComparisonData.suppliers || []" stripe size="small">
                <el-table-column prop="supplier_name" label="供应商" min-width="200" show-overflow-tooltip />
                <el-table-column prop="quantity" label="采购量" width="110" align="right">
                  <template #default="{ row }">{{ formatNum(row.quantity) }}</template>
                </el-table-column>
                <el-table-column prop="amount_cny" label="金额(CNY)" width="130" align="right">
                  <template #default="{ row }">{{ formatMoney(row.amount_cny) }}</template>
                </el-table-column>
                <el-table-column prop="avg_price" label="均价" width="110" align="right">
                  <template #default="{ row }">{{ formatNum(row.avg_price) }}</template>
                </el-table-column>
                <el-table-column prop="price_vs_avg" label="vs均价" width="100" align="center">
                  <template #default="{ row }">
                    <span :style="{ color: row.price_vs_avg > 0 ? '#f56c6c' : '#67c23a', fontWeight: 600 }">
                      {{ row.price_vs_avg > 0 ? '+' : '' }}{{ row.price_vs_avg }}%
                    </span>
                  </template>
                </el-table-column>
                <el-table-column prop="last_purchase_date" label="最近采购" width="110" align="center" />
              </el-table>
            </template>
            <el-empty v-else description="点击后加载比价数据" />
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-dialog>
  </div>
</template>

<script setup>
const router = useRouter()
import { ref, computed, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import {
  BarChart,
  LineChart,
  PieChart,
  HeatmapChart
} from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  VisualMapComponent
} from 'echarts/components'
import VChart from 'vue-echarts'
import { Refresh, CaretTop, CaretBottom, DataLine, Calendar } from '@element-plus/icons-vue'
import { getYears } from '../api/yoy'
import { getDashboardFull, getMajorCategoryDistribution, getSupplierDrill, getMaterialDrill, getSupplierPriceComparison } from '../api/dashboard'
import { getOrgHierarchy } from '../api/org'
import { getMe } from '../api/auth'
import OrgFilter from '../components/OrgFilter.vue'
import OrgDrillChart from '../components/OrgDrillChart.vue'
import MaterialFilter from '../components/MaterialFilter.vue'
import { stripLeadingZeros } from '../utils/format'

use([
  CanvasRenderer,
  BarChart,
  LineChart,
  PieChart,
  HeatmapChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  VisualMapComponent
])

const fiscalYear = ref(null)
const yearOptions = ref([])
const loading = ref(false)
const kpis = ref(null)
const monthlyTrend = ref([])
const quarterly = ref([])
const companyComparison = ref([])
const topSuppliers = ref([])
const topMaterials = ref([])
const categoryDistribution = ref([])
const majorCategoryDistribution = ref([])
const purposeDistribution = ref([])
const companyMonthMatrix = ref({ companies: [], months: [], matrix: [] })

// 组织下钻图所需：组织层级 + 当前用户权限公司码
const orgHierarchyData = ref([])
const userCompanyCodes = ref([])

// 供应商比价分析
const priceComparisonData = ref(null)
const priceComparisonLoading = ref(false)

// 供应商/物料下钻状态
const supplierDrillVisible = ref(false)
const supplierDrillName = ref('')
const supplierDrillData = ref([])
const supplierDrillLoading = ref(false)
const materialDrillVisible = ref(false)
const materialDrillCode = ref('')
const materialDrillData = ref([])
const materialDrillLoading = ref(false)
const materialDrillActiveTab = ref('suppliers')

// 组织筛选状态
const orgFilterRef = ref(null)
const orgFilter = reactive({
  level: 'all',
  companyCodes: [],
  companyName: ''
})

// 物料筛选状态
const materialFilter = reactive({
  materialCode: '',
  materialKeyword: '',
  majorCategory: ''
})

function onOrgFilterChange(payload) {
  orgFilter.level = payload.level
  orgFilter.companyCodes = payload.companyCodes || []
  orgFilter.companyName = payload.companyName || ''
  loadData()
}

function onMaterialFilterChange(payload) {
  materialFilter.materialCode = payload.materialCode || ''
  materialFilter.materialKeyword = payload.materialKeyword || ''
  materialFilter.majorCategory = payload.majorCategory || ''
  loadData()
}

async function loadData() {
  if (!fiscalYear.value) return
  loading.value = true
  try {
    // 构建通用过滤参数
    const filters = {
      fiscalYear: fiscalYear.value,
      companyName: orgFilter.companyName || undefined,
      companyCodes: orgFilter.companyCodes.length > 0 ? orgFilter.companyCodes : undefined,
      materialCode: materialFilter.materialCode || undefined,
      materialKeyword: materialFilter.materialKeyword || undefined,
      majorCategory: materialFilter.majorCategory || undefined
    }

    // 一次性加载所有 Dashboard 数据（带过滤）
    const baseRes = await getDashboardFull(filters)
    kpis.value = baseRes.kpis
    monthlyTrend.value = baseRes.monthly_trend
    quarterly.value = baseRes.quarterly
    companyComparison.value = baseRes.company_comparison
    topSuppliers.value = baseRes.top_suppliers
    topMaterials.value = baseRes.top_materials
    categoryDistribution.value = baseRes.category_distribution
    purposeDistribution.value = baseRes.purpose_distribution || []
    companyMonthMatrix.value = baseRes.company_month_matrix || { companies: [], months: [], matrix: [] }

    // 加载物料大类分布（独立请求）
    try {
      majorCategoryDistribution.value = await getMajorCategoryDistribution(filters)
    } catch (e) {
      console.error('加载物料大类分布失败:', e)
      majorCategoryDistribution.value = []
    }
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}


function goPurchaseRecords() {
  const query = {}
  if (fiscalYear.value) query.fiscal_year = String(fiscalYear.value)
  if (orgFilter.companyCodes?.length) query.company_codes = orgFilter.companyCodes.join(',')
  if (materialFilter.materialCode) query.material_code = materialFilter.materialCode
  else if (materialFilter.materialKeyword) query.material_keyword = materialFilter.materialKeyword
  router.push({ path: '/purchase-records', query })
}

onMounted(async () => {
  try {
    // 1) 加载当前用户权限公司码（OrgDrillChart 用它判定起点）
    await loadUserCompanyCodes()
    // 2) 加载组织层级（OrgFilter 和 OrgDrillChart 都需要）
    await loadOrgHierarchy()
    // 3) 加载财年
    const res = await getYears()
    yearOptions.value = res
    if (res && res.length > 0) {
      fiscalYear.value = res[0]
    }
    // 等 OrgFilter 组件加载完层级数据后，会通过 @change 触发 loadData
    setTimeout(() => {
      if (!kpis.value) loadData()
    }, 800)
  } catch (e) {
    console.error(e)
  }
})

// 加载当前用户的公司权限码（用于 OrgDrillChart 起点判定）
async function loadUserCompanyCodes() {
  try {
    // 优先从 localStorage 读（登录时已缓存）
    const cached = JSON.parse(localStorage.getItem('pp_user') || '{}')
    if (cached.company_codes && Array.isArray(cached.company_codes)) {
      userCompanyCodes.value = cached.role === 'admin' ? [] : cached.company_codes
      return
    }
    // 兜底：实时拉 /auth/me
    const me = await getMe()
    userCompanyCodes.value = me.role === 'admin' ? [] : (me.company_codes || [])
    localStorage.setItem('pp_user', JSON.stringify(me))
  } catch (e) {
    console.error('加载用户公司权限失败:', e)
    userCompanyCodes.value = []
  }
}

// 加载组织层级树
async function loadOrgHierarchy() {
  try {
    orgHierarchyData.value = await getOrgHierarchy()
  } catch (e) {
    console.error('加载组织层级失败:', e)
    orgHierarchyData.value = []
  }
}

// ============ 供应商/物料下钻 ============
async function handleSupplierClick(params) {
  const supplierName = params.name
  if (!supplierName) return
  supplierDrillName.value = supplierName
  supplierDrillVisible.value = true
  supplierDrillLoading.value = true
  try {
    const filters = {
      fiscalYear: fiscalYear.value,
      companyCodes: orgFilter.companyCodes.length > 0 ? orgFilter.companyCodes : undefined,
    }
    supplierDrillData.value = await getSupplierDrill(supplierName, filters)
  } catch (e) {
    console.error('供应商下钻失败:', e)
    supplierDrillData.value = []
  } finally {
    supplierDrillLoading.value = false
  }
}

async function handleMaterialClick(params) {
  // 通过 dataIndex 直接从排序后的数据取物料编码，避免依赖 y 轴标签字符串匹配
  const dataIndex = params?.dataIndex
  if (dataIndex == null || dataIndex < 0) return
  const sorted = sortedTopMaterials.value
  const material = sorted[dataIndex]
  if (!material) return
  const materialCode = material.material_code
  if (!materialCode) return
  materialDrillCode.value = materialCode
  materialDrillActiveTab.value = 'suppliers'
  materialDrillVisible.value = true
  materialDrillLoading.value = true
  priceComparisonData.value = null
  try {
    const filters = {
      fiscalYear: fiscalYear.value,
      companyCodes: orgFilter.companyCodes.length > 0 ? orgFilter.companyCodes : undefined,
    }
    materialDrillData.value = await getMaterialDrill(materialCode, filters)
  } catch (e) {
    console.error('物料下钻失败:', e)
    materialDrillData.value = []
  } finally {
    materialDrillLoading.value = false
  }
}

async function loadPriceComparison(materialCode) {
  priceComparisonLoading.value = true
  try {
    const filters = {
      fiscalYear: fiscalYear.value,
      companyCodes: orgFilter.companyCodes.length > 0 ? orgFilter.companyCodes : undefined,
    }
    priceComparisonData.value = await getSupplierPriceComparison(materialCode, filters)
  } catch (e) {
    console.error('加载比价分析失败:', e)
    priceComparisonData.value = null
  } finally {
    priceComparisonLoading.value = false
  }
}

function onMaterialDrillTabChange(tab) {
  if (tab === 'comparison' && materialDrillCode.value && !priceComparisonData.value) {
    loadPriceComparison(materialDrillCode.value)
  }
}

// OrgDrillChart 的过滤参数：同步 Dashboard 顶部 OrgFilter + 财年 + 物料筛选
const drillChartFilters = computed(() => ({
  fiscalYear: fiscalYear.value,
  companyName: orgFilter.companyName || undefined,
  companyCodes: orgFilter.companyCodes.length > 0 ? orgFilter.companyCodes : undefined,
  materialCode: materialFilter.materialCode || undefined,
  materialKeyword: materialFilter.materialKeyword || undefined,
  majorCategory: materialFilter.majorCategory || undefined
}))

// ============ 工具函数 ============
function formatMoney(v) {
  if (v === null || v === undefined) return '0'
  if (Math.abs(v) >= 1e8) return (v / 1e8).toFixed(2) + ' 亿'
  if (Math.abs(v) >= 1e4) return (v / 1e4).toFixed(2) + ' 万'
  return Number(v).toFixed(2)
}
function formatNum(v) {
  if (v === null || v === undefined) return '0'
  return Number(v).toLocaleString('zh-CN', { maximumFractionDigits: 4 })
}

// ============ ECharts 配置 ============
// containLabel:true 让 ECharts 自动留出 Y/X 轴刻度和名称的空间，避免缩放后被挤压重叠
const COMMON_GRID = { left: 60, right: 30, top: 60, bottom: 50, containLabel: true }
const COMMON_TOOLTIP = { trigger: 'axis', axisPointer: { type: 'shadow' } }

const monthlyOption = computed(() => {
  const months = monthlyTrend.value.map(m => m.month_name)
  const amounts = monthlyTrend.value.map(m => m.amount_cny)
  const counts = monthlyTrend.value.map(m => m.order_count)
  return {
    tooltip: COMMON_TOOLTIP,
    legend: { data: ['采购金额 (CNY)', '采购笔数'], top: 15 },
    grid: { ...COMMON_GRID, top: 60 },
    xAxis: { type: 'category', data: months, axisLine: { lineStyle: { color: '#aaa' } } },
    yAxis: [
      {
        type: 'value',
        name: '金额(元)',
        nameLocation: 'end',
        nameGap: 12,
        nameTextStyle: { padding: [0, 0, 4, -10] },
        axisLabel: { formatter: v => formatMoney(v) }
      },
      {
        type: 'value',
        name: '笔数',
        nameLocation: 'end',
        nameGap: 12,
        nameTextStyle: { padding: [0, -10, 4, 0] },
        splitLine: { show: false }
      }
    ],
    series: [
      {
        name: '采购金额 (CNY)',
        type: 'bar',
        data: amounts,
        itemStyle: { color: '#5470c6', borderRadius: [4, 4, 0, 0] },
        barWidth: '45%'
      },
      {
        name: '采购笔数',
        type: 'line',
        yAxisIndex: 1,
        data: counts,
        smooth: true,
        symbol: 'circle',
        symbolSize: 8,
        lineStyle: { color: '#ee6666', width: 3 },
        itemStyle: { color: '#ee6666' }
      }
    ]
  }
})

// 物料类别分布：WGBEZ 中文名称，加大图例区域防止重叠
const categoryOption = computed(() => {
  const data = categoryDistribution.value.slice(0, 15).map(c => ({
    name: c.category,
    value: c.amount_cny
  }))
  const total = data.reduce((s, x) => s + x.value, 0)
  return {
    tooltip: {
      trigger: 'item',
      formatter: p => `${p.name}<br/>${formatMoney(p.value)} 元 (${p.percent}%)`
    },
    legend: {
      type: 'scroll',
      orient: 'vertical',
      right: 5,
      top: 50,
      bottom: 20,
      itemWidth: 12,
      itemHeight: 12,
      itemGap: 8,
      textStyle: { fontSize: 12, lineHeight: 16 }
    },
    series: [{
      name: '物料类别',
      type: 'pie',
      radius: ['40%', '68%'],
      center: ['35%', '50%'],
      avoidLabelOverlap: false,
      itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
      label: { show: false },
      emphasis: {
        label: { show: true, fontSize: 14, fontWeight: 'bold' },
        scaleSize: 10
      },
      data
    }]
  }
})

// 物料大类分布（来自维护表）：环形面积图
const majorCategoryOption = computed(() => {
  const data = (majorCategoryDistribution.value || []).slice(0, 15).map(d => ({
    name: d.major_category || d.category || '未维护',
    value: d.amount_cny || d.amt || 0,
    order_count: d.order_count || d.cnt || 0,
    material_count: d.material_count || d.mat_cnt || 0
  }))
  return {
    tooltip: {
      trigger: 'item',
      formatter: p => {
        const d = data[p.dataIndex]
        return `<b>${p.name}</b><br/>金额: ${formatMoney(p.value)} 元 (${p.percent}%)<br/>采购笔数: ${d.order_count}<br/>物料数: ${d.material_count}`
      }
    },
    legend: {
      type: 'scroll',
      orient: 'vertical',
      right: 20,
      top: 30,
      bottom: 30,
      itemWidth: 14,
      itemHeight: 14,
      textStyle: { fontSize: 12, lineHeight: 18 }
    },
    series: [{
      name: '物料大类',
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['38%', '50%'],
      avoidLabelOverlap: true,
      itemStyle: {
        borderRadius: 8,
        borderColor: '#fff',
        borderWidth: 2,
        color: (params) => {
          const colors = ['#5B8FF9', '#5AD8A6', '#5D7092', '#F6BD16', '#E86452',
                          '#6DC8EC', '#945FB9', '#FF9845', '#1E9493', '#FF99C3',
                          '#7C7C7C', '#B5E7A0', '#F4A261', '#A8DADC', '#457B9D']
          return colors[params.dataIndex % colors.length]
        }
      },
      // 智能标签：占比 ≥5% 显示名称+百分比，否则只显示百分比；自动隐藏重叠标签
      label: {
        show: true,
        formatter: (p) => (p.percent >= 5 ? `{b|${p.name}}\n{d|${p.percent}%}` : `{d|${p.percent}%}`),
        rich: {
          b: { fontSize: 12, color: '#303133', lineHeight: 16 },
          d: { fontSize: 11, color: '#909399' }
        }
      },
      labelLine: { length: 12, length2: 8 },
      labelLayout: { hideOverlap: true },
      emphasis: {
        label: { show: true, fontSize: 14, fontWeight: 'bold' },
        itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0, 0, 0, 0.2)' }
      },
      data
    }]
  }
})

// 物料 TOP10：已排序的物料数据（给图表和点击事件共用）
const sortedTopMaterials = computed(() => {
  const top = topMaterials.value.slice(0, 10)
  return [...top].sort((a, b) => a.amount_cny - b.amount_cny)
})

const supplierOption = computed(() => {
  const top = topSuppliers.value.slice(0, 10)
  const sorted = [...top].sort((a, b) => a.amount_cny - b.amount_cny)
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, formatter: '{b}<br/>{c} 元' },
    // containLabel 自动避让左侧长供应商名和右侧数值标签，避免缩放后被截断
    grid: { left: 10, right: 20, top: 20, bottom: 20, containLabel: true },
    xAxis: { type: 'value', axisLabel: { formatter: v => formatMoney(v) } },
    yAxis: { type: 'category', data: sorted.map(d => d.supplier_name), axisLabel: { width: 180, overflow: 'truncate', lineHeight: 16 } },
    series: [{
      name: '采购金额', type: 'bar',
      data: sorted.map(d => d.amount_cny),
      itemStyle: {
        color: (params) => {
          const colors = ['#5B8FF9', '#5AD8A6', '#5D7092', '#F6BD16', '#E86452',
                          '#6DC8EC', '#945FB9', '#FF9845', '#1E9493', '#FF99C3']
          return colors[params.dataIndex % colors.length]
        },
        borderRadius: [0, 4, 4, 0]
      },
      label: { show: true, position: 'right', formatter: p => formatMoney(p.value) },
      cursor: 'pointer'
    }]
  }
})

const materialOption = computed(() => {
  const sorted = sortedTopMaterials.value
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, formatter: p => {
      const d = sorted[p.dataIndex]
      if (!d) return ''
      return `<b>${d.material_name}</b><br/>${stripLeadingZeros(d.material_code)}<br/>${formatMoney(d.amount_cny)} 元`
    } },
    grid: { left: 10, right: 20, top: 20, bottom: 20, containLabel: true },
    xAxis: { type: 'value', axisLabel: { formatter: v => formatMoney(v) } },
    yAxis: { type: 'category', data: sorted.map(d => d.material_name), axisLabel: { width: 180, overflow: 'truncate', lineHeight: 16 } },
    series: [{
      name: '采购金额', type: 'bar',
      data: sorted.map(d => d.amount_cny),
      itemStyle: { color: '#5470c6', borderRadius: [0, 4, 4, 0] },
      label: { show: true, position: 'right', formatter: p => formatMoney(p.value) },
      cursor: 'pointer'
    }]
  }
})

// 采购用途分布
const purposeOption = computed(() => {
  const data = (purposeDistribution.value || []).map(d => ({
    name: d.purpose || '未指定',
    value: d.amount_cny || 0,
  }))
  return {
    tooltip: {
      trigger: 'item',
      formatter: p => `${p.name}<br/>${formatMoney(p.value)} 元 (${p.percent}%)`
    },
    legend: {
      type: 'scroll',
      orient: 'vertical',
      right: 5,
      top: 40,
      bottom: 20,
      textStyle: { fontSize: 12 }
    },
    series: [{
      name: '采购用途',
      type: 'pie',
      radius: ['38%', '65%'],
      center: ['35%', '50%'],
      itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
      label: { show: false },
      emphasis: { label: { show: true, fontSize: 13, fontWeight: 'bold' } },
      data
    }]
  }
})

// 公司 × 月度热力图
const companyMonthOption = computed(() => {
  const mat = companyMonthMatrix.value || { companies: [], months: [], matrix: [] }
  const companies = mat.companies || []
  const months = (mat.months || []).map(m => `${m}月`)
  const values = (mat.matrix || []).map(cell => [
    (cell.month || 1) - 1,
    companies.indexOf(cell.company),
    cell.amount_cny || 0,
  ]).filter(d => d[1] >= 0)
  const maxVal = values.reduce((m, d) => Math.max(m, d[2]), 0) || 1
  return {
    tooltip: {
      position: 'top',
      formatter: p => {
        const company = companies[p.value[1]] || ''
        const month = months[p.value[0]] || ''
        return `${company}<br/>${month}: ${formatMoney(p.value[2])} 元`
      }
    },
    grid: { left: 10, right: 40, top: 20, bottom: 40, containLabel: true },
    xAxis: { type: 'category', data: months, splitArea: { show: true } },
    yAxis: {
      type: 'category',
      data: companies,
      axisLabel: { width: 140, overflow: 'truncate', fontSize: 11 }
    },
    visualMap: {
      min: 0,
      max: maxVal,
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      inRange: { color: ['#f0f5ff', '#5470c6', '#1a3a8a'] },
      text: ['高', '低'],
      formatter: v => formatMoney(v)
    },
    series: [{
      name: '采购金额',
      type: 'heatmap',
      data: values,
      label: { show: false },
      emphasis: { itemStyle: { shadowBlur: 8, shadowColor: 'rgba(0,0,0,0.3)' } }
    }]
  }
})

</script>

<style scoped>
.dashboard {
  padding: 20px;
  background: #f5f7fa;
  min-height: calc(100vh - 60px);
}

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
  font-size: 18px;
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
.data-range {
  font-size: 12px;
  color: #606266;
  background: #f0f9ff;
  border: 1px solid #bae6fd;
  padding: 4px 10px;
  border-radius: 4px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.kpi-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}
.kpi-card {
  padding: 20px;
  border-radius: 8px;
  color: #fff;
  position: relative;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}
.kpi-blue { background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); }
.kpi-green { background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%); }
.kpi-orange { background: linear-gradient(135deg, #fa709a 0%, #fee140 100%); }
.kpi-purple { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }

.kpi-label {
  font-size: 13px;
  opacity: 0.9;
  margin-bottom: 8px;
}
.kpi-value {
  font-size: 26px;
  font-weight: 700;
  margin-bottom: 8px;
  line-height: 1.2;
}
.kpi-extra {
  font-size: 12px;
  opacity: 0.95;
  display: flex;
  align-items: center;
  gap: 6px;
}
.kpi-sub {
  opacity: 0.85;
  font-size: 11px;
}
.rate-up {
  background: rgba(255, 255, 255, 0.25);
  padding: 2px 8px;
  border-radius: 10px;
  display: inline-flex;
  align-items: center;
  font-weight: 600;
}
.rate-down {
  background: rgba(255, 255, 255, 0.25);
  padding: 2px 8px;
  border-radius: 10px;
  display: inline-flex;
  align-items: center;
  font-weight: 600;
}

.chart-row {
  margin-bottom: 16px;
}
.chart-row :deep(.el-col) {
  display: flex;
  /* 关键：flex 子项默认 min-width:auto 会拒绝收缩到内容宽度以下，
     导致缩放后图表卡片互相挤压重叠。设为 0 强制按 flex 比例收缩 */
  min-width: 0;
}
.chart-row :deep(.el-col > .chart-card) {
  flex: 1;
  /* 同理，让卡片内部能正确收缩 */
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.chart-card {
  background: #fff;
  border-radius: 8px;
  padding: 16px 20px 20px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
  margin-bottom: 16px;
  /* v-chart 是 flex 子项，允许收缩避免溢出到相邻卡片 */
  min-width: 0;
}
.chart-card :deep(.vue-echarts) {
  width: 100%;
  min-width: 0;
}
.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid #ebeef5;
  /* 缩放时标题+副标题+按钮可能挤压，允许换行而非重叠 */
  flex-wrap: wrap;
}
.chart-header h3 {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  margin: 0;
}
.chart-header .sub {
  font-size: 12px;
  color: #909399;
}

.comparison-summary {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}
.cmp-card {
  background: #f5f7fa;
  border-radius: 8px;
  padding: 12px 16px;
  text-align: center;
}
.cmp-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}
.cmp-value {
  font-size: 18px;
  font-weight: 700;
  color: #303133;
}

@media (max-width: 1200px) {
  .kpi-row {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
