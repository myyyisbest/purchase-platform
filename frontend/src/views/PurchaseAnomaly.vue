<template>
  <div class="anomaly-page">
    <!-- 顶部筛选 -->
    <div class="filter-bar">
      <div class="filter-title">
        <el-icon><Warning /></el-icon>
        <span>采购异常监测</span>
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
      </div>
    </div>

    <!-- 单源供应风险清单 -->
    <div class="chart-card" v-if="singleSourceRisk.length > 0">
      <div class="chart-header">
        <h3><el-icon color="#E6A23C" style="margin-right:6px"><Warning /></el-icon>单源供应风险清单</h3>
        <span class="sub">仅 1 个供应商的物料，按采购金额排序（{{ singleSourceRisk.length }} 条）</span>
        <div style="margin-left: auto; display: flex; align-items: center; gap: 12px;">
          <el-button size="small" type="success" plain @click="exportSingleSourceRisk" :disabled="singleSourceRisk.length === 0">
            <el-icon><Download /></el-icon> 导出 Excel
          </el-button>
        </div>
      </div>
      <el-table :data="singleSourceRisk" stripe size="small" max-height="420" v-loading="singleSourceLoading">
        <el-table-column type="index" label="#" width="50" align="center" />
        <el-table-column label="物料编码" width="120">
          <template #default="{ row }">
            <el-link type="primary" @click="goRecordsByMaterial(row.material_code)">{{ stripLeadingZeros(row.material_code) }}</el-link>
          </template>
        </el-table-column>
        <el-table-column prop="material_name" label="物料名称" min-width="200" show-overflow-tooltip />
        <el-table-column prop="supplier_name" label="唯一供应商" min-width="200" show-overflow-tooltip />
        <el-table-column prop="amount_cny" label="采购金额 (CNY)" width="150" align="right" sortable>
          <template #default="{ row }">{{ formatMoney(row.amount_cny) }}</template>
        </el-table-column>
        <el-table-column label="风险等级" width="100" align="center">
          <template #default>
            <el-tag type="danger" size="small" effect="dark">高风险</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 物料单价波动监控 -->
    <div class="chart-card">
      <div class="chart-header">
        <h3>物料单价波动监控</h3>
        <span class="sub">按订单货币维度同比，{{ filteredVolatility.length }} 条异常（阈值 ±{{ volatilityThreshold }}%）</span>
        <div style="margin-left: auto; display: flex; align-items: center; gap: 12px;">
          <el-input-number
            v-model="volatilityThreshold"
            :min="1"
            :max="200"
            :step="5"
            size="small"
            style="width: 130px"
            controls-position="right"
          />
          <el-button size="small" type="success" plain @click="exportVolatility" :disabled="filteredVolatility.length === 0">
            <el-icon><Download /></el-icon> 导出表格
          </el-button>
        </div>
      </div>
      <el-table
        :data="filteredVolatility"
        stripe
        size="default"
        max-height="500"
        v-loading="volatilityLoading"
      >
        <el-table-column label="物料代码" width="110">
          <template #default="{ row }">{{ stripLeadingZeros(row.material_code) }}</template>
        </el-table-column>
        <el-table-column prop="material_name" label="物料名称" min-width="220" show-overflow-tooltip />
        <el-table-column prop="currency" label="币种" width="70" align="center" />
        <el-table-column prop="previous_avg_price" label="对比年均价" width="120" align="right">
          <template #default="{ row }">{{ formatNum(row.previous_avg_price) }}</template>
        </el-table-column>
        <el-table-column prop="current_avg_price" label="本年均价" width="120" align="right">
          <template #default="{ row }">{{ formatNum(row.current_avg_price) }}</template>
        </el-table-column>
        <el-table-column prop="change_rate" label="变化率" width="160" align="center" sortable>
          <template #default="{ row }">
            <div :class="['change-cell', row.change_rate >= 0 ? 'up' : 'down']">
              <el-icon>
                <CaretTop v-if="row.change_rate >= 0" />
                <CaretBottom v-else />
              </el-icon>
              <span style="margin-left:4px">{{ Math.abs(row.change_rate).toFixed(1) }}%</span>
            </div>
            <el-progress
              :percentage="Math.min(Math.abs(row.change_rate), 100)"
              :color="row.change_rate >= 0 ? '#f56c6c' : '#67c23a'"
              :show-text="false"
              :stroke-width="4"
              style="margin-top: 4px"
            />
          </template>
        </el-table-column>
        <el-table-column prop="current_amount" label="本年金额(CNY)" width="140" align="right" sortable>
          <template #default="{ row }">{{ formatMoney(row.current_amount) }}</template>
        </el-table-column>
        <el-table-column prop="current_count" label="笔数" width="70" align="center" />
        <el-table-column prop="compare_year" label="对比年" width="80" align="center" />
      </el-table>
    </div>
  </div>
</template>

<script setup>
const router = useRouter()
import { ref, computed, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Refresh, CaretTop, CaretBottom, Download, Warning } from '@element-plus/icons-vue'
import { getYears } from '../api/yoy'
import { getSingleSourceRisk, getPriceVolatility } from '../api/dashboard'
import { exportSingleSourceRiskExcel } from '../api/dashboard'
import OrgFilter from '../components/OrgFilter.vue'
import MaterialFilter from '../components/MaterialFilter.vue'
import { stripLeadingZeros } from '../utils/format'

const fiscalYear = ref(null)
const yearOptions = ref([])
const loading = ref(false)

// 单源供应风险
const singleSourceRisk = ref([])
const singleSourceLoading = ref(false)

// 单价波动
const priceVolatility = ref([])
const volatilityLoading = ref(false)
const volatilityThreshold = ref(30)

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

// 根据阈值过滤后的波动数据
const filteredVolatility = computed(() => {
  const threshold = volatilityThreshold.value
  return priceVolatility.value.filter(p => Math.abs(p.change_rate) >= threshold)
})

function buildFilters() {
  return {
    fiscalYear: fiscalYear.value,
    companyName: orgFilter.companyName || undefined,
    companyCodes: orgFilter.companyCodes.length > 0 ? orgFilter.companyCodes : undefined,
    materialCode: materialFilter.materialCode || undefined,
    materialKeyword: materialFilter.materialKeyword || undefined,
    majorCategory: materialFilter.majorCategory || undefined
  }
}

async function loadData() {
  if (!fiscalYear.value) return
  loading.value = true
  try {
    const filters = buildFilters()

    // 并行加载单源风险和单价波动
    const [riskRes, volRes] = await Promise.allSettled([
      getSingleSourceRisk(filters, 50),
      getPriceVolatility(filters, 200)
    ])

    singleSourceRisk.value = riskRes.status === 'fulfilled' ? (riskRes.value || []) : []
    priceVolatility.value = volRes.status === 'fulfilled'
      ? (volRes.value || []).map(p => ({ ...p, change_rate_abs: Math.abs(p.change_rate) }))
      : []
  } catch (e) {
    console.error('加载异常监测数据失败:', e)
  } finally {
    loading.value = false
  }
}


function goRecordsByMaterial(materialCode) {
  const query = { material_code: materialCode }
  if (fiscalYear.value) query.fiscal_year = String(fiscalYear.value)
  if (orgFilter.companyCodes?.length) query.company_codes = orgFilter.companyCodes.join(',')
  router.push({ path: '/purchase-records', query })
}

onMounted(async () => {
  try {
    const res = await getYears()
    yearOptions.value = res
    if (res && res.length > 0) {
      fiscalYear.value = res[0]
    }
    setTimeout(() => {
      if (singleSourceRisk.value.length === 0 && priceVolatility.value.length === 0) loadData()
    }, 800)
  } catch (e) {
    console.error(e)
  }
})

// 导出单源风险为 Excel
async function exportSingleSourceRisk() {
  try {
    const filters = buildFilters()
    const response = await exportSingleSourceRiskExcel(filters, 200)
    const blob = new Blob([response], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = `单源供应风险清单_${fiscalYear.value}.xlsx`
    link.click()
  } catch (e) {
    console.error('导出失败:', e)
  }
}

// 导出波动数据为CSV
function exportVolatility() {
  const headers = ['物料代码', '物料名称', '币种', '对比年均价', '本年均价', '变化率(%)', '本年金额(CNY)', '笔数', '对比年']
  const rows = filteredVolatility.value.map(p => [
    p.material_code, p.material_name, p.currency,
    p.previous_avg_price?.toFixed(4) || '', p.current_avg_price?.toFixed(4) || '',
    p.change_rate?.toFixed(2) || '', p.current_amount?.toFixed(2) || '',
    p.current_count || '', p.compare_year || ''
  ])
  const csvContent = '\uFEFF' + [headers, ...rows].map(r => r.map(c => `"${c}"`).join(',')).join('\n')
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = `物料单价波动_阈值${volatilityThreshold.value}%_${fiscalYear.value}.csv`
  link.click()
}

// 工具函数
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
</script>

<style scoped>
.anomaly-page {
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

.chart-card {
  background: #fff;
  border-radius: 8px;
  padding: 16px 20px 20px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
  margin-bottom: 16px;
}
.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid #ebeef5;
}
.chart-header h3 {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  margin: 0;
  display: flex;
  align-items: center;
}
.chart-header .sub {
  font-size: 12px;
  color: #909399;
}

.change-cell {
  display: inline-flex;
  align-items: center;
  font-weight: 600;
}
.change-cell.up { color: #f56c6c; }
.change-cell.down { color: #67c23a; }
</style>
