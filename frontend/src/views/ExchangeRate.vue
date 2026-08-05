<template>
  <div class="exchange-rate">
    <!-- 筛选区 -->
    <el-card class="filter-card" shadow="never">
      <div class="filter-row">
        <div class="filter-item">
          <label class="filter-label">币种</label>
          <el-select v-model="filterCurrency" placeholder="全部币种" clearable style="width: 140px">
            <el-option v-for="c in currencies" :key="c" :label="c" :value="c" />
          </el-select>
        </div>
        <div class="filter-item">
          <label class="filter-label">生效日期</label>
          <el-date-picker
            v-model="filterDate"
            type="date"
            placeholder="选择日期筛选生效汇率"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            style="width: 180px"
          />
        </div>
        <el-button type="primary" :icon="Search" @click="doQuery">查询</el-button>
        <el-button :icon="RefreshRight" @click="doReset">重置</el-button>
      </div>
    </el-card>

    <!-- 工具栏 -->
    <el-card class="table-card" shadow="never">
      <div class="table-toolbar">
        <el-button type="primary" :icon="Plus" @click="handleAdd">新增汇率</el-button>
        <span class="result-info" v-if="total > 0">共 {{ total }} 条记录</span>
      </div>

      <!-- 表格 -->
      <el-table
        :data="tableData"
        v-loading="loading"
        stripe
        border
        style="width: 100%"
        :default-sort="{ prop: 'effective_date', order: 'descending' }"
      >
        <el-table-column prop="from_currency" label="币种" width="80" align="center" />
        <el-table-column prop="to_currency" label="目标币种" width="90" align="center" />
        <el-table-column prop="effective_date" label="生效日期" width="120" align="center" sortable="custom" />
        <el-table-column label="失效日期" width="140" align="center">
          <template #default="{ row }">
            <el-tag v-if="!row.expiry_date" type="success" size="small">永久生效</el-tag>
            <span v-else>{{ row.expiry_date }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="exchange_rate" label="汇率" width="120" align="right">
          <template #default="{ row }">
            <span class="rate-value">{{ Number(row.exchange_rate).toFixed(6) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="source" label="来源" width="100" align="center" />
        <el-table-column prop="description" label="描述" min-width="150" show-overflow-tooltip />
        <el-table-column label="操作" width="140" align="center" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" :icon="Edit" @click="handleEdit(row)">编辑</el-button>
            <el-button type="danger" link size="small" :icon="Delete" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-wrapper" v-if="total > 0">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="doQuery"
          @current-change="doQuery"
        />
      </div>
    </el-card>

    <!-- 新增/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑汇率' : '新增汇率'"
      width="500px"
      destroy-on-close
      @closed="resetForm"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px" label-position="right">
        <el-form-item label="币种" prop="from_currency">
          <el-select
            v-model="form.from_currency"
            placeholder="请选择币种"
            filterable
            allow-create
            style="width: 100%"
            :disabled="isEdit"
          >
            <el-option v-for="c in allCurrencyOptions" :key="c" :label="c" :value="c" />
          </el-select>
        </el-form-item>
        <el-form-item label="目标币种" prop="to_currency">
          <el-input v-model="form.to_currency" disabled />
        </el-form-item>
        <el-form-item label="生效日期" prop="effective_date">
          <el-date-picker
            v-model="form.effective_date"
            type="date"
            placeholder="选择生效日期"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="失效日期" prop="expiry_date">
          <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
            <el-date-picker
              v-model="form.expiry_date"
              type="date"
              placeholder="选择失效日期"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              style="width: 200px"
              :disabled="form.is_permanent"
            />
            <el-checkbox v-model="form.is_permanent" @change="onPermanentChange">永久生效</el-checkbox>
          </div>
          <div class="form-tip">勾选"永久生效"后失效日期自动清空</div>
        </el-form-item>
        <el-form-item label="汇率" prop="exchange_rate">
          <el-input-number
            v-model="form.exchange_rate"
            :precision="6"
            :step="0.01"
            :min="0.000001"
            placeholder="请输入汇率"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="来源" prop="source">
          <el-input v-model="form.source" placeholder="如：银行牌价、手工维护" />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="备注说明（选填）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleSubmit">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, RefreshRight, Plus, Edit, Delete } from '@element-plus/icons-vue'
import {
  getCurrencies,
  getOrderCurrencies,
  getExchangeRates,
  createExchangeRate,
  updateExchangeRate,
  deleteExchangeRate,
} from '../api/exchangeRate'

// ========== 筛选 ==========
const currencies = ref([])
const filterCurrency = ref('')
const filterDate = ref('')
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

// ========== 表格 ==========
const loading = ref(false)
const tableData = ref([])

// ========== 对话框 ==========
const dialogVisible = ref(false)
const isEdit = ref(false)
const editId = ref(null)
const submitLoading = ref(false)
const formRef = ref(null)

const allCurrencyOptions = ref([])  // 从采购订单数据动态获取

const form = reactive({
  from_currency: '',
  to_currency: 'CNY',
  effective_date: '',
  expiry_date: '',
  exchange_rate: null,
  source: '',
  description: '',
  is_permanent: false,
})

const rules = {
  from_currency: [{ required: true, message: '请选择币种', trigger: 'change' }],
  effective_date: [{ required: true, message: '请选择生效日期', trigger: 'change' }],
  exchange_rate: [{ required: true, message: '请输入汇率', trigger: 'blur' }],
}

// ========== 数据加载 ==========
async function loadCurrencies() {
  try {
    const data = await getCurrencies()
    currencies.value = data || []
  } catch (e) {
    console.error('加载币种失败:', e)
  }
}

async function loadOrderCurrencies() {
  try {
    const data = await getOrderCurrencies()
    allCurrencyOptions.value = data || []
  } catch (e) {
    console.error('加载订单币种失败:', e)
  }
}

async function doQuery() {
  loading.value = true
  try {
    const params = {
      page: page.value,
      page_size: pageSize.value,
    }
    if (filterCurrency.value) params.from_currency = filterCurrency.value
    if (filterDate.value) params.effective_date = filterDate.value

    // 拦截器将 {code, data: {items, total, page, page_size}} 解包为 {items, total, page, page_size}
    const res = await getExchangeRates(params)
    tableData.value = res.items || []
    total.value = res.total || 0
  } catch (e) {
    console.error('查询汇率失败:', e)
  } finally {
    loading.value = false
  }
}

function doReset() {
  filterCurrency.value = ''
  filterDate.value = ''
  page.value = 1
  doQuery()
}

// ========== CRUD ==========
function handleAdd() {
  isEdit.value = false
  editId.value = null
  resetForm()
  dialogVisible.value = true
}

function handleEdit(row) {
  isEdit.value = true
  editId.value = row.id
  Object.assign(form, {
    from_currency: row.from_currency,
    to_currency: row.to_currency || 'CNY',
    effective_date: row.effective_date,
    expiry_date: row.expiry_date || '',
    exchange_rate: Number(row.exchange_rate),
    source: row.source || '',
    description: row.description || '',
    is_permanent: !row.expiry_date,
  })
  dialogVisible.value = true
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(
      `确定要删除 ${row.from_currency} 的汇率记录（生效日：${row.effective_date}）吗？`,
      '确认删除',
      { type: 'warning' }
    )
    await deleteExchangeRate(row.id)
    ElMessage.success('删除成功')
    doQuery()
  } catch (e) {
    if (e?.response?.data?.detail) {
      ElMessage.error(e.response.data.detail)
    }
  }
}

async function handleSubmit() {
  if (!formRef.value) return
  await formRef.value.validate()

  submitLoading.value = true
  try {
    const payload = {
      from_currency: form.from_currency,
      to_currency: form.to_currency,
      effective_date: form.effective_date,
      exchange_rate: form.exchange_rate,
      source: form.source || undefined,
      description: form.description || undefined,
    }
    // 永久生效 → 显式传 null 清除旧值；否则传具体日期
    if (form.is_permanent) {
      payload.expiry_date = null
    } else if (form.expiry_date) {
      payload.expiry_date = form.expiry_date
    }

    if (isEdit.value) {
      await updateExchangeRate(editId.value, payload)
      ElMessage.success('更新成功')
    } else {
      await createExchangeRate(payload)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    doQuery()
    loadCurrencies()
  } catch (e) {
    const msg = e?.response?.data?.detail || e?.message || '操作失败'
    ElMessage.error(msg)
  } finally {
    submitLoading.value = false
  }
}

function onPermanentChange(val) {
  // 勾选"永久生效"时清空失效日期，取消勾选时恢复空（由用户手动选）
  if (val) {
    form.expiry_date = ''
  }
}

function resetForm() {
  form.from_currency = ''
  form.to_currency = 'CNY'
  form.effective_date = ''
  form.expiry_date = ''
  form.exchange_rate = null
  form.source = ''
  form.description = ''
  form.is_permanent = false
}

// ========== 初始化 ==========
onMounted(async () => {
  await Promise.all([loadCurrencies(), loadOrderCurrencies(), doQuery()])
})
</script>

<style scoped>
.exchange-rate {
  padding: 0;
}

.filter-card {
  margin-bottom: 16px;
}

.filter-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.filter-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.filter-label {
  font-size: 13px;
  color: #606266;
  white-space: nowrap;
}

.table-card {
  min-height: 400px;
}

.table-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.result-info {
  font-size: 13px;
  color: #909399;
}

.rate-value {
  font-family: 'Courier New', monospace;
  font-weight: 500;
}

.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

:deep(.el-card__body) {
  padding: 16px;
}
</style>
