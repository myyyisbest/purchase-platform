<template>
  <div class="suppliers-page">
    <div class="page-header">
      <div class="header-left">
        <el-icon :size="22" color="#409EFF"><OfficeBuilding /></el-icon>
        <h2>供应商管理</h2>
      </div>
      <div class="header-right">
        <el-button v-if="isAdmin" type="warning" :loading="syncing" @click="handleSync">从采购记录同步</el-button>
        <el-button v-if="isAdmin" type="primary" :icon="Plus" @click="openCreate">新增供应商</el-button>
        <el-button :icon="Refresh" @click="loadList">刷新</el-button>
      </div>
    </div>

    <el-card class="filter-card" shadow="never">
      <div class="filter-row">
        <el-input v-model="keyword" placeholder="编码/名称关键词" clearable style="width: 220px" @keyup.enter="handleSearch" />
        <el-select v-model="category" clearable placeholder="类别" style="width: 140px">
          <el-option label="关联方" value="关联方" />
          <el-option label="非关联方" value="非关联方" />
        </el-select>
        <el-button type="primary" :icon="Search" @click="handleSearch">查询</el-button>
      </div>
    </el-card>

    <el-card shadow="never">
      <el-table :data="list" v-loading="loading" stripe border>
        <el-table-column type="index" label="#" width="55" align="center" />
        <el-table-column prop="supplier_code" label="供应商编码" width="140">
          <template #default="{ row }">
            <el-link type="primary" @click="goRecords(row)">{{ row.supplier_code }}</el-link>
          </template>
        </el-table-column>
        <el-table-column prop="supplier_name" label="供应商名称" min-width="220" show-overflow-tooltip />
        <el-table-column prop="category" label="类别" width="110" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.category" size="small">{{ row.category }}</el-tag>
            <span v-else style="color:#c0c4cc">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="risk_level" label="风险等级" width="100" align="center" />
        <el-table-column prop="contact_person" label="联系人" width="120" />
        <el-table-column prop="contact_phone" label="电话" width="130" />
        <el-table-column label="操作" width="160" align="center" fixed="right" v-if="isAdmin">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click="openEdit(row)">编辑</el-button>
            <el-popconfirm title="确认删除该供应商？" @confirm="handleDelete(row)">
              <template #reference>
                <el-button size="small" type="danger" link>删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          background
          @size-change="loadList"
          @current-change="loadList"
        />
      </div>
    </el-card>

    <el-drawer v-model="drawerVisible" :title="drawerMode === 'create' ? '新增供应商' : '编辑供应商'" size="420px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="供应商编码" required>
          <el-input v-model="form.supplier_code" :disabled="drawerMode === 'edit'" />
        </el-form-item>
        <el-form-item label="供应商名称" required>
          <el-input v-model="form.supplier_name" />
        </el-form-item>
        <el-form-item label="类别">
          <el-select v-model="form.category" clearable style="width:100%">
            <el-option label="关联方" value="关联方" />
            <el-option label="非关联方" value="非关联方" />
          </el-select>
        </el-form-item>
        <el-form-item label="风险等级">
          <el-input v-model="form.risk_level" />
        </el-form-item>
        <el-form-item label="联系人">
          <el-input v-model="form.contact_person" />
        </el-form-item>
        <el-form-item label="电话">
          <el-input v-model="form.contact_phone" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="form.email" />
        </el-form-item>
        <el-form-item label="地址">
          <el-input v-model="form.address" type="textarea" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.description" type="textarea" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="drawerVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Plus, Refresh, Search, OfficeBuilding } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listSuppliers,
  createSupplier,
  updateSupplier,
  deleteSupplier,
  syncSuppliersFromRecords,
} from '../api/supplier'

const router = useRouter()
const isAdmin = ref(false)
try {
  isAdmin.value = JSON.parse(localStorage.getItem('pp_user') || '{}').role === 'admin'
} catch { /* ignore */ }

const list = ref([])
const loading = ref(false)
const syncing = ref(false)
const saving = ref(false)
const keyword = ref('')
const category = ref('')
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

const drawerVisible = ref(false)
const drawerMode = ref('create')
const editingId = ref(null)
const form = ref(emptyForm())

function emptyForm() {
  return {
    supplier_code: '',
    supplier_name: '',
    category: '',
    risk_level: '',
    contact_person: '',
    contact_phone: '',
    email: '',
    address: '',
    description: '',
  }
}

async function loadList() {
  loading.value = true
  try {
    const res = await listSuppliers({
      keyword: keyword.value || undefined,
      category: category.value || undefined,
      page: page.value,
      page_size: pageSize.value,
    })
    list.value = res?.items || []
    total.value = res?.total || 0
  } catch (e) {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  page.value = 1
  loadList()
}

function goRecords(row) {
  router.push({
    path: '/purchase-records',
    query: { supplier_keyword: row.supplier_name || row.supplier_code },
  })
}

function openCreate() {
  drawerMode.value = 'create'
  editingId.value = null
  form.value = emptyForm()
  drawerVisible.value = true
}

function openEdit(row) {
  drawerMode.value = 'edit'
  editingId.value = row.id
  form.value = {
    supplier_code: row.supplier_code,
    supplier_name: row.supplier_name,
    category: row.category || '',
    risk_level: row.risk_level || '',
    contact_person: row.contact_person || '',
    contact_phone: row.contact_phone || '',
    email: row.email || '',
    address: row.address || '',
    description: row.description || '',
  }
  drawerVisible.value = true
}

async function handleSave() {
  if (!form.value.supplier_code || !form.value.supplier_name) {
    ElMessage.warning('请填写编码与名称')
    return
  }
  saving.value = true
  try {
    if (drawerMode.value === 'create') {
      await createSupplier(form.value)
      ElMessage.success('创建成功')
    } else {
      const { supplier_code, ...rest } = form.value
      await updateSupplier(editingId.value, rest)
      ElMessage.success('更新成功')
    }
    drawerVisible.value = false
    loadList()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleDelete(row) {
  try {
    await deleteSupplier(row.id)
    ElMessage.success('已删除')
    loadList()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

async function handleSync() {
  try {
    await ElMessageBox.confirm('将从采购记录中同步去重供应商到主数据，是否继续？', '同步确认', { type: 'warning' })
  } catch { return }
  syncing.value = true
  try {
    const stats = await syncSuppliersFromRecords()
    ElMessage.success(`同步完成：新增 ${stats.created}，更新 ${stats.updated}`)
    loadList()
  } catch (e) {
    ElMessage.error('同步失败')
  } finally {
    syncing.value = false
  }
}

onMounted(loadList)
</script>

<style scoped>
.suppliers-page { padding: 4px; }
.page-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 16px;
}
.header-left { display: flex; align-items: center; gap: 10px; }
.header-left h2 { margin: 0; font-size: 18px; }
.filter-card { margin-bottom: 16px; }
.filter-row { display: flex; gap: 12px; flex-wrap: wrap; }
.pagination-wrap { margin-top: 16px; display: flex; justify-content: flex-end; }
</style>
