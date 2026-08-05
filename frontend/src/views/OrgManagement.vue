<template>
  <div class="org-management">
    <!-- 页面标题 -->
    <div class="page-header">
      <h2>组织架构管理</h2>
      <p class="subtitle">集团 → 事业部 → 板块 → 公司 四级组织管理</p>
    </div>

    <el-row :gutter="20">
      <!-- 左侧：组织架构树 -->
      <el-col :span="10">
        <el-card shadow="hover" class="tree-card">
          <template #header>
            <div class="card-header">
              <span>组织架构树</span>
              <el-button type="primary" size="small" @click="handleAdd('group')">
                <el-icon><Plus /></el-icon> 新增集团
              </el-button>
            </div>
          </template>

          <div v-if="treeLoading" class="tree-loading">
            <el-skeleton :rows="6" animated />
          </div>

          <el-tree
            v-else
            ref="orgTree"
            :data="treeData"
            :props="treeProps"
            node-key="treeKey"
            :default-expanded-keys="defaultExpandedKeys"
            highlight-current
            @node-click="handleNodeClick"
          >
            <template #default="{ node, data }">
              <div class="tree-node">
                <div class="node-label">
                  <el-icon :size="16" :color="getLevelColor(data.level)">
                    <component :is="getLevelIcon(data.level)" />
                  </el-icon>
                  <span class="node-name">{{ data.name }}</span>
                  <el-tag size="small" :type="getLevelTagType(data.level)" class="level-tag">
                    {{ getLevelLabel(data.level) }}
                  </el-tag>
                </div>
                <div class="node-actions" @click.stop>
                  <el-dropdown trigger="click" @command="(cmd) => handleTreeCommand(cmd, data)">
                    <el-icon class="more-btn"><MoreFilled /></el-icon>
                    <template #dropdown>
                      <el-dropdown-menu>
                        <el-dropdown-item command="add" v-if="data.level !== 'company'">
                          <el-icon><Plus /></el-icon> 新增下级
                        </el-dropdown-item>
                        <el-dropdown-item command="edit">
                          <el-icon><Edit /></el-icon> 编辑
                        </el-dropdown-item>
                        <el-dropdown-item command="delete" divided>
                          <el-icon><Delete /></el-icon> 删除
                        </el-dropdown-item>
                      </el-dropdown-menu>
                    </template>
                  </el-dropdown>
                </div>
              </div>
            </template>
          </el-tree>

          <el-empty v-if="!treeLoading && treeData.length === 0" description="暂无组织数据" />
        </el-card>
      </el-col>

      <!-- 右侧：详情/编辑面板 -->
      <el-col :span="14">
        <!-- 未选中状态 -->
        <el-card v-if="!selectedNode" shadow="hover" class="detail-card">
          <el-empty description="请在左侧选择一个组织节点" />
        </el-card>

        <!-- 选中后详情 -->
        <el-card v-else shadow="hover" class="detail-card">
          <template #header>
            <div class="card-header">
              <span>{{ getLevelLabel(selectedNode.level) }}详情</span>
              <div>
                <el-button size="small" @click="handleEdit(selectedNode)">
                  <el-icon><Edit /></el-icon> 编辑
                </el-button>
                <el-button
                  v-if="selectedNode.level !== 'company'"
                  size="small"
                  type="primary"
                  @click="handleAddChild(selectedNode)"
                >
                  <el-icon><Plus /></el-icon> 新增下级
                </el-button>
                <el-button size="small" type="danger" @click="handleDelete(selectedNode)">
                  <el-icon><Delete /></el-icon> 删除
                </el-button>
              </div>
            </div>
          </template>

          <!-- 集团详情 -->
          <template v-if="selectedNode.level === 'group'">
            <el-descriptions :column="2" border>
              <el-descriptions-item label="集团代码">{{ selectedNode.raw.group_code }}</el-descriptions-item>
              <el-descriptions-item label="集团名称">{{ selectedNode.raw.group_name }}</el-descriptions-item>
              <el-descriptions-item label="描述" :span="2">{{ selectedNode.raw.description || '-' }}</el-descriptions-item>
              <el-descriptions-item label="下属事业部">{{ selectedNode.raw.units?.length || 0 }} 个</el-descriptions-item>
              <el-descriptions-item label="创建时间">{{ formatTime(selectedNode.raw.created_at) }}</el-descriptions-item>
            </el-descriptions>
          </template>

          <!-- 事业部详情 -->
          <template v-if="selectedNode.level === 'unit'">
            <el-descriptions :column="2" border>
              <el-descriptions-item label="事业部代码">{{ selectedNode.raw.unit_code }}</el-descriptions-item>
              <el-descriptions-item label="事业部名称">{{ selectedNode.raw.unit_name }}</el-descriptions-item>
              <el-descriptions-item label="所属集团">{{ getParentName(selectedNode) }}</el-descriptions-item>
              <el-descriptions-item label="下属板块">{{ selectedNode.raw.sectors?.length || 0 }} 个</el-descriptions-item>
              <el-descriptions-item label="描述" :span="2">{{ selectedNode.raw.description || '-' }}</el-descriptions-item>
              <el-descriptions-item label="创建时间" :span="2">{{ formatTime(selectedNode.raw.created_at) }}</el-descriptions-item>
            </el-descriptions>
          </template>

          <!-- 板块详情 -->
          <template v-if="selectedNode.level === 'sector'">
            <el-descriptions :column="2" border>
              <el-descriptions-item label="板块代码">{{ selectedNode.raw.sector_code }}</el-descriptions-item>
              <el-descriptions-item label="板块名称">{{ selectedNode.raw.sector_name }}</el-descriptions-item>
              <el-descriptions-item label="所属事业部">{{ getParentName(selectedNode) }}</el-descriptions-item>
              <el-descriptions-item label="下属公司">{{ selectedNode.raw.companies?.length || 0 }} 个</el-descriptions-item>
              <el-descriptions-item label="描述" :span="2">{{ selectedNode.raw.description || '-' }}</el-descriptions-item>
              <el-descriptions-item label="创建时间" :span="2">{{ formatTime(selectedNode.raw.created_at) }}</el-descriptions-item>
            </el-descriptions>
          </template>

          <!-- 公司详情 -->
          <template v-if="selectedNode.level === 'company'">
            <el-descriptions :column="2" border>
              <el-descriptions-item label="公司代码">{{ selectedNode.raw.company_code || selectedNode.raw.code }}</el-descriptions-item>
              <el-descriptions-item label="公司名称">{{ selectedNode.raw.company_name || selectedNode.raw.name }}</el-descriptions-item>
              <el-descriptions-item label="所属板块">{{ getParentName(selectedNode) }}</el-descriptions-item>
              <el-descriptions-item label="税号">{{ selectedNode.raw.tax_number || '-' }}</el-descriptions-item>
              <el-descriptions-item label="描述" :span="2">{{ selectedNode.raw.description || '-' }}</el-descriptions-item>
              <el-descriptions-item label="创建时间" :span="2">{{ formatTime(selectedNode.raw.created_at) }}</el-descriptions-item>
            </el-descriptions>
          </template>
        </el-card>
      </el-col>
    </el-row>

    <!-- 新增/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="520px"
      destroy-on-close
    >
      <el-form
        ref="formRef"
        :model="formData"
        :rules="formRules"
        label-width="100px"
        label-position="right"
      >
        <!-- 集团表单 -->
        <template v-if="formLevel === 'group'">
          <el-form-item label="集团代码" prop="group_code">
            <el-input v-model="formData.group_code" placeholder="请输入集团代码" />
          </el-form-item>
          <el-form-item label="集团名称" prop="group_name">
            <el-input v-model="formData.group_name" placeholder="请输入集团名称" />
          </el-form-item>
          <el-form-item label="描述" prop="description">
            <el-input v-model="formData.description" type="textarea" :rows="3" placeholder="请输入描述" />
          </el-form-item>
        </template>

        <!-- 事业部表单 -->
        <template v-if="formLevel === 'unit'">
          <el-form-item label="所属集团" prop="group_id">
            <el-select v-model="formData.group_id" placeholder="请选择所属集团" style="width:100%">
              <el-option v-for="g in groups" :key="g.id" :label="g.group_name" :value="g.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="事业部代码" prop="unit_code">
            <el-input v-model="formData.unit_code" placeholder="请输入事业部代码" />
          </el-form-item>
          <el-form-item label="事业部名称" prop="unit_name">
            <el-input v-model="formData.unit_name" placeholder="请输入事业部名称" />
          </el-form-item>
          <el-form-item label="描述" prop="description">
            <el-input v-model="formData.description" type="textarea" :rows="3" placeholder="请输入描述" />
          </el-form-item>
        </template>

        <!-- 板块表单 -->
        <template v-if="formLevel === 'sector'">
          <el-form-item label="所属事业部" prop="unit_id">
            <el-select v-model="formData.unit_id" placeholder="请选择所属事业部" style="width:100%">
              <el-option v-for="u in units" :key="u.id" :label="u.unit_name" :value="u.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="板块代码" prop="sector_code">
            <el-input v-model="formData.sector_code" placeholder="请输入板块代码" />
          </el-form-item>
          <el-form-item label="板块名称" prop="sector_name">
            <el-input v-model="formData.sector_name" placeholder="请输入板块名称" />
          </el-form-item>
          <el-form-item label="描述" prop="description">
            <el-input v-model="formData.description" type="textarea" :rows="3" placeholder="请输入描述" />
          </el-form-item>
        </template>

        <!-- 公司表单 -->
        <template v-if="formLevel === 'company'">
          <el-form-item label="所属板块" prop="sector_id">
            <el-select v-model="formData.sector_id" placeholder="请选择所属板块" style="width:100%">
              <el-option v-for="s in sectors" :key="s.id" :label="s.sector_name" :value="s.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="公司代码" prop="company_code">
            <el-input v-model="formData.company_code" placeholder="请输入公司代码" />
          </el-form-item>
          <el-form-item label="公司名称" prop="company_name">
            <el-input v-model="formData.company_name" placeholder="请输入公司名称" />
          </el-form-item>
          <el-form-item label="税号" prop="tax_number">
            <el-input v-model="formData.tax_number" placeholder="请输入税号" />
          </el-form-item>
          <el-form-item label="描述" prop="description">
            <el-input v-model="formData.description" type="textarea" :rows="3" placeholder="请输入描述" />
          </el-form-item>
        </template>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitLoading">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Plus, Edit, Delete, MoreFilled,
  OfficeBuilding, Grid, Histogram, HomeFilled
} from '@element-plus/icons-vue'
import {
  getOrgTree, getGroups, getUnits, getSectors, getCompany,
  createGroup, updateGroup, deleteGroup,
  createUnit, updateUnit, deleteUnit,
  createSector, updateSector, deleteSector,
  createCompany, updateCompany, deleteCompany
} from '../api/org'

// ========== 数据状态 ==========
const treeLoading = ref(false)
const submitLoading = ref(false)
const orgTree = ref(null)
const rawTree = ref([])  // API原始树数据
const groups = ref([])
const units = ref([])
const sectors = ref([])
const selectedNode = ref(null)
const dialogVisible = ref(false)
const formRef = ref(null)
const isEdit = ref(false)
const formLevel = ref('group')

const formData = ref({})
const formRules = computed(() => {
  const required = (label) => [{ required: true, message: `请输入${label}`, trigger: 'blur' }]
  const selectRequired = (label) => [{ required: true, message: `请选择${label}`, trigger: 'change' }]
  switch (formLevel.value) {
    case 'group':
      return { group_code: required('集团代码'), group_name: required('集团名称') }
    case 'unit':
      return { group_id: selectRequired('所属集团'), unit_code: required('事业部代码'), unit_name: required('事业部名称') }
    case 'sector':
      return { unit_id: selectRequired('所属事业部'), sector_code: required('板块代码'), sector_name: required('板块名称') }
    case 'company':
      return { sector_id: selectRequired('所属板块'), company_code: required('公司代码'), company_name: required('公司名称') }
    default:
      return {}
  }
})

// ========== 树数据处理 ==========
const treeProps = {
  children: 'children',
  label: 'name'
}

// 默认只展开到事业部（不展开板块和公司）
const defaultExpandedKeys = computed(() => {
  const keys = []
  for (const group of treeData.value) {
    keys.push(group.treeKey)
    if (group.children) {
      for (const unit of group.children) {
        keys.push(unit.treeKey)
      }
    }
  }
  return keys
})

// 将API原始数据转为el-tree可用的格式
const treeData = computed(() => {
  return buildTreeData(rawTree.value)
})

function buildTreeData(apiData) {
  if (!apiData || !Array.isArray(apiData)) return []
  return apiData.map(group => {
    const groupNode = {
      treeKey: `group-${group.id}`,
      name: group.name,
      code: group.code,
      level: 'group',
      raw: group,
      children: []
    }
    if (group.units && Array.isArray(group.units)) {
      groupNode.children = group.units.map(unit => {
        const unitNode = {
          treeKey: `unit-${unit.id}`,
          name: unit.name,
          code: unit.code,
          level: 'unit',
          raw: unit,
          parentName: group.name,
          children: []
        }
        if (unit.sectors && Array.isArray(unit.sectors)) {
          unitNode.children = unit.sectors.map(sector => {
            const sectorNode = {
              treeKey: `sector-${sector.id}`,
              name: sector.name,
              code: sector.code,
              level: 'sector',
              raw: sector,
              parentName: unit.name,
              children: []
            }
            if (sector.companies && Array.isArray(sector.companies)) {
              sectorNode.children = sector.companies.map(company => ({
                treeKey: `company-${company.id}`,
                name: company.name,
                code: company.code,
                level: 'company',
                raw: company,
                parentName: sector.name,
                children: []
              }))
            }
            return sectorNode
          })
        }
        return unitNode
      })
    }
    return groupNode
  })
}

// ========== 辅助函数 ==========
function getLevelLabel(level) {
  const map = { group: '集团', unit: '事业部', sector: '板块', company: '公司' }
  return map[level] || level
}

function getLevelIcon(level) {
  const map = { group: OfficeBuilding, unit: Grid, sector: Histogram, company: HomeFilled }
  return map[level] || OfficeBuilding
}

function getLevelColor(level) {
  const map = { group: '#E6A23C', unit: '#409EFF', sector: '#67C23A', company: '#909399' }
  return map[level] || '#409EFF'
}

function getLevelTagType(level) {
  const map = { group: 'warning', unit: '', sector: 'success', company: 'info' }
  return map[level] || ''
}

function getParentName(node) {
  return node.parentName || '-'
}

function formatTime(t) {
  if (!t) return '-'
  return t.replace('T', ' ').substring(0, 19)
}

// ========== 数据加载 ==========
async function loadTree() {
  treeLoading.value = true
  try {
    const data = await getOrgTree()
    rawTree.value = data || []
  } catch (e) {
    console.error('加载组织树失败:', e)
  } finally {
    treeLoading.value = false
  }
}

async function loadOptions() {
  try {
    const [g, u, s] = await Promise.all([getGroups(), getUnits(), getSectors()])
    groups.value = g || []
    units.value = u || []
    sectors.value = s || []
  } catch (e) {
    console.error('加载选项失败:', e)
  }
}

// ========== 节点操作 ==========
async function handleNodeClick(data) {
  selectedNode.value = data
  // 公司节点：树数据只有 id/code/name/sector_id，需要加载完整字段
  if (data.level === 'company') {
    try {
      const detail = await getCompany(data.raw.id)
      // 把完整数据合并到 raw，让详情面板能正确显示
      data.raw = { ...data.raw, ...detail, company_code: detail.company_code, company_name: detail.company_name }
      // 触发响应式更新
      selectedNode.value = { ...data }
    } catch (e) {
      console.error('加载公司详情失败:', e)
    }
  }
}

function handleTreeCommand(cmd, data) {
  if (cmd === 'add') handleAddChild(data)
  else if (cmd === 'edit') handleEdit(data)
  else if (cmd === 'delete') handleDelete(data)
}

// ========== 新增 ==========
function handleAdd(level) {
  isEdit.value = false
  formLevel.value = level
  formData.value = {}
  dialogVisible.value = true
}

function handleAddChild(parentNode) {
  const childLevelMap = { group: 'unit', unit: 'sector', sector: 'company' }
  const childLevel = childLevelMap[parentNode.level]
  if (!childLevel) return

  isEdit.value = false
  formLevel.value = childLevel
  formData.value = {}

  // 自动填充父级ID
  if (childLevel === 'unit') formData.value.group_id = parentNode.raw.id
  if (childLevel === 'sector') formData.value.unit_id = parentNode.raw.id
  if (childLevel === 'company') formData.value.sector_id = parentNode.raw.id

  dialogVisible.value = true
}

// ========== 编辑 ==========
async function handleEdit(node) {
  isEdit.value = true
  formLevel.value = node.level
  const raw = node.raw

  switch (node.level) {
    case 'group':
      formData.value = { group_code: raw.group_code, group_name: raw.group_name, description: raw.description }
      break
    case 'unit':
      formData.value = { unit_code: raw.unit_code, unit_name: raw.unit_name, group_id: raw.group_id, description: raw.description }
      break
    case 'sector':
      formData.value = { sector_code: raw.sector_code, sector_name: raw.sector_name, unit_id: raw.unit_id, description: raw.description }
      break
    case 'company': {
      // 树节点只有 id/code/name/sector_id，需要通过详情 API 获取完整字段
      const detail = await getCompany(raw.id)
      formData.value = {
        company_code: detail.company_code, company_name: detail.company_name,
        sector_id: detail.sector_id, tax_number: detail.tax_number,
        contact_person: detail.contact_person, contact_phone: detail.contact_phone,
        address: detail.address, description: detail.description
      }
      break
    }
  }
  // 保存原始ID供更新用
  formData.value._id = raw.id
  dialogVisible.value = true
}

// ========== 删除 ==========
async function handleDelete(node) {
  const levelLabel = getLevelLabel(node.level)
  try {
    await ElMessageBox.confirm(
      `确定要删除${levelLabel}「${node.name}」吗？${node.level !== 'company' ? '删除前请先移除所有下级组织。' : ''}`,
      '确认删除',
      { type: 'warning' }
    )

    let ok = false
    const id = node.raw.id
    switch (node.level) {
      case 'group': ok = await deleteGroup(id); break
      case 'unit': ok = await deleteUnit(id); break
      case 'sector': ok = await deleteSector(id); break
      case 'company': ok = await deleteCompany(id); break
    }

    if (ok !== false) {
      ElMessage.success('删除成功')
      selectedNode.value = null
      await Promise.all([loadTree(), loadOptions()])
    }
  } catch (e) {
    if (e?.response?.data?.detail) {
      ElMessage.error(e.response.data.detail)
    }
  }
}

// ========== 提交 ==========
async function handleSubmit() {
  if (!formRef.value) return
  await formRef.value.validate()

  submitLoading.value = true
  try {
    const id = formData.value._id
    const data = { ...formData.value }
    delete data._id

    switch (formLevel.value) {
      case 'group':
        isEdit.value ? await updateGroup(id, data) : await createGroup(data)
        break
      case 'unit':
        isEdit.value ? await updateUnit(id, data) : await createUnit(data)
        break
      case 'sector':
        isEdit.value ? await updateSector(id, data) : await createSector(data)
        break
      case 'company':
        isEdit.value ? await updateCompany(id, data) : await createCompany(data)
        break
    }

    ElMessage.success(isEdit.value ? '更新成功' : '创建成功')
    dialogVisible.value = false
    selectedNode.value = null
    await Promise.all([loadTree(), loadOptions()])
  } catch (e) {
    const msg = e?.response?.data?.detail || e?.message || '操作失败'
    ElMessage.error(msg)
  } finally {
    submitLoading.value = false
  }
}

// ========== 初始化 ==========
onMounted(async () => {
  await Promise.all([loadTree(), loadOptions()])
})
</script>

<style scoped>
.org-management {
  padding: 0;
}

.page-header {
  margin-bottom: 20px;
}

.page-header h2 {
  font-size: 20px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 4px;
}

.page-header .subtitle {
  font-size: 13px;
  color: #909399;
}

.tree-card,
.detail-card {
  min-height: 600px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header span {
  font-weight: 600;
  font-size: 15px;
}

.tree-node {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding-right: 8px;
}

.node-label {
  display: flex;
  align-items: center;
  gap: 6px;
}

.node-name {
  font-size: 14px;
  color: #303133;
}

.level-tag {
  margin-left: 4px;
  transform: scale(0.85);
}

.node-actions {
  display: none;
}

.tree-node:hover .node-actions {
  display: flex;
}

.more-btn {
  cursor: pointer;
  color: #909399;
  font-size: 16px;
  padding: 2px 4px;
  border-radius: 4px;
}

.more-btn:hover {
  color: #409EFF;
  background: #ecf5ff;
}

.tree-loading {
  padding: 20px;
}

:deep(.el-tree-node__content) {
  height: 36px;
}

:deep(.el-descriptions__label) {
  font-weight: 500;
  width: 100px;
}
</style>
