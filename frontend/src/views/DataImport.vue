<template>
  <div class="data-import">
    <el-card>
      <template #header>
        <div class="card-header">
          <h3>数据导入</h3>
          <el-button type="success" plain :loading="downloadingTemplate" @click="handleDownloadTemplate">
            下载导入模板
          </el-button>
        </div>
      </template>

      <el-alert
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 16px"
        title="仅管理员可导入。请使用「下载导入模板」中的中文列名；支持 .xlsx / .xls / .csv。供应商类别为「关联方」或物料代码为空的行会自动跳过；按「物料凭证+行项目」去重。"
      />

      <el-upload
        ref="uploadRef"
        class="upload-demo"
        drag
        action="#"
        :auto-upload="false"
        :on-change="handleFileChange"
        :limit="1"
        :on-exceed="handleExceed"
        accept=".xlsx,.xls,.csv"
      >
        <el-icon class="el-icon--upload"><upload-filled /></el-icon>
        <div class="el-upload__text">
          将 Excel / CSV 文件拖到此处，或 <em>点击上传</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">只能上传 .xlsx / .xls / .csv 文件，且不超过 50MB</div>
        </template>
      </el-upload>

      <div class="action-buttons" style="margin-top: 20px;">
        <el-button type="primary" @click="handleImport" :loading="importing">开始导入</el-button>
        <el-button @click="handleReset">重置</el-button>
      </div>

      <div v-if="importResult" class="import-result" style="margin-top: 20px;">
        <el-alert
          :title="importResult.title"
          :type="importResult.type"
          :description="importResult.description"
          show-icon
          :closable="false"
        />

        <el-table
          v-if="importResult.stats"
          :data="[importResult.stats]"
          style="width: 100%; margin-top: 20px;"
          border
        >
          <el-table-column prop="total" label="总记录数" />
          <el-table-column prop="success" label="成功" />
          <el-table-column prop="failed" label="失败" />
          <el-table-column prop="skipped_related" label="跳过关联方" />
          <el-table-column prop="skipped_empty_material" label="跳过空物料" />
          <el-table-column prop="duplicates_skipped" label="去重跳过" />
        </el-table>

        <div v-if="importResult.stats?.missing_rates?.length" style="margin-top: 12px;">
          <el-alert
            type="warning"
            :closable="false"
            :title="`缺少汇率的货币：${importResult.stats.missing_rates.join(', ')}`"
          />
        </div>

        <div v-if="importResult.errors?.length" style="margin-top: 20px;">
          <h4>错误详情：</h4>
          <el-table :data="importResult.errors" style="width: 100%;" border max-height="300">
            <el-table-column prop="row" label="行号" width="100" />
            <el-table-column prop="error" label="错误信息" />
          </el-table>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import { uploadImportFile, downloadImportTemplate } from '../api/import'

const uploadRef = ref()
const importing = ref(false)
const downloadingTemplate = ref(false)
const importResult = ref(null)
const selectedFile = ref(null)

const handleFileChange = (file) => {
  selectedFile.value = file.raw
  ElMessage.success(`已选择文件: ${file.name}`)
}

const handleExceed = () => {
  ElMessage.warning('只能上传一个文件')
}

async function handleDownloadTemplate() {
  downloadingTemplate.value = true
  try {
    const blob = await downloadImportTemplate()
    const url = window.URL.createObjectURL(new Blob([blob], { type: 'text/csv;charset=utf-8' }))
    const link = document.createElement('a')
    link.href = url
    link.download = '06_采购记录表_核心.csv'
    link.click()
    window.URL.revokeObjectURL(url)
    ElMessage.success('模板已下载')
  } catch (e) {
    ElMessage.error('模板下载失败：' + (e.response?.data?.detail || e.message))
  } finally {
    downloadingTemplate.value = false
  }
}

const handleImport = async () => {
  if (!selectedFile.value) {
    ElMessage.warning('请先选择文件')
    return
  }
  importing.value = true
  importResult.value = null
  try {
    const formData = new FormData()
    formData.append('file', selectedFile.value)
    const stats = await uploadImportFile(formData)
    const failed = stats.failed || 0
    importResult.value = {
      title: failed > 0 ? '导入完成（部分失败）' : '导入成功',
      type: failed > 0 ? 'warning' : 'success',
      description: `成功导入 ${stats.success || 0} 条记录`
        + (stats.duplicates_skipped ? `，去重跳过 ${stats.duplicates_skipped} 条` : ''),
      stats,
      errors: stats.errors || []
    }
    ElMessage.success('导入完成')
  } catch (error) {
    const detail = error.response?.data?.detail || error.message || '导入过程中发生错误'
    importResult.value = {
      title: '导入失败',
      type: 'error',
      description: typeof detail === 'string' ? detail : JSON.stringify(detail)
    }
    ElMessage.error('导入失败')
  } finally {
    importing.value = false
  }
}

const handleReset = () => {
  selectedFile.value = null
  importResult.value = null
  uploadRef.value?.clearFiles()
  ElMessage.info('已重置')
}
</script>

<style scoped>
.data-import { padding: 0; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.card-header h3 { margin: 0; font-size: 18px; }
.upload-demo { width: 100%; }
.action-buttons { display: flex; gap: 10px; }
</style>
