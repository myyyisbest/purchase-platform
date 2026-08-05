<template>
  <div class="org-filter" style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
    <el-select
      v-model="selectedGroup"
      placeholder="全部集团"
      clearable
      style="width: 130px"
      @change="onGroupChange"
      @clear="onClear"
    >
      <el-option v-for="g in groups" :key="g.id" :label="g.name" :value="g.id" />
    </el-select>

    <el-select
      v-model="selectedUnit"
      placeholder="全部事业部"
      clearable
      :disabled="!selectedGroup"
      style="width: 140px"
      @change="onUnitChange"
      @clear="onUnitClear"
    >
      <el-option v-for="u in units" :key="u.id" :label="u.name" :value="u.id" />
    </el-select>

    <el-select
      v-model="selectedSector"
      placeholder="全部板块"
      clearable
      :disabled="!selectedUnit"
      style="width: 130px"
      @change="onSectorChange"
      @clear="onSectorClear"
    >
      <el-option v-for="s in sectors" :key="s.id" :label="s.name" :value="s.id" />
    </el-select>

    <el-select
      v-model="selectedCompany"
      placeholder="全部公司"
      clearable
      :disabled="!selectedSector"
      filterable
      style="width: 180px"
      @change="onCompanyChange"
      @clear="onCompanyClear"
    >
      <el-option v-for="c in companies" :key="c.id" :label="c.name" :value="c.code" />
    </el-select>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getOrgHierarchy } from '../api/org'

const emit = defineEmits(['change'])

// 层级数据
const hierarchy = ref([])
const groups = ref([])
const units = ref([])
const sectors = ref([])
const companies = ref([])

// 选中状态
const selectedGroup = ref(null)
const selectedUnit = ref(null)
const selectedSector = ref(null)
const selectedCompany = ref(null)

// 查找当前选中的层级节点
function findGroup(id) { return hierarchy.value.find(g => g.id === id) }
function findUnit(group, id) { return group?.units?.find(u => u.id === id) }
function findSector(unit, id) { return unit?.sectors?.find(s => s.id === id) }

// 提取某个层级下所有公司代码
function collectCompanyCodes(node, level) {
  const codes = []
  if (level === 'company' && node.code) {
    codes.push(node.code)
  } else if (level === 'sector' && node.companies) {
    node.companies.forEach(c => codes.push(c.code))
  } else if (level === 'unit' && node.sectors) {
    node.sectors.forEach(s => s.companies?.forEach(c => codes.push(c.code)))
  } else if (level === 'group' && node.units) {
    node.units.forEach(u => u.sectors?.forEach(s => s.companies?.forEach(c => codes.push(c.code))))
  }
  return codes
}

function emitChange() {
  const codes = []
  if (selectedCompany.value) {
    codes.push(selectedCompany.value)
    emit('change', { level: 'company', companyCodes: codes, companyName: companies.value.find(c => c.code === selectedCompany.value)?.name })
  } else if (selectedSector.value) {
    const g = findGroup(selectedGroup.value)
    const u = findUnit(g, selectedUnit.value)
    const s = findSector(u, selectedSector.value)
    if (s) codes.push(...collectCompanyCodes(s, 'sector'))
    emit('change', { level: 'sector', companyCodes: codes })
  } else if (selectedUnit.value) {
    const g = findGroup(selectedGroup.value)
    const u = findUnit(g, selectedUnit.value)
    if (u) codes.push(...collectCompanyCodes(u, 'unit'))
    emit('change', { level: 'unit', companyCodes: codes })
  } else if (selectedGroup.value) {
    const g = findGroup(selectedGroup.value)
    if (g) codes.push(...collectCompanyCodes(g, 'group'))
    emit('change', { level: 'group', companyCodes: codes })
  } else {
    emit('change', { level: 'all', companyCodes: [] })
  }
}

function onGroupChange(val) {
  selectedUnit.value = null
  selectedSector.value = null
  selectedCompany.value = null
  units.value = []
  sectors.value = []
  companies.value = []
  if (val) {
    const g = findGroup(val)
    units.value = g?.units || []
  }
  emitChange()
}

function onUnitChange(val) {
  selectedSector.value = null
  selectedCompany.value = null
  sectors.value = []
  companies.value = []
  if (val) {
    const g = findGroup(selectedGroup.value)
    const u = findUnit(g, val)
    sectors.value = u?.sectors || []
  }
  emitChange()
}

function onSectorChange(val) {
  selectedCompany.value = null
  companies.value = []
  if (val) {
    const g = findGroup(selectedGroup.value)
    const u = findUnit(g, selectedUnit.value)
    const s = findSector(u, val)
    companies.value = s?.companies || []
  }
  emitChange()
}

function onCompanyChange() { emitChange() }
function onClear() { onGroupChange(null) }
function onUnitClear() { selectedUnit.value = null; onUnitChange(null) }
function onSectorClear() { selectedSector.value = null; onSectorChange(null) }
function onCompanyClear() { selectedCompany.value = null; emitChange() }

onMounted(async () => {
  try {
    hierarchy.value = await getOrgHierarchy()
    groups.value = hierarchy.value.map(g => ({ id: g.id, code: g.code, name: g.name }))
    // 默认选中第一个集团（如果有且只有一个）
    if (groups.value.length === 1) {
      selectedGroup.value = groups.value[0].id
      onGroupChange(selectedGroup.value)
    }
  } catch (e) {
    console.error('加载组织层级失败:', e)
  }
})
</script>
