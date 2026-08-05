<template>
  <div class="user-management">
    <div class="page-header">
      <h3>用户与权限管理</h3>
      <div class="header-actions">
        <el-button type="primary" :icon="Plus" @click="openCreateDialog">新建用户</el-button>
        <el-button type="success" plain :icon="Upload" @click="csvDialogVisible = true">CSV 批量导入</el-button>
      </div>
    </div>

    <!-- 用户列表 -->
    <el-table :data="users" stripe v-loading="loading" style="width: 100%">
      <el-table-column prop="username" label="用户名" width="120" />
      <el-table-column prop="real_name" label="姓名" width="120" />
      <el-table-column prop="email" label="邮箱" width="180" show-overflow-tooltip />
      <el-table-column prop="role" label="角色" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="row.role === 'admin' ? 'danger' : 'primary'" size="small" effect="dark">
            {{ row.role === 'admin' ? '管理员' : '普通用户' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="is_active" label="状态" width="80" align="center">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
            {{ row.is_active ? '启用' : '禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="授权公司" min-width="200">
        <template #default="{ row }">
          <template v-if="row.role === 'admin'">
            <el-tag type="warning" size="small">全部公司</el-tag>
          </template>
          <template v-else-if="row.company_codes && row.company_codes.length > 0">
            <el-tag v-for="c in row.company_codes.slice(0, 5)" :key="c" size="small" style="margin: 2px">
              {{ c }}
            </el-tag>
            <el-tag v-if="row.company_codes.length > 5" size="small" type="info">
              +{{ row.company_codes.length - 5 }}
            </el-tag>
          </template>
          <template v-else>
            <span style="color: #909399">未授权</span>
          </template>
        </template>
      </el-table-column>
      <el-table-column prop="last_login" label="最后登录" width="160">
        <template #default="{ row }">{{ row.last_login || '-' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="220" align="center" fixed="right">
        <template #default="{ row }">
          <el-button size="small" text type="primary" @click="openEditDialog(row)">编辑</el-button>
          <el-button size="small" text type="warning" @click="handleResetPwd(row)">重置密码</el-button>
          <el-button size="small" text type="danger" @click="handleDelete(row)" :disabled="row.username === 'admin'">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 新建/编辑用户弹窗 -->
    <el-dialog v-model="userDialogVisible" :title="isEdit ? '编辑用户' : '新建用户'" width="560px">
      <el-form :model="userForm" :rules="userRules" ref="userFormRef" label-width="80px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="userForm.username" :disabled="isEdit" placeholder="登录用户名" />
        </el-form-item>
        <el-form-item label="姓名" prop="real_name">
          <el-input v-model="userForm.real_name" placeholder="真实姓名" />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="userForm.email" placeholder="邮箱地址" />
        </el-form-item>
        <el-form-item label="角色" prop="role">
          <el-radio-group v-model="userForm.role">
            <el-radio value="user">普通用户</el-radio>
            <el-radio value="admin">管理员</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="状态" v-if="isEdit">
          <el-switch v-model="userForm.is_active" active-text="启用" inactive-text="禁用" />
        </el-form-item>

        <!-- 公司授权（仅普通用户） -->
        <el-form-item label="授权公司" v-if="userForm.role === 'user'">
          <div class="company-selector">
            <div class="selector-header">
              <el-tag type="info" size="small">已选 {{ selectedCompanyCodes.length }} 家公司</el-tag>
              <el-button size="small" text type="primary" @click="selectAllCompanies">全选</el-button>
              <el-button size="small" text @click="selectedCompanyCodes = []">清空</el-button>
            </div>
            <div class="org-tree-scroll" v-loading="companyLoading">
              <div v-for="group in orgGroups" :key="group.id" class="tree-group">
                <div class="tree-node-label" @click="toggleNode(group.id)">
                  <el-icon><ArrowRight v-if="!expanded[group.id]" /><ArrowDown v-else /></el-icon>
                  <span class="node-text">{{ group.name }}</span>
                  <el-button size="small" text @click.stop="selectGroupCompanies(group)">选全部</el-button>
                </div>
                <div v-if="expanded[group.id]" class="tree-children">
                  <div v-for="unit in group.units || []" :key="unit.id" class="tree-unit">
                    <div class="tree-node-label" @click="toggleNode('u' + unit.id)">
                      <el-icon><ArrowRight v-if="!expanded['u' + unit.id]" /><ArrowDown v-else /></el-icon>
                      <span class="node-text">{{ unit.name }}</span>
                      <el-button size="small" text @click.stop="selectUnitCompanies(unit)">选全部</el-button>
                    </div>
                    <div v-if="expanded['u' + unit.id]" class="tree-children">
                      <div v-for="sector in unit.sectors || []" :key="sector.id" class="tree-sector">
                        <div class="tree-node-label" @click="toggleNode('s' + sector.id)">
                          <el-icon><ArrowRight v-if="!expanded['s' + sector.id]" /><ArrowDown v-else /></el-icon>
                          <span class="node-text">{{ sector.name }}</span>
                          <el-button size="small" text @click.stop="selectSectorCompanies(sector)">选全部</el-button>
                        </div>
                        <div v-if="expanded['s' + sector.id]" class="tree-children">
                          <div v-for="company in sector.companies || []" :key="company.code" class="tree-company">
                            <el-checkbox
                              :model-value="selectedCompanyCodes.includes(company.code)"
                              @change="(val) => toggleCompany(company.code, val)"
                            >
                              {{ company.code }} - {{ company.name }}
                            </el-checkbox>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="userDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSaveUser">保存</el-button>
      </template>
    </el-dialog>

    <!-- CSV 导入弹窗 -->
    <el-dialog v-model="csvDialogVisible" title="CSV 批量导入用户" width="520px">
      <el-alert type="info" :closable="false" style="margin-bottom: 16px">
        <p>CSV 文件格式：<code>username,real_name,role,company_codes</code></p>
        <p>company_codes 用分号分隔，如：<code>1000;2000;D230</code></p>
        <p>role 可选值：<code>admin</code> 或 <code>user</code>（默认 user）</p>
      </el-alert>
      <el-upload
        ref="uploadRef"
        :auto-upload="false"
        :limit="1"
        accept=".csv"
        :on-change="handleFileChange"
        drag
      >
        <el-icon style="font-size: 40px; color: #c0c4cc"><Upload /></el-icon>
        <div>拖拽 CSV 文件到此处，或点击上传</div>
      </el-upload>
      <template #footer>
        <el-button @click="csvDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="importing" :disabled="!csvFile" @click="handleImport">导入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Upload, ArrowRight, ArrowDown } from '@element-plus/icons-vue'
import { getUsers, createUser, updateUser, deleteUser, resetPassword, importUsers } from '../api/user'
import { getOrgTree } from '../api/org'

const loading = ref(false)
const users = ref([])
const orgGroups = ref([])
const companyLoading = ref(false)

// 用户表单
const userDialogVisible = ref(false)
const isEdit = ref(false)
const editingUserId = ref(null)
const saving = ref(false)
const userFormRef = ref(null)
const selectedCompanyCodes = ref([])

const userForm = reactive({
  username: '',
  real_name: '',
  email: '',
  role: 'user',
  is_active: true,
})

const userRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
}

// 树展开状态
const expanded = reactive({})

// CSV 导入
const csvDialogVisible = ref(false)
const csvFile = ref(null)
const importing = ref(false)
const uploadRef = ref(null)

onMounted(() => {
  loadUsers()
  loadOrgTree()
})

async function loadUsers() {
  loading.value = true
  try {
    users.value = await getUsers()
  } catch (e) {
    ElMessage.error('加载用户列表失败')
  } finally {
    loading.value = false
  }
}

async function loadOrgTree() {
  companyLoading.value = true
  try {
    orgGroups.value = await getOrgTree()
    // 默认展开第一层
    if (orgGroups.value.length > 0) {
      expanded[orgGroups.value[0].id] = true
    }
  } catch (e) {
    console.error('加载组织架构失败:', e)
  } finally {
    companyLoading.value = false
  }
}

function toggleNode(key) {
  expanded[key] = !expanded[key]
}

function toggleCompany(code, checked) {
  if (checked) {
    if (!selectedCompanyCodes.value.includes(code)) {
      selectedCompanyCodes.value.push(code)
    }
  } else {
    selectedCompanyCodes.value = selectedCompanyCodes.value.filter(c => c !== code)
  }
}

function getAllCompaniesFromNode(node) {
  const codes = []
  if (node.companies) {
    node.companies.forEach(c => codes.push(c.code))
  }
  if (node.sectors) {
    node.sectors.forEach(s => codes.push(...getAllCompaniesFromNode(s)))
  }
  if (node.units) {
    node.units.forEach(u => codes.push(...getAllCompaniesFromNode(u)))
  }
  return codes
}

function selectGroupCompanies(group) {
  const codes = getAllCompaniesFromNode(group)
  addCodes(codes)
}

function selectUnitCompanies(unit) {
  const codes = getAllCompaniesFromNode(unit)
  addCodes(codes)
}

function selectSectorCompanies(sector) {
  const codes = getAllCompaniesFromNode(sector)
  addCodes(codes)
}

function addCodes(codes) {
  const set = new Set([...selectedCompanyCodes.value, ...codes])
  selectedCompanyCodes.value = [...set]
}

function selectAllCompanies() {
  selectedCompanyCodes.value = getAllCompaniesFromNode({ units: orgGroups.value.flatMap(g => g.units || []) })
}

function openCreateDialog() {
  isEdit.value = false
  editingUserId.value = null
  userForm.username = ''
  userForm.real_name = ''
  userForm.email = ''
  userForm.role = 'user'
  userForm.is_active = true
  selectedCompanyCodes.value = []
  userDialogVisible.value = true
}

function openEditDialog(row) {
  isEdit.value = true
  editingUserId.value = row.id
  userForm.username = row.username
  userForm.real_name = row.real_name || ''
  userForm.email = row.email || ''
  userForm.role = row.role
  userForm.is_active = row.is_active
  selectedCompanyCodes.value = [...(row.company_codes || [])]
  userDialogVisible.value = true
}

async function handleSaveUser() {
  await userFormRef.value?.validate()
  saving.value = true
  try {
    if (isEdit.value) {
      await updateUser(editingUserId.value, {
        real_name: userForm.real_name,
        email: userForm.email,
        role: userForm.role,
        is_active: userForm.is_active,
        company_codes: userForm.role === 'user' ? selectedCompanyCodes.value : [],
      })
      ElMessage.success('更新成功')
    } else {
      await createUser({
        username: userForm.username,
        real_name: userForm.real_name,
        email: userForm.email,
        role: userForm.role,
        company_codes: userForm.role === 'user' ? selectedCompanyCodes.value : [],
      })
      ElMessage.success('创建成功')
    }
    userDialogVisible.value = false
    loadUsers()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  } finally {
    saving.value = false
  }
}

async function handleDelete(row) {
  await ElMessageBox.confirm(`确定删除用户 "${row.username}"？`, '确认删除', { type: 'warning' })
  try {
    await deleteUser(row.id)
    ElMessage.success('删除成功')
    loadUsers()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}

async function handleResetPwd(row) {
  await ElMessageBox.confirm(`确定将 "${row.username}" 的密码重置为默认密码？`, '重置密码', { type: 'warning' })
  try {
    await resetPassword(row.id)
    ElMessage.success('密码已重置，用户下次登录需修改密码')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '重置失败')
  }
}

function handleFileChange(file) {
  csvFile.value = file.raw
}

async function handleImport() {
  if (!csvFile.value) return
  importing.value = true
  try {
    const res = await importUsers(csvFile.value)
    ElMessage.success(`导入完成: 成功 ${res.success} 条, 失败 ${res.failed} 条`)
    csvDialogVisible.value = false
    csvFile.value = null
    loadUsers()
  } catch (e) {
    ElMessage.error('导入失败')
  } finally {
    importing.value = false
  }
}
</script>

<style scoped>
.user-management {
  padding: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h3 {
  font-size: 18px;
  font-weight: 600;
  margin: 0;
}

.company-selector {
  width: 100%;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  padding: 8px;
}

.selector-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid #ebeef5;
}

.org-tree-scroll {
  max-height: 300px;
  overflow-y: auto;
}

.tree-children {
  padding-left: 20px;
}

.tree-node-label {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 0;
  cursor: pointer;
  font-size: 13px;
}

.tree-node-label:hover {
  background: #f5f7fa;
}

.node-text {
  flex: 1;
}

.tree-company {
  padding: 2px 0;
}
</style>
