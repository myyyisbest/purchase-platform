<template>
  <div class="yoy-analysis">
    <!-- 筛选控制区 -->
    <el-card class="filter-card" shadow="never">
      <div class="filter-row">
        <div class="filter-item">
          <label class="filter-label">年份</label>
          <el-select v-model="currentYear" placeholder="选择年份" style="width: 120px" @change="onYearChange">
            <el-option v-for="y in years" :key="y" :label="y + '年'" :value="y" />
          </el-select>
        </div>
        <div class="filter-item">
          <label class="filter-label">截止月份</label>
          <el-select v-model="period" placeholder="选择月份" style="width: 120px">
            <el-option v-for="m in 12" :key="m" :label="m + '月'" :value="m" />
          </el-select>
        </div>
        <OrgFilter ref="orgFilterRef" @change="onOrgFilterChange" />
        <MaterialFilter
          :company-codes="orgFilter.companyCodes"
          @change="onMaterialFilterChange"
        />
        <el-button type="primary" :icon="Search" @click="doAnalyze" :loading="loading">
          查询分析
        </el-button>
        <el-button :icon="Download" @click="doExport" :disabled="!hasData" :loading="exporting">
          导出Excel
        </el-button>
      </div>
    </el-card>

    <!-- 汇总统计卡片 -->
    <div v-if="hasData" class="summary-row">
      <el-card class="summary-card" shadow="never">
        <div class="summary-title">物料组总数</div>
        <div class="summary-value">{{ summary.total_items }}</div>
      </el-card>
      <el-card class="summary-card current" shadow="never">
        <div class="summary-title">{{ currentYear }}年1-{{ period }}月金额(CNY)</div>
        <div class="summary-value">{{ formatMoney(summary.total_current_amount) }}</div>
      </el-card>
      <el-card class="summary-card prev" shadow="never">
        <div class="summary-title">{{ currentYear - 1 }}年全年金额(CNY)</div>
        <div class="summary-value">{{ formatMoney(summary.total_prev_amount) }}</div>
      </el-card>
      <el-card class="summary-card comparable" shadow="never">
        <div class="summary-title">可对比物料组</div>
        <div class="summary-value">{{ summary.comparable_count }}</div>
        <div class="summary-sub">
          <span class="price-down">单价下降 {{ summary.price_down_count }}组</span>
          <span class="price-up">单价上涨 {{ summary.price_up_count }}组</span>
        </div>
      </el-card>
      <el-card class="summary-card saving" shadow="never">
        <div class="summary-title">成本变动合计(CNY)</div>
        <div class="summary-value" :class="summary.total_cost_saving < 0 ? 'positive' : 'negative'">
          {{ formatMoney(summary.total_cost_saving) }}
        </div>
        <div class="summary-sub">{{ summary.total_cost_saving < 0 ? '成本节省' : '成本增加' }}</div>
      </el-card>
    </div>

    <!-- 数据表格 -->
    <el-card v-if="hasData" class="table-card" shadow="never">
      <!-- 搜索框 -->
      <div class="table-toolbar">
        <el-input v-model="searchText" placeholder="搜索物料代码/名称/公司" clearable style="width: 300px" :prefix-icon="Search" />
        <span class="result-info">共 {{ filteredItems.length }} 条结果，当前显示 {{ pagination.page }}/{{ pagination.total_pages }} 页</span>
      </div>

      <!-- 双行表头表格 -->
      <div class="table-wrapper">
        <table class="yoy-table">
          <thead>
            <!-- 第一行：分组标题 -->
            <tr class="header-group-row">
              <th class="fixed-col" rowspan="2">公司代码</th>
              <th class="fixed-col" rowspan="2">公司名称</th>
              <th class="fixed-col" rowspan="2">物料代码</th>
              <th class="fixed-col" rowspan="2">物料名称</th>
              <th class="current-group" colspan="3">{{ currentYear }}年1-{{ period }}月累计</th>
              <th class="prev-group" colspan="3">{{ currentYear - 1 }}年全年</th>
              <th class="diff-group" colspan="3">同比分析</th>
            </tr>
            <!-- 第二行：具体列标题 -->
            <tr class="header-detail-row">
              <th class="current-col">金额(CNY)</th>
              <th class="current-col">数量</th>
              <th class="current-col">平均单价</th>
              <th class="prev-col">金额(CNY)</th>
              <th class="prev-col">数量</th>
              <th class="prev-col">平均单价</th>
              <th class="diff-col">单价变动</th>
              <th class="diff-col">变动率(%)</th>
              <th class="diff-col">成本变动(CNY)</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(item, idx) in pagedItems" :key="idx" :class="{ 'no-compare': !item.can_compare }">
              <td class="fixed-col">{{ item.company_code }}</td>
              <td class="fixed-col name-col">{{ item.company_name }}</td>
              <td class="fixed-col">{{ stripLeadingZeros(item.material_code) }}</td>
              <td class="fixed-col name-col">{{ item.material_name }}</td>
              <td class="current-col">{{ formatMoney(item.current_amount) }}</td>
              <td class="current-col">{{ formatQty(item.current_qty) }}</td>
              <td class="current-col highlight">{{ formatPrice(item.current_avg_price) }}</td>
              <td class="prev-col">{{ item.can_compare ? formatMoney(item.prev_amount) : '—' }}</td>
              <td class="prev-col">{{ item.can_compare ? formatQty(item.prev_qty) : '—' }}</td>
              <td class="prev-col highlight">{{ item.can_compare ? formatPrice(item.prev_avg_price) : '—' }}</td>
              <td class="diff-col" :class="priceClass(item.price_change)">
                {{ item.can_compare ? formatPrice(item.price_change) : '—' }}
              </td>
              <td class="diff-col" :class="rateClass(item.price_change_rate)">
                {{ item.can_compare ? formatRate(item.price_change_rate) : '—' }}
              </td>
              <td class="diff-col" :class="priceClass(item.cost_change)">
                {{ item.can_compare ? formatMoney(item.cost_change) : '—' }}
              </td>
            </tr>
            <tr v-if="pagedItems.length === 0">
              <td colspan="13" class="empty-row">暂无匹配数据</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 分页 -->
      <div class="pagination-row">
        <el-pagination
          v-model:current-page="pagination.page"
          :page-size="pagination.page_size"
          :total="filteredItems.length"
          layout="prev, pager, next"
          @current-change="onPageChange"
        />
      </div>
    </el-card>

    <!-- 无数据提示 -->
    <el-card v-if="!hasData && !loading" class="empty-card" shadow="never">
      <el-empty description="请选择年份和月份，点击查询分析" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, reactive, onMounted, watch } from 'vue'
import { Search, Download } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { getYears, getCompanies, getMaterials, analyze, exportAnalysis } from '../api/yoy'
import OrgFilter from '../components/OrgFilter.vue'
import MaterialFilter from '../components/MaterialFilter.vue'
import { stripLeadingZeros } from '../utils/format'

// 状态变量
const years = ref([])
const currentYear = ref(2026)
const period = ref(5)
const loading = ref(false)
const exporting = ref(false)
const searchText = ref('')

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
}

function onMaterialFilterChange(payload) {
  materialFilter.materialCode = payload.materialCode || ''
  materialFilter.materialKeyword = payload.materialKeyword || ''
  materialFilter.majorCategory = payload.majorCategory || ''
}

// 分析结果
const analysisData = ref(null)
const pagination = ref({ page: 1, page_size: 50, total: 0, total_pages: 0 })

// 计算属性
const hasData = computed(() => analysisData.value !== null)
const summary = computed(() => analysisData.value?.summary || {})
const items = computed(() => analysisData.value?.items || [])
const filteredItems = computed(() => {
  if (!searchText.value) return items.value
  const search = searchText.value.toLowerCase()
  return items.value.filter(item =>
    item.company_code.toLowerCase().includes(search) ||
    item.company_name.toLowerCase().includes(search) ||
    item.material_code.toLowerCase().includes(search) ||
    item.material_name.toLowerCase().includes(search)
  )
})
const pagedItems = computed(() => {
  const start = (pagination.value.page - 1) * pagination.value.page_size
  return filteredItems.value.slice(start, start + pagination.value.page_size)
})

// 生命周期
onMounted(async () => {
  try {
    const res = await getYears()
    years.value = res || []
    if (years.value.length > 0) {
      currentYear.value = years.value[0]
    }
    // 自动加载分析数据
    await doAnalyze()
  } catch (e) {
    ElMessage.error('加载年份列表失败')
  }
})

function onYearChange() {
  analysisData.value = null
}

async function doAnalyze() {
  loading.value = true
  try {
    const params = {
      current_year: currentYear.value,
      period: period.value,
      company_codes: orgFilter.companyCodes.length > 0 ? orgFilter.companyCodes : undefined,
      material_keyword: materialFilter.materialKeyword || undefined,
      material_code: materialFilter.materialCode || undefined,
      major_category: materialFilter.majorCategory || undefined,
      page: 1,
      page_size: 50
    }
    const res = await analyze(params)
    analysisData.value = res
    pagination.value = res.pagination
    // 需要加载全部数据以支持前端搜索和分页
    await loadAllData()
  } catch (e) {
    ElMessage.error('分析查询失败：' + (e.response?.data?.detail || e.message))
  } finally {
    loading.value = false
  }
}

async function loadAllData() {
  // 加载全部数据用于前端搜索过滤
  try {
    const params = {
      current_year: currentYear.value,
      period: period.value,
      company_codes: orgFilter.companyCodes.length > 0 ? orgFilter.companyCodes : undefined,
      material_keyword: materialFilter.materialKeyword || undefined,
      material_code: materialFilter.materialCode || undefined,
      major_category: materialFilter.majorCategory || undefined,
      page: 1,
      page_size: 9999
    }
    const res = await analyze(params)
    // 替换items为全量数据
    analysisData.value.items = res.items
    pagination.value.total = res.items.length
    pagination.value.total_pages = Math.ceil(res.items.length / pagination.value.page_size)
    pagination.value.page = 1
  } catch (e) {
    console.error(e)
  }
}

function onPageChange(page) {
  pagination.value.page = page
}

async function doExport() {
  exporting.value = true
  try {
    const params = {
      current_year: currentYear.value,
      period: period.value,
      company_codes: orgFilter.companyCodes.length > 0 ? orgFilter.companyCodes : undefined,
      material_keyword: materialFilter.materialKeyword || undefined,
      material_code: materialFilter.materialCode || undefined,
      major_category: materialFilter.majorCategory || undefined
    }
    const res = await exportAnalysis(params)
    // 处理blob下载
    const blob = new Blob([res], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `采购同期对比分析_${currentYear.value}年1-${period.value}月vs${currentYear.value-1}年.xlsx`
    link.click()
    window.URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch (e) {
    ElMessage.error('导出失败')
  } finally {
    exporting.value = false
  }
}

// 格式化函数
function formatMoney(val) {
  if (val === 0 || val === '—' || val === null) return '—'
  return new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 }).format(val)
}
function formatQty(val) {
  if (val === 0 || val === '—' || val === null) return '—'
  return new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 }).format(val)
}
function formatPrice(val) {
  if (val === 0 || val === '—' || val === null) return '—'
  return val.toFixed(2)
}
function formatRate(val) {
  if (val === 0 || val === '—' || val === null) return '—'
  return val.toFixed(2) + '%'
}

// 样式判断
function priceClass(val) {
  if (val < 0) return 'price-down-cell'
  if (val > 0) return 'price-up-cell'
  return ''
}
function rateClass(val) {
  if (val < 0) return 'price-down-cell'
  if (val > 0) return 'price-up-cell'
  return ''
}
</script>

<style scoped>
.yoy-analysis {
  padding: 0;
}

.filter-card {
  margin-bottom: 16px;
}
.filter-row {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}
.filter-item {
  display: flex;
  align-items: center;
  gap: 8px;
}
.filter-label {
  font-size: 14px;
  color: #606266;
  white-space: nowrap;
}

/* 汇总卡片 */
.summary-row {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}
.summary-card {
  flex: 1;
  min-width: 150px;
}
.summary-card .summary-title {
  font-size: 13px;
  color: #909399;
  margin-bottom: 8px;
}
.summary-card .summary-value {
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}
.summary-card.current .summary-title { color: #409EFF; }
.summary-card.current .summary-value { color: #409EFF; }
.summary-card.prev .summary-title { color: #E6A23C; }
.summary-card.prev .summary-value { color: #E6A23C; }
.summary-card.comparable .summary-title { color: #67C23A; }
.summary-card.comparable .summary-value { color: #67C23A; }
.summary-card .summary-sub {
  font-size: 12px;
  margin-top: 4px;
}
.price-down { color: #67C23A; }
.price-up { color: #F56C6C; }
.summary-card.saving .summary-value.positive { color: #67C23A; }
.summary-card.saving .summary-value.negative { color: #F56C6C; }

/* 表格 */
.table-card {
  margin-bottom: 16px;
}
.table-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.result-info {
  font-size: 13px;
  color: #909399;
}

.table-wrapper {
  overflow-x: auto;
}

.yoy-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.yoy-table th,
.yoy-table td {
  padding: 8px 12px;
  border: 1px solid #ebeef5;
  text-align: right;
  white-space: nowrap;
}
.yoy-table .fixed-col {
  text-align: left;
}
.yoy-table .name-col {
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 表头样式 */
.header-group-row th {
  background-color: #f5f7fa;
  font-weight: 600;
  color: #303133;
  text-align: center;
}
.header-detail-row th {
  background-color: #fafafa;
  font-weight: 500;
  color: #606266;
}
.current-group {
  background-color: #e6f4ff !important;
  color: #409EFF !important;
}
.prev-group {
  background-color: #fff7e6 !important;
  color: #E6A23C !important;
}
.diff-group {
  background-color: #f6ffed !important;
  color: #67C23A !important;
}
.current-col {
  background-color: #f0f7ff;
}
.prev-col {
  background-color: #fff9eb;
}
.diff-col {
  background-color: #f3ffed;
}
.highlight {
  font-weight: 600;
  color: #303133;
}

/* 单价变动样式 */
.price-down-cell {
  color: #67C23A;
  font-weight: 500;
}
.price-up-cell {
  color: #F56C6C;
  font-weight: 500;
}

.no-compare td {
  color: #c0c4cc;
}

.empty-row {
  text-align: center;
  color: #909399;
  padding: 40px 0;
}

.pagination-row {
  display: flex;
  justify-content: center;
  margin-top: 16px;
}

.empty-card {
  margin-top: 40px;
}
</style>