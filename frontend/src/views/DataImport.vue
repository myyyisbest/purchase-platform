<template>
  <div class="data-import">
    <el-card>
      <template #header>
        <div class="card-header">
          <h3>数据导入</h3>
        </div>
      </template>
      
      <!-- 上传区域 -->
      <el-upload
        ref="uploadRef"
        class="upload-demo"
        drag
        action="#"
        :auto-upload="false"
        :on-change="handleFileChange"
        :limit="1"
        :on-exceed="handleExceed"
        accept=".xlsx,.xls"
      >
        <el-icon class="el-icon--upload"><upload-filled /></el-icon>
        <div class="el-upload__text">
          将Excel文件拖到此处，或 <em>点击上传</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">
            只能上传 .xlsx / .xls 文件，且不超过 50MB
          </div>
        </template>
      </el-upload>
      
      <!-- 操作按钮 -->
      <div class="action-buttons" style="margin-top: 20px;">
        <el-button type="primary" @click="handleImport" :loading="importing">
          开始导入
        </el-button>
        <el-button @click="handleReset">
          重置
        </el-button>
      </div>
      
      <!-- 导入结果 -->
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
        </el-table>
        
        <div v-if="importResult.errors && importResult.errors.length > 0" style="margin-top: 20px;">
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
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import axios from 'axios'

const uploadRef = ref()
const importing = ref(false)
const importResult = ref(null)
const selectedFile = ref(null)

// 处理文件选择
const handleFileChange = (file) => {
  selectedFile.value = file.raw
  ElMessage.success(`已选择文件: ${file.name}`)
}

// 处理文件超出限制
const handleExceed = () => {
  ElMessage.warning('只能上传一个文件')
}

// 处理导入
const handleImport = async () => {
  if (!selectedFile.value) {
    ElMessage.warning('请先选择文件')
    return
  }
  
  importing.value = true
  importResult.value = null
  
  try {
    // 创建FormData
    const formData = new FormData()
    formData.append('file', selectedFile.value)
    
    // 发送请求
    // 使用 axios 实例的 baseURL，避免硬编码地址
    const response = await axios.post('/api/import/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
    
    // 处理响应
    if (response.data.code === 200) {
      const stats = response.data.data
      importResult.value = {
        title: '导入成功',
        type: 'success',
        description: `成功导入 ${stats.success} 条记录`,
        stats: stats,
        errors: stats.errors
      }
      ElMessage.success('导入成功')
    } else {
      throw new Error(response.data.message)
    }
    
  } catch (error) {
    importResult.value = {
      title: '导入失败',
      type: 'error',
      description: error.message || '导入过程中发生错误'
    }
    ElMessage.error('导入失败')
  } finally {
    importing.value = false
  }
}

// 处理重置
const handleReset = () => {
  selectedFile.value = null
  importResult.value = null
  uploadRef.value?.clearFiles()
  ElMessage.info('已重置')
}
</script>

<style scoped>
.data-import {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header h3 {
  margin: 0;
  font-size: 18px;
}

.upload-demo {
  width: 100%;
}

.action-buttons {
  display: flex;
  gap: 10px;
}
</style>
