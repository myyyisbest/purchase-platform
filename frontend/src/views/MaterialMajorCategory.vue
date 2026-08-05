<template>
  <div class="material-major-category">
    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-left">
        <el-icon :size="22" color="#409EFF"><Files /></el-icon>
        <h2>物料大类维护</h2>
        <el-tag type="info" size="small">按 (公司, 物料编码) 唯一</el-tag>
      </div>
      <div class="header-right">
        <el-button type="primary" :icon="Plus" @click="handleAdd">新增维护记录</el-button>
        <el-button :icon="Refresh" @click="loadList">刷新</el-button>
      </div>
    </div>

    <!-- 筛选区 -->
    <el-card class="filter-card" shadow="never">
      <div class="filter-row">
        <div class="filter-item">
          <label class="filter-label">公司代码</label>
          <el-input
            v-model="filterCompanyCode"
            placeholder="如 1000 / 2000"
            clearable
            style="width: 140px"
            @keyup.enter="handleFilterSearch"
          />
        </div>
        <div class="filter-item">
          <label class="filter-label">物料编码</label>
          <el-input
            v-model="filterMaterialCode"
            placeholder="精确匹配"
            clearable
            style="width: 180px"
            @keyup.enter="handleFilterSearch"
          />
        </div>
        <div class="filter-item">
          <label class="filter-label">物料大类</label>
          <el-input
            v-model="filterMajorCategory"
            placeholder="精确匹配"
            clearable
            style="width: 160px"
            @keyup.enter="handleFilterSearch"
          />
        </div>
        <div class="filter-item">
          <label class="filter-label">关键词</label>
          <el-input
            v-model="filterKeyword"
            placeholder="模糊搜索编码/名称/大类"
            clearable
            style="width: 240px"
            @keyup.enter="handleFilterSearch"
          />
        </div>
        <el-button type="primary" :icon="Search" @click="handleFilterSearch">查询</el-button>
        <el-button :icon="RefreshLeft" @click="handleFilterReset">重置</el-button>
      </div>
    </el-card>

    <!-- 数据表格 -->
    <el-card class="table-card" shadow="never">
      <el-table
        :data="list"
        v-loading="loading"
        stripe
        border
        size="default"
        :header-cell-style="{ background: '#f5f7fa', color: '#303133' }"
      >
        <el-table-column type="index" label="#" width="55" align="center" />
        <el-table-column prop="company_code" label="公司代码" width="110" align="center" />
        <el-table-column prop="material_code" label="物料编码" width="160">
          <template #default="{ row }">
            <span style="font-family: monospace; color: #409EFF; font-weight: 500;">{{ stripLeadingZeros(row.material_code) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="material_name" label="物料名称" min-width="280" show-overflow-tooltip />
        <el-table-column prop="major_category" label="物料大类" width="160" align="center">
          <template #default="{ row }">
            <el-tag type="success" size="small">{{ row.major_category }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="updated_at" label="更新时间" width="170" align="center">
          <template #default="{ row }">
            <span style="color:#909399; font-size:12px">{{ formatTime(row.updated_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="170" align="center" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click="handleEdit(row)">编辑</el-button>
            <el-popconfirm
              :title="`确认删除 ${row.company_code} - ${row.material_code} 的大类维护？`"
              confirm-button-text="确认删除"
              cancel-button-text="取消"
              @confirm="handleDelete(row)"
            >
              <template #reference>
                <el-button size="small" type="danger" link>删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.page_size"
          :page-sizes="[20, 50, 100, 200]"
          :total="pagination.total"
          layout="total, sizes, prev, pager, next, jumper"
          background
          @size-change="loadList"
          @current-change="loadList"
        />
      </div>
    </el-card>

    <!-- 新增/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogMode === 'add' ? '新增物料大类维护' : '编辑物料大类维护'"
      width="560px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="formRules"
        label-width="100px"
        label-position="right"
      >
        <el-form-item label="公司代码" prop="company_code">
          <el-input
            v-model="form.company_code"
            placeholder="如 1000 / 2000"
            :disabled="dialogMode === 'edit'"
          />
        </el-form-item>
        <el-form-item label="物料编码" prop="material_code">
          <el-input
            v-model="form.material_code"
            placeholder="物料编码"
            :disabled="dialogMode === 'edit'"
          />
        </el-form-item>
        <el-form-item label="物料名称" prop="material_name">
          <el-input
            v-model="form.material_name"
            placeholder="物料名称（可后补）"
            maxlength="200"
          />
        </el-form-item>
        <el-form-item label="物料大类" prop="major_category">
          <el-select
            v-model="form.major_category"
            placeholder="选择或输入新大类"
            filterable
            allow-create
            default-first-option
            style="width: 100%"
          >
            <el-option
              v-for="cat in majorCategoryOptions"
              :key="cat"
              :label="cat"
              :value="cat"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSubmit">
          {{ dialogMode === 'add' ? '创建' : '保存' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Plus,
  Refresh,
  Search,
  RefreshLeft,
  Files
} from '@element-plus/icons-vue'
import {
  listMaterialMajorCategories,
  getMajorCategoryOptions,
  createMaterialMajorCategory,
  updateMaterialMajorCategory,
  deleteMaterialMajorCategory
} from '../api/materialMajorCategory'
import { stripLeadingZeros } from '../utils/format'

// ========== 列表/筛选 ==========
const list = ref([])
const loading = ref(false)
const saving = ref(false)
const pagination = reactive({ page: 1, page_size: 20, total: 0 })

const filterCompanyCode = ref('')
const filterMaterialCode = ref('')
const filterMajorCategory = ref('')
const filterKeyword = ref('')

async function loadList() {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.page_size
    }
    if (filterCompanyCode.value) params.company_code = filterCompanyCode.value
    if (filterMaterialCode.value) params.material_code = filterMaterialCode.value
    if (filterMajorCategory.value) params.major_category = filterMajorCategory.value
    if (filterKeyword.value) params.keyword = filterKeyword.value

    const res = await listMaterialMajorCategories(params)
    // 解包：后端返回 {code, data: {items, total, page, page_size}}
    if (res && res.items) {
      list.value = res.items
      pagination.total = res.total
    } else {
      list.value = []
      pagination.total = 0
    }
  } catch (e) {
    console.error(e)
    ElMessage.error('加载物料大类维护记录失败')
  } finally {
    loading.value = false
  }
}

function handleFilterSearch() {
  pagination.page = 1
  loadList()
}

function handleFilterReset() {
  filterCompanyCode.value = ''
  filterMaterialCode.value = ''
  filterMajorCategory.value = ''
  filterKeyword.value = ''
  pagination.page = 1
  loadList()
}

// ========== 大类下拉 ==========
const majorCategoryOptions = ref([])

async function loadMajorCategoryOptions() {
  try {
    const res = await getMajorCategoryOptions()
    majorCategoryOptions.value = res || []
  } catch (e) {
    console.error('加载物料大类选项失败:', e)
    majorCategoryOptions.value = []
  }
}

// ========== 新增/编辑对话框 ==========
const dialogVisible = ref(false)
const dialogMode = ref('add')  // add | edit
const formRef = ref(null)
const form = reactive({
  id: null,
  company_code: '',
  material_code: '',
  material_name: '',
  major_category: ''
})
const formRules = {
  company_code: [{ required: true, message: '请输入公司代码', trigger: 'blur' }],
  material_code: [{ required: true, message: '请输入物料编码', trigger: 'blur' }],
  major_category: [{ required: true, message: '请选择或输入物料大类', trigger: 'change' }]
}

function resetForm() {
  form.id = null
  form.company_code = ''
  form.material_code = ''
  form.material_name = ''
  form.major_category = ''
}

function handleAdd() {
  resetForm()
  dialogMode.value = 'add'
  dialogVisible.value = true
  loadMajorCategoryOptions()
}

function handleEdit(row) {
  form.id = row.id
  form.company_code = row.company_code
  form.material_code = row.material_code
  form.material_name = row.material_name || ''
  form.major_category = row.major_category
  dialogMode.value = 'edit'
  dialogVisible.value = true
  loadMajorCategoryOptions()
}

async function handleSubmit() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }
  saving.value = true
  try {
    if (dialogMode.value === 'add') {
      await createMaterialMajorCategory({
        company_code: form.company_code.trim(),
        material_code: form.material_code.trim(),
        material_name: form.material_name.trim(),
        major_category: form.major_category.trim()
      })
      ElMessage.success('创建成功')
    } else {
      await updateMaterialMajorCategory(form.id, {
        material_name: form.material_name.trim(),
        major_category: form.major_category.trim()
      })
      ElMessage.success('更新成功')
    }
    dialogVisible.value = false
    await loadList()
  } catch (e) {
    const msg = e?.response?.data?.detail || e?.message || '操作失败'
    ElMessage.error(msg)
  } finally {
    saving.value = false
  }
}

async function handleDelete(row) {
  try {
    await deleteMaterialMajorCategory(row.id)
    ElMessage.success('删除成功')
    // 删完如果当前页空了，回退一页
    if (list.value.length === 1 && pagination.page > 1) {
      pagination.page -= 1
    }
    await loadList()
  } catch (e) {
    const msg = e?.response?.data?.detail || e?.message || '删除失败'
    ElMessage.error(msg)
  }
}

// ========== 工具 ==========
function formatTime(t) {
  if (!t) return '-'
  try {
    const d = new Date(t)
    if (isNaN(d.getTime())) return t
    const pad = n => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
  } catch {
    return t
  }
}

onMounted(() => {
  loadList()
  loadMajorCategoryOptions()
})
</script>

<style scoped>
.material-major-category {
  padding: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding: 16px 20px;
  background: #fff;
  border-radius: 6px;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
}
.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}
.header-left h2 {
  margin: 0;
  font-size: 18px;
  color: #303133;
}
.header-right {
  display: flex;
  gap: 8px;
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

.table-card { margin-bottom: 16px; }
.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
