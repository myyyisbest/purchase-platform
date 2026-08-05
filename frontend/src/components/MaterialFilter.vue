<template>
  <div class="material-filter" style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
    <!-- 物料编码/名称模糊搜索 -->
    <el-autocomplete
      v-model="materialKeyword"
      :fetch-suggestions="handleMaterialSearch"
      placeholder="物料编码/名称（模糊）"
      clearable
      style="width: 240px"
      :trigger-on-focus="false"
      value-key="material_code"
      @select="handleMaterialSelect"
      @clear="handleMaterialClear"
    >
      <template #default="{ item }">
        <div style="display:flex; align-items:center; gap:8px;">
          <span style="font-family: monospace; color: #409EFF; min-width: 80px;">{{ item.material_code }}</span>
          <span style="flex:1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{{ item.material_name }}</span>
        </div>
      </template>
    </el-autocomplete>

    <!-- 物料大类下拉 -->
    <el-select
      v-model="majorCategory"
      placeholder="全部物料大类"
      clearable
      filterable
      style="width: 180px"
      @change="emitChange"
      @clear="emitChange"
    >
      <el-option
        v-for="cat in majorCategoryOptions"
        :key="cat"
        :label="cat"
        :value="cat"
      />
    </el-select>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { getMajorCategoryOptions } from '../api/materialMajorCategory'
import { searchMaterialsFromRecords } from '../api/dashboard'

const props = defineProps({
  // 限定公司代码（用于按公司范围过滤，可选）
  companyCodes: { type: Array, default: () => [] },
  // 物料精确编码（v-model 双向绑定）
  modelMaterialCode: { type: String, default: '' },
  // 物料模糊关键词（双向）
  modelMaterialKeyword: { type: String, default: '' },
  // 物料大类（双向）
  modelMajorCategory: { type: String, default: '' }
})

const emit = defineEmits(['change'])

// 状态
const materialKeyword = ref(props.modelMaterialKeyword || '')
const materialCode = ref(props.modelMaterialCode || '')
const majorCategory = ref(props.modelMajorCategory || '')
const majorCategoryOptions = ref([])

// 当外部 props 变化时同步
watch(() => props.modelMaterialKeyword, v => { materialKeyword.value = v || '' })
watch(() => props.modelMaterialCode, v => { materialCode.value = v || '' })
watch(() => props.modelMajorCategory, v => { majorCategory.value = v || '' })

// 监听 companyCodes 变化重新拉大类下拉
watch(() => props.companyCodes, () => { loadMajorCategories() }, { deep: true })

// 模糊搜索物料（从采购记录中搜索）
async function handleMaterialSearch(query, cb) {
  if (!query || query.length < 1) { cb([]); return }
  try {
    const items = await searchMaterialsFromRecords(query, 20, props.companyCodes?.length > 0 ? props.companyCodes : undefined)
    cb(items || [])
  } catch (e) {
    console.error('物料搜索失败:', e)
    cb([])
  }
}

function handleMaterialSelect(item) {
  materialCode.value = item.material_code
  materialKeyword.value = item.material_code
  emitChange()
}

function handleMaterialClear() {
  materialCode.value = ''
  materialKeyword.value = ''
  emitChange()
}

function emitChange() {
  emit('change', {
    materialCode: materialCode.value,
    materialKeyword: materialKeyword.value,
    majorCategory: majorCategory.value
  })
}

// 加载物料大类下拉
async function loadMajorCategories() {
  try {
    let res
    if (props.companyCodes && props.companyCodes.length === 1) {
      res = await getMajorCategoryOptions(props.companyCodes[0])
    } else {
      res = await getMajorCategoryOptions()
    }
    majorCategoryOptions.value = res || []
  } catch (e) {
    console.error('加载物料大类选项失败:', e)
    majorCategoryOptions.value = []
  }
}

onMounted(() => {
  loadMajorCategories()
})

// 暴露给父组件的 reset 方法（如有需要）
defineExpose({ loadMajorCategories })
</script>
