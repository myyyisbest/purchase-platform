<template>
  <div class="hana-sync-page">
    <div class="page-header">
      <div class="header-left">
        <el-icon :size="22" color="#409EFF"><Connection /></el-icon>
        <h2>HANA 同步运维</h2>
        <el-tag type="danger" size="small">仅管理员</el-tag>
      </div>
      <div class="header-right">
        <el-button :icon="Refresh" @click="loadAll" :loading="loading">刷新状态</el-button>
      </div>
    </div>

    <el-row :gutter="16">
      <el-col :xs="24" :md="12">
        <el-card shadow="never" class="info-card">
          <template #header><span>连接配置</span></template>
          <el-descriptions :column="1" border size="small" v-loading="loading">
            <el-descriptions-item label="Host">{{ status.hana_host || '—' }}</el-descriptions-item>
            <el-descriptions-item label="Port">{{ status.hana_port || '—' }}</el-descriptions-item>
            <el-descriptions-item label="User">{{ status.hana_user || '—' }}</el-descriptions-item>
            <el-descriptions-item label="View">{{ status.hana_view || '—' }}</el-descriptions-item>
          </el-descriptions>
          <p class="hint">密码不会在接口中返回。</p>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="12">
        <el-card shadow="never" class="info-card">
          <template #header><span>最近同步状态</span></template>
          <el-descriptions :column="1" border size="small" v-loading="loading">
            <el-descriptions-item label="本地记录数">{{ state.local_record_count ?? '—' }}</el-descriptions-item>
            <el-descriptions-item label="同步类型">{{ lastSync.sync_type || '—' }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag v-if="lastSync.status" size="small" :type="statusType(lastSync.status)">{{ lastSync.status }}</el-tag>
              <span v-else>—</span>
            </el-descriptions-item>
            <el-descriptions-item label="最近同步时间">{{ formatTime(lastSync.last_sync_at) }}</el-descriptions-item>
            <el-descriptions-item label="新增 / 更新 / 删除">
              {{ lastSync.total_inserted ?? 0 }} / {{ lastSync.total_updated ?? 0 }} / {{ lastSync.total_deleted ?? 0 }}
            </el-descriptions-item>
            <el-descriptions-item label="错误信息" v-if="lastSync.error_message">
              <span style="color:#f56c6c">{{ lastSync.error_message }}</span>
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="action-card">
      <template #header><span>触发同步</span></template>
      <div class="actions">
        <el-button type="primary" :loading="syncing === 'full'" @click="doSync('full')">全量同步</el-button>
        <el-button type="warning" :loading="syncing === 'incremental'" @click="doSync('incremental')">增量同步</el-button>
        <el-button type="success" :loading="syncing === 'monthly'" @click="doSync('monthly')">月度同步（当月+上月）</el-button>
      </div>
      <p class="hint">全量/增量耗时可能较长，请勿重复点击。定时任务请配置 CRON_API_TOKEN 后使用 scripts/daily_monthly_sync.sh。</p>
      <el-alert v-if="lastResult" :title="lastResultTitle" :type="lastResultOk ? 'success' : 'error'" show-icon :closable="false" style="margin-top:12px">
        <pre class="result-pre">{{ JSON.stringify(lastResult, null, 2) }}</pre>
      </el-alert>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { Connection, Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getHanaStatus, getHanaState, triggerHanaSync } from '../api/hanaSync'

const loading = ref(false)
const syncing = ref('')
const status = ref({})
const state = ref({})
const lastResult = ref(null)
const lastResultOk = ref(true)

const lastSync = computed(() => state.value.last_sync || {})
const lastResultTitle = computed(() => lastResultOk.value ? '同步成功' : '同步失败')

function statusType(s) {
  if (s === 'completed') return 'success'
  if (s === 'failed') return 'danger'
  if (s === 'running') return 'warning'
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

async function loadAll() {
  loading.value = true
  try {
    const [s, st] = await Promise.all([getHanaStatus(), getHanaState()])
    status.value = s || {}
    state.value = st || {}
  } catch (e) {
    ElMessage.error('加载 HANA 状态失败')
    console.error(e)
  } finally {
    loading.value = false
  }
}

const modeLabel = { full: '全量同步', incremental: '增量同步', monthly: '月度同步' }

async function doSync(mode) {
  try {
    await ElMessageBox.confirm(
      `确认执行「${modeLabel[mode]}」？此操作会写入采购明细，可能耗时较长。`,
      '确认同步',
      { type: 'warning', confirmButtonText: '开始同步', cancelButtonText: '取消' }
    )
  } catch { return }

  syncing.value = mode
  lastResult.value = null
  try {
    const data = await triggerHanaSync(mode)
    lastResult.value = data
    lastResultOk.value = true
    ElMessage.success(`${modeLabel[mode]}完成`)
    await loadAll()
  } catch (e) {
    lastResultOk.value = false
    lastResult.value = { error: e?.response?.data?.detail || e?.message || String(e) }
    ElMessage.error('同步失败')
  } finally {
    syncing.value = ''
  }
}

onMounted(loadAll)
</script>

<style scoped>
.hana-sync-page { padding: 4px; }
.page-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 16px;
}
.header-left { display: flex; align-items: center; gap: 10px; }
.header-left h2 { margin: 0; font-size: 18px; }
.info-card, .action-card { margin-bottom: 16px; }
.hint { margin-top: 10px; font-size: 12px; color: #909399; }
.actions { display: flex; flex-wrap: wrap; gap: 12px; }
.result-pre {
  margin: 8px 0 0; font-size: 12px; white-space: pre-wrap; word-break: break-all;
  max-height: 240px; overflow: auto;
}
</style>
