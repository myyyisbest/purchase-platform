<template>
  <div class="audit-page">
    <div class="page-header">
      <div class="header-left">
        <el-icon :size="22" color="#409EFF"><Document /></el-icon>
        <h2>审计日志</h2>
        <el-tag type="danger" size="small">仅管理员</el-tag>
      </div>
      <el-button :icon="Refresh" @click="loadList">刷新</el-button>
    </div>

    <el-card shadow="never" class="filter-card">
      <div class="filter-row">
        <el-input v-model="filters.username" placeholder="用户名" clearable style="width: 140px" />
        <el-select v-model="filters.method" clearable placeholder="方法" style="width: 110px">
          <el-option label="POST" value="POST" />
          <el-option label="PUT" value="PUT" />
          <el-option label="DELETE" value="DELETE" />
          <el-option label="GET" value="GET" />
        </el-select>
        <el-input v-model="filters.path_keyword" placeholder="路径关键词" clearable style="width: 200px" />
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          value-format="YYYY-MM-DD"
          style="width: 260px"
        />
        <el-button type="primary" :icon="Search" @click="handleSearch">查询</el-button>
      </div>
    </el-card>

    <el-card shadow="never">
      <el-table :data="list" v-loading="loading" stripe border size="small">
        <el-table-column prop="created_at" label="时间" width="170">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column prop="username" label="用户" width="110" />
        <el-table-column prop="method" label="方法" width="80" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="methodType(row.method)">{{ row.method }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="path" label="路径" min-width="240" show-overflow-tooltip />
        <el-table-column prop="status_code" label="状态" width="80" align="center" />
        <el-table-column prop="client_ip" label="IP" width="130" />
        <el-table-column prop="cost_ms" label="耗时(ms)" width="90" align="right" />
        <el-table-column prop="body_summary" label="摘要" min-width="180" show-overflow-tooltip />
      </el-table>
      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[50, 100, 200]"
          layout="total, sizes, prev, pager, next"
          background
          @size-change="loadList"
          @current-change="loadList"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { Document, Refresh, Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { listAuditLogs } from '../api/auditLog'

const list = ref([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(50)
const total = ref(0)
const dateRange = ref(null)
const filters = reactive({
  username: '',
  method: '',
  path_keyword: '',
})

function methodType(m) {
  if (m === 'DELETE') return 'danger'
  if (m === 'POST') return 'success'
  if (m === 'PUT') return 'warning'
  return 'info'
}

function formatTime(v) {
  if (!v) return '—'
  try {
    return new Date(v).toLocaleString('zh-CN', { hour12: false })
  } catch {
    return String(v)
  }
}

async function loadList() {
  loading.value = true
  try {
    const params = {
      page: page.value,
      page_size: pageSize.value,
    }
    if (filters.username) params.username = filters.username
    if (filters.method) params.method = filters.method
    if (filters.path_keyword) params.path_keyword = filters.path_keyword
    if (dateRange.value?.length === 2) {
      params.date_from = dateRange.value[0]
      params.date_to = dateRange.value[1]
    }
    const res = await listAuditLogs(params)
    list.value = res?.items || []
    total.value = res?.total || 0
  } catch (e) {
    ElMessage.error('加载审计日志失败')
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  page.value = 1
  loadList()
}

onMounted(loadList)
</script>

<style scoped>
.audit-page { padding: 4px; }
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
