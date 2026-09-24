<template>
  <div class="purchase-records">
    <el-card class="filter-card" shadow="never">
      <div class="filter-row">
        <OrgFilter ref="orgFilterRef" @change="onOrgFilterChange" />
        <el-input v-model="filters.material_keyword" placeholder="物料编码/名称" clearable style="width: 160px" />
        <el-input v-model="filters.supplier_keyword" placeholder="供应商编码/名称" clearable style="width: 160px" />
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          value-format="YYYY-MM-DD"
          style="width: 260px"
        />
        <el-input v-model="filters.po_number" placeholder="采购订单" clearable style="width: 140px" />
        <el-input v-model="filters.material_doc" placeholder="物料凭证" clearable style="width: 140px" />
        <el-input-number v-model="filters.fiscal_year" :controls="false" placeholder="财年" style="width: 100px" />
        <el-button type="primary" :icon="Search" :loading="loading" @click="doSearch(1)">查询</el-button>
        <el-button :icon="Download" :loading="exporting" :disabled="!hasData" @click="doExport">导出Excel</el-button>
        <el-button @click="resetFilters">重置</el-button>
      </div>
    </el-card>

    <div v-if="summary" class="summary-row">
      <el-card class="summary-card" shadow="never">
        <div class="summary-title">记录数</div>
        <div class="summary-value">{{ summary.count?.toLocaleString() }}</div>
      </el-card>
      <el-card class="summary-card" shadow="never">
        <div class="summary-title">采购金额合计 (CNY)</div>
        <div class="summary-value">{{ formatMoney(summary.total_cny) }}</div>
      </el-card>
      <el-card class="summary-card" shadow="never">
        <div class="summary-title">采购数量合计</div>
        <div class="summary-value">{{ formatQty(summary.total_qty) }}</div>
      </el-card>
    </div>

    <el-card class="table-card" shadow="never" v-loading="loading">
      <el-table :data="items" stripe border size="small" max-height="560" empty-text="暂无数据，请调整筛选条件后查询">
        <el-table-column prop="transaction_date" label="日期" width="110" fixed />
        <el-table-column prop="company_code" label="公司" width="80" />
        <el-table-column prop="company_name" label="公司名称" min-width="140" show-overflow-tooltip />
        <el-table-column label="物料代码" width="120">
          <template #default="{ row }">{{ stripLeadingZeros(row.material_code) }}</template>
        </el-table-column>
        <el-table-column prop="material_name" label="物料名称" min-width="160" show-overflow-tooltip />
        <el-table-column prop="supplier_name" label="供应商" min-width="150" show-overflow-tooltip />
        <el-table-column prop="quantity" label="数量" width="100" align="right">
          <template #default="{ row }">{{ formatQty(row.quantity) }}</template>
        </el-table-column>
        <el-table-column prop="unit" label="单位" width="60" />
        <el-table-column prop="order_currency" label="币种" width="70" />
        <el-table-column prop="order_amount" label="订单金额" width="110" align="right">
          <template #default="{ row }">{{ formatMoney(row.order_amount) }}</template>
        </el-table-column>
        <el-table-column prop="cny_amount" label="金额(CNY)" width="120" align="right">
          <template #default="{ row }">{{ formatMoney(row.cny_amount) }}</template>
        </el-table-column>
        <el-table-column prop="po_number" label="采购订单" width="120" show-overflow-tooltip />
        <el-table-column prop="material_doc" label="物料凭证" width="120" show-overflow-tooltip />
        <el-table-column prop="line_item" label="行项目" width="80" />
      </el-table>

      <div class="pagination-row">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.page_size"
          :total="pagination.total"
          :page-sizes="[20, 50, 100, 200]"
          layout="total, sizes, prev, pager, next"
          @current-change="(p) => doSearch(p)"
          @size-change="() => doSearch(1)"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Search, Download } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import OrgFilter from '../components/OrgFilter.vue'
import { listPurchaseRecords, exportPurchaseRecords } from '../api/purchaseRecord'
import { formatMoney, stripLeadingZeros } from '../utils/format'

const route = useRoute()
const router = useRouter()

const orgFilterRef = ref(null)
const orgFilter = reactive({ companyCodes: [], companyName: '' })

const filters = reactive({
  material_code: '',
  material_keyword: '',
  supplier_keyword: '',
  po_number: '',
  material_doc: '',
  fiscal_year: undefined,
})

const dateRange = ref(null)
const loading = ref(false)
const exporting = ref(false)
const items = ref([])
const summary = ref(null)
const pagination = reactive({ page: 1, page_size: 50, total: 0, total_pages: 0 })
const hasData = computed(() => (pagination.total || 0) > 0)

function formatQty(v) {
  if (v === null || v === undefined || v === '') return '—'
  const n = Number(v)
  if (Number.isNaN(n)) return String(v)
  return n.toLocaleString(undefined, { maximumFractionDigits: 4 })
}

function onOrgFilterChange(payload) {
  orgFilter.companyCodes = payload.companyCodes || []
  orgFilter.companyName = payload.companyName || ''
}

function buildParams(page) {
  const params = {
    page: page || pagination.page,
    page_size: pagination.page_size,
  }
  if (orgFilter.companyCodes.length > 0) params.company_codes = orgFilter.companyCodes
  if (filters.material_code) params.material_code = filters.material_code
  if (filters.material_keyword) params.material_keyword = filters.material_keyword
  if (filters.supplier_keyword) params.supplier_keyword = filters.supplier_keyword
  if (filters.po_number) params.po_number = filters.po_number
  if (filters.material_doc) params.material_doc = filters.material_doc
  if (filters.fiscal_year) params.fiscal_year = filters.fiscal_year
  if (dateRange.value && dateRange.value.length === 2) {
    params.date_from = dateRange.value[0]
    params.date_to = dateRange.value[1]
  }
  return params
}

function syncQueryToRoute(params) {
  const q = {}
  if (params.company_codes?.length) q.company_codes = params.company_codes.join(',')
  if (params.material_code) q.material_code = params.material_code
  if (params.material_keyword) q.material_keyword = params.material_keyword
  if (params.supplier_keyword) q.supplier_keyword = params.supplier_keyword
  if (params.po_number) q.po_number = params.po_number
  if (params.material_doc) q.material_doc = params.material_doc
  if (params.fiscal_year) q.fiscal_year = String(params.fiscal_year)
  if (params.date_from) q.date_from = params.date_from
  if (params.date_to) q.date_to = params.date_to
  if (params.page && params.page > 1) q.page = String(params.page)
  if (params.page_size && params.page_size !== 50) q.page_size = String(params.page_size)
  router.replace({ query: q })
}

function applyQueryFromRoute() {
  const q = route.query
  if (q.material_code) filters.material_code = String(q.material_code)
  if (q.material_keyword) filters.material_keyword = String(q.material_keyword)
  if (q.supplier_keyword) filters.supplier_keyword = String(q.supplier_keyword)
  if (q.po_number) filters.po_number = String(q.po_number)
  if (q.material_doc) filters.material_doc = String(q.material_doc)
  if (q.fiscal_year) {
    const y = parseInt(String(q.fiscal_year), 10)
    if (!Number.isNaN(y)) filters.fiscal_year = y
  }
  if (q.date_from && q.date_to) dateRange.value = [String(q.date_from), String(q.date_to)]
  if (q.page) {
    const p = parseInt(String(q.page), 10)
    if (!Number.isNaN(p) && p > 0) pagination.page = p
  }
  if (q.page_size) {
    const s = parseInt(String(q.page_size), 10)
    if (!Number.isNaN(s) && s >= 10) pagination.page_size = s
  }
  if (q.company_codes) {
    orgFilter.companyCodes = String(q.company_codes).split(',').map(s => s.trim()).filter(Boolean)
  }
}

async function doSearch(page = 1) {
  loading.value = true
  try {
    const params = buildParams(page)
    syncQueryToRoute(params)
    const res = await listPurchaseRecords(params)
    items.value = res.items || []
    summary.value = res.summary || null
    Object.assign(pagination, res.pagination || {})
  } catch (e) {
    ElMessage.error('查询失败：' + (e.response?.data?.detail || e.message))
  } finally {
    loading.value = false
  }
}

async function doExport() {
  exporting.value = true
  try {
    const params = buildParams(1)
    delete params.page
    delete params.page_size
    const blob = await exportPurchaseRecords(params)
    const url = window.URL.createObjectURL(
      new Blob([blob], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
    )
    const link = document.createElement('a')
    link.href = url
    link.download = `采购记录明细_${new Date().toISOString().slice(0, 10)}.xlsx`
    link.click()
    window.URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch (e) {
    ElMessage.error('导出失败：' + (e.response?.data?.detail || e.message))
  } finally {
    exporting.value = false
  }
}

function resetFilters() {
  filters.material_code = ''
  filters.material_keyword = ''
  filters.supplier_keyword = ''
  filters.po_number = ''
  filters.material_doc = ''
  filters.fiscal_year = undefined
  dateRange.value = null
  orgFilter.companyCodes = []
  orgFilter.companyName = ''
  pagination.page = 1
  router.replace({ query: {} })
  items.value = []
  summary.value = null
  pagination.total = 0
}

onMounted(async () => {
  applyQueryFromRoute()
  if (Object.keys(route.query).length > 0) {
    await doSearch(pagination.page || 1)
  }
})
</script>

<style scoped>
.purchase-records { display: flex; flex-direction: column; gap: 16px; }
.filter-card :deep(.el-card__body) { padding: 12px 16px; }
.filter-row { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.summary-row { display: flex; gap: 12px; flex-wrap: wrap; }
.summary-card { flex: 1; min-width: 180px; }
.summary-title { font-size: 13px; color: #909399; margin-bottom: 6px; }
.summary-value { font-size: 22px; font-weight: 600; color: #303133; }
.pagination-row { margin-top: 16px; display: flex; justify-content: flex-end; }
</style>
