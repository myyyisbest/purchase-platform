<template>
  <!-- 组织占比下钻图：集团/事业部/板块/公司 四级下钻，受限用户自动定位起点 -->
  <div class="org-drill-chart">
    <!-- 头部：标题 + 副标题 + 重置 -->
    <div class="chart-header">
      <div class="header-left">
        <h3>占比（事业部 → 板块 → 公司）</h3>
        <span class="sub">{{ currentSub }}</span>
      </div>
      <el-tooltip content="重置到起点" placement="top" v-if="drillStack.length > 1">
        <el-button size="small" text @click="resetToStart">
          <el-icon><Refresh /></el-icon>
        </el-button>
      </el-tooltip>
    </div>

    <!-- 面包屑：层级链 -->
    <div class="breadcrumb-row" v-if="drillStack.length > 0">
      <el-breadcrumb separator="/">
        <el-breadcrumb-item v-for="(item, idx) in drillStack" :key="idx">
          <a
            v-if="idx < drillStack.length - 1"
            class="crumb-link"
            @click="goToLevel(idx)"
          >{{ item.name }}</a>
          <span v-else class="crumb-current">{{ item.name }}</span>
        </el-breadcrumb-item>
      </el-breadcrumb>
    </div>

    <!-- 加载中 -->
    <div v-if="loading" class="state-block">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>加载中...</span>
    </div>

    <!-- 无数据 -->
    <div v-else-if="!hasData" class="state-block">
      <el-empty description="当前权限范围内暂无采购数据" :image-size="80" />
    </div>

    <!-- 单公司模式：受限用户只能看 1 家公司时降级为物料大类占比 -->
    <div v-else-if="singleCompanyMode" class="single-company-mode">
      <div class="single-hint">
        <el-icon><InfoFilled /></el-icon>
        <span>当前权限仅覆盖 1 家公司（{{ singleCompanyName }}），已切换为「物料大类占比」视图</span>
      </div>
      <v-chart
        :option="singleCompanyChartOption"
        autoresize
        style="height: 360px"
      />
    </div>

    <!-- 多层级下钻饼图 -->
    <v-chart
      v-else
      :option="drillChartOption"
      autoresize
      style="height: 380px"
      @click="handleChartClick"
    />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart, BarChart } from 'echarts/charts'
import {
  TitleComponent, TooltipComponent, LegendComponent, GridComponent
} from 'echarts/components'
import VChart from 'vue-echarts'
import {
  Refresh, Loading, InfoFilled
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import {
  getDashboardFull, getSectorDistributionByUnit,
  getCompanyComparison, getMajorCategoryDistribution
} from '../api/dashboard'

use([CanvasRenderer, PieChart, BarChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent])

const props = defineProps({
  // Dashboard 顶部 OrgFilter 同步过来的过滤条件
  filters: { type: Object, default: () => ({}) },
  // 组织架构完整层级（getOrgHierarchy 的结果）
  orgHierarchy: { type: Array, default: () => [] },
  // 当前用户权限公司码（admin 为空数组 = 全部权限）
  userCompanyCodes: { type: Array, default: () => [] }
})

// ============ 状态 ============

const loading = ref(false)
// 下钻栈：[{ level, id, name, companyCodes }]
// level: 'group' | 'unit' | 'sector' | 'company'
// 第 0 项为起点，最后一项为当前所在层
const drillStack = ref([])
// 当前层级聚合数据 [{ id, name, value, level, companyCodes }]
const chartData = ref([])

// 单公司模式相关
const singleCompanyMode = ref(false)
const singleCompanyName = ref('')
const singleCompanyDist = ref([])

// ============ 性能优化：请求竞态 + 防抖 ============

// 竞态 token：每次发起新请求自增，回调里比对，旧请求结果直接丢弃，防止快速切换时旧数据覆盖新数据
let requestToken = 0

// debounce 工具：合并 OrgFilter 连续 emit 造成的高频重置
function debounce(fn, wait) {
  let timer = null
  return function (...args) {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => { timer = null; fn.apply(this, args) }, wait)
  }
}

// ============ 计算属性 ============

const currentLevel = computed(() => {
  if (singleCompanyMode.value) return 'single'
  const top = drillStack.value[drillStack.value.length - 1]
  return top ? top.level : null
})

const hasData = computed(() => {
  if (singleCompanyMode.value) return singleCompanyDist.value.length > 0
  return chartData.value.length > 0
})

// 当前层级名称 → 子层级名称（用于标题文案）
const LEVEL_NAMES = {
  group: { title: '事业部', child: '事业部' },
  unit: { title: '事业部', child: '板块' },
  sector: { title: '板块', child: '公司' },
  company: { title: '公司', child: null }
}

const currentSub = computed(() => {
  if (singleCompanyMode.value) return '该公司物料大类占比'
  const top = drillStack.value[drillStack.value.length - 1]
  if (!top) return ''
  // 判断当前展示的是哪一层
  const isCompanyLevel = chartData.value.length > 0 && chartData.value[0].level === 'company'
  if (isCompanyLevel) return '公司层（最深），鼠标悬停看明细'
  if (top.level === 'group') return '点击扇区可下钻'
  if (top.level === 'unit') return '点击扇区可下钻'
  if (top.level === 'sector') return '点击扇区可下钻到公司'
  return ''
})

// ============ 核心算法：起点判定 ============

/**
 * 剪枝：保留包含 userCompanyCodes 的节点。
 * admin（userCompanyCodes 为空）直接返回原树。
 */
function pruneHierarchy(hierarchy, codes) {
  if (!codes || codes.length === 0) return hierarchy
  const codeSet = new Set(codes)
  return hierarchy
    .map(g => pruneGroup(g, codeSet))
    .filter(Boolean)
}

function pruneGroup(g, codeSet) {
  const units = (g.units || []).map(u => pruneUnit(u, codeSet)).filter(Boolean)
  if (units.length === 0) return null
  return { ...g, units }
}

function pruneUnit(u, codeSet) {
  const sectors = (u.sectors || []).map(s => pruneSector(s, codeSet)).filter(Boolean)
  if (sectors.length === 0) return null
  return { ...u, sectors }
}

function pruneSector(s, codeSet) {
  const companies = (s.companies || []).filter(c => codeSet.has(c.code))
  if (companies.length === 0) return null
  return { ...s, companies }
}

/**
 * 找最深的多叶子节点：计算所有叶子的最低公共祖先（LCA）。
 * 返回 { mode: 'multi' | 'single' | 'empty', chain: [{level,node}] }
 * - mode='multi': chain 为 LCA 链（公共祖先），起点 = LCA 最末端节点的下一层
 * - mode='single': chain 为单叶子的完整路径，降级为单公司模式
 * - mode='empty': 无任何数据
 */
function findDrillStart(prunedHierarchy) {
  // 收集所有叶子（公司）的完整路径
  const allPaths = []
  prunedHierarchy.forEach(g => collectLeafPaths(g, 'group', [], allPaths))

  if (allPaths.length === 0) return { mode: 'empty', chain: [] }
  if (allPaths.length === 1) return { mode: 'single', chain: allPaths[0] }

  // 多叶子：求最长公共前缀（LCA）
  const minLen = Math.min(...allPaths.map(p => p.length))
  let lcaLen = 0
  for (let i = 0; i < minLen; i++) {
    const ref = allPaths[0][i]
    const allMatch = allPaths.every(
      p => p[i].node.id === ref.node.id && p[i].level === ref.level
    )
    if (allMatch) lcaLen = i + 1
    else break
  }
  return { mode: 'multi', chain: allPaths[0].slice(0, lcaLen) }
}

function collectLeafPaths(node, level, currentPath, allPaths) {
  const newPath = [...currentPath, { level, node }]
  if (level === 'sector') {
    (node.companies || []).forEach(c =>
      allPaths.push([...newPath, { level: 'company', node: c }])
    )
  } else if (level === 'unit') {
    (node.sectors || []).forEach(s => collectLeafPaths(s, 'sector', newPath, allPaths))
  } else if (level === 'group') {
    (node.units || []).forEach(u => collectLeafPaths(u, 'unit', newPath, allPaths))
  }
}

/**
 * 给定剪枝后的子树，收集某 unit/sector/group 下的所有公司码。
 * 用于下钻时传递 companyCodes 给后端。
 */
function collectCompanyCodesUnder(node, level) {
  const codes = []
  if (level === 'group') {
    (node.units || []).forEach(u => collectCompanyCodesUnder(u, 'unit', codes))
  } else if (level === 'unit') {
    (node.sectors || []).forEach(s => collectCompanyCodesUnder(s, 'sector', codes))
  } else if (level === 'sector') {
    (node.companies || []).forEach(c => codes.push(c.code))
  } else if (level === 'company') {
    codes.push(node.code)
  }
  return codes
}

// ============ 数据加载 ============

/**
 * 加载某层的金额分布数据。
 * parentLevel: 当前所在层，决定了要请求"下一层"的什么数据。
 * - group: 请求事业部分布（用 getDashboardFull）
 * - unit: 请求该事业部下的板块分布（getSectorDistributionByUnit）
 * - sector: 请求该板块下的公司分布（getCompanyComparison + 公司码过滤）
 */
async function loadLevelData(parentLevel, parentId, parentCompanyCodes) {
  // 受限用户：把请求范围限定为该父节点的可见公司码（与权限自动交集）
  // admin：parentCompanyCodes 为 undefined，后端不过滤
  const baseFilters = buildBaseFilters()
  const mergedCodes = mergeCompanyCodes(baseFilters.companyCodes, parentCompanyCodes)
  const effectiveFilters = { ...baseFilters, companyCodes: mergedCodes }

  if (parentLevel === 'group') {
    const res = await getDashboardFull(effectiveFilters)
    const unitDist = res.unit_distribution || []
    return unitDist.map(u => ({
      id: u.unit_id,
      name: u.unit_name,
      value: u.amount_cny,
      level: 'unit'
    }))
  }
  if (parentLevel === 'unit') {
    const res = await getSectorDistributionByUnit(parentId, effectiveFilters)
    return (res || []).map(s => ({
      id: s.sector_id,
      name: s.sector_name,
      value: s.amount_cny,
      level: 'sector'
    }))
  }
  if (parentLevel === 'sector') {
    const res = await getCompanyComparison(effectiveFilters)
    return (res || []).map(c => ({
      id: c.company_code,
      name: c.company_name,
      value: c.amount_cny,
      level: 'company'
    }))
  }
  return []
}

function buildBaseFilters() {
  // 复用 Dashboard 顶部 OrgFilter + 财年 + 物料筛选
  const f = props.filters || {}
  return {
    fiscalYear: f.fiscalYear,
    companyName: f.companyName || undefined,
    companyCodes: f.companyCodes && f.companyCodes.length > 0 ? [...f.companyCodes] : undefined,
    materialCode: f.materialCode || undefined,
    materialKeyword: f.materialKeyword || undefined,
    majorCategory: f.majorCategory || undefined
  }
}

// 用户筛选 + 下钻层级公司码取并集（实际上是限制为该层级下）
function mergeCompanyCodes(filterCodes, parentCodes) {
  // 如果父节点公司码为空（admin 起点），保留用户筛选的公司码
  if (!parentCodes || parentCodes.length === 0) return filterCodes
  // 否则用父节点公司码（更窄），后端会自动与权限取交集
  return parentCodes
}

// ============ 入口：初始化 + 起点 ============

async function initStart() {
  if (!props.orgHierarchy || props.orgHierarchy.length === 0) return
  const myToken = ++requestToken  // 标记本次请求，旧请求结果会被丢弃
  loading.value = true
  try {
    const pruned = pruneHierarchy(props.orgHierarchy, props.userCompanyCodes)
    const { mode, chain } = findDrillStart(pruned)

    // 旧请求结果丢弃（用户在此期间又改了筛选条件）
    if (myToken !== requestToken) return

    if (mode === 'empty') {
      drillStack.value = []
      chartData.value = []
      singleCompanyMode.value = false
      return
    }

    if (mode === 'single') {
      // 单公司：降级为物料大类占比
      await enterSingleCompanyMode(chain, myToken)
      return
    }

    // 多叶子：chain 是 LCA，起点 = LCA 最末端节点的子层
    const startChain = chain.length === 0
      ? [{ level: 'group', node: { id: null, name: '全部' } }]
      : chain

    drillStack.value = startChain.map(item => ({
      level: item.level,
      id: item.node.id,
      name: item.node.name || item.node.unit_name || item.node.sector_name || '全部',
      companyCodes: collectCompanyCodesUnder(item.node, item.level)
    }))

    // 加载起点层数据（带单子节点自动下钻）
    await loadAndAutoExpand(myToken)
    singleCompanyMode.value = false
  } catch (e) {
    if (myToken !== requestToken) return
    console.error('初始化下钻起点失败:', e)
    ElMessage.error('加载组织下钻数据失败')
  } finally {
    if (myToken === requestToken) loading.value = false
  }
}

async function enterSingleCompanyMode(chain, parentToken) {
  // chain 最后一项是 company
  const companyNode = chain[chain.length - 1].node
  singleCompanyName.value = companyNode.name
  singleCompanyMode.value = true
  drillStack.value = chain.map(item => ({
    level: item.level,
    id: item.node.id,
    name: item.node.name,
    companyCodes: [companyNode.code]
  }))
  try {
    const filters = {
      ...buildBaseFilters(),
      companyCodes: [companyNode.code]
    }
    const res = await getMajorCategoryDistribution(filters)
    if (parentToken !== requestToken) return  // 旧请求丢弃
    singleCompanyDist.value = res || []
  } catch (e) {
    if (parentToken !== requestToken) return
    console.error('加载单公司物料分布失败:', e)
    singleCompanyDist.value = []
  }
}

// ============ 下钻 / 返回 ============

/**
 * 单子节点自动下钻：加载某层数据后，如果只有 1 个子节点且不是公司层，
 * 自动继续下钻一层，避免出现"100% 单扇区圆环"。
 *
 * 用场景：事业部下只有 1 个板块有采购数据 → 自动跳到公司层展示该公司占比。
 */
async function loadAndAutoExpand(myToken) {
  const top = drillStack.value[drillStack.value.length - 1]
  if (!top) return

  let currentLevel = top.level
  let currentId = top.id
  let currentCodes = top.companyCodes
  let depth = 0
  const MAX_DEPTH = 3  // 防御性兜底，避免异常数据造成死循环

  while (depth <= MAX_DEPTH) {
    const nextData = await loadLevelData(currentLevel, currentId, currentCodes)
    if (myToken !== requestToken) return  // 旧请求丢弃

    // 空数据
    if (!nextData || nextData.length === 0) {
      // depth=0 时表示起点就没数据，清空图表
      if (depth === 0) chartData.value = []
      return
    }

    // 推入当前数据
    chartData.value = nextData

    // 终止条件：已到公司层（最深） 或 多子节点（≥2 项）
    const isCompanyLevel = nextData[0].level === 'company'
    const isMultiNode = nextData.length >= 2
    if (isCompanyLevel || isMultiNode) return

    // 单子节点且非公司层 → 自动继续下钻
    const nextChild = nextData[0]
    drillStack.value.push({
      level: nextChild.level,
      id: nextChild.id,
      name: nextChild.name,
      companyCodes: nextChild.level === 'sector'
        ? computeChildCompanyCodes(nextChild)
        : []
    })
    currentLevel = nextChild.level
    currentId = nextChild.id
    currentCodes = nextChild.level === 'sector'
      ? computeChildCompanyCodes(nextChild)
      : []
    depth++
  }
}

async function handleChartClick(params) {
  const clicked = params.data
  if (!clicked || !clicked.level) return
  // 已到公司层，不再下钻
  if (clicked.level === 'company') {
    ElMessage.info(`${clicked.name} 已是最深层级`)
    return
  }

  const myToken = ++requestToken
  loading.value = true
  try {
    // 先尝试加载下一层数据
    const childCompanyCodes = clicked.level === 'sector'
      ? computeChildCompanyCodes(clicked)
      : []
    const firstData = await loadLevelData(clicked.level, clicked.id, childCompanyCodes)
    if (myToken !== requestToken) return  // 旧请求丢弃

    if (!firstData || firstData.length === 0) {
      ElMessage.info(`${clicked.name} 下暂无采购数据`)
      return
    }

    // 推入下钻栈，进入自动展开流程（处理单子节点自动下钻）
    drillStack.value.push({
      level: clicked.level,
      id: clicked.id,
      name: clicked.name,
      companyCodes: childCompanyCodes
    })
    chartData.value = firstData

    // 单子节点且非公司层 → 继续自动下钻
    const isCompanyLevel = firstData[0].level === 'company'
    if (!isCompanyLevel && firstData.length === 1) {
      // 临时把栈顶的 level/id 更新为子节点，复用 loadAndAutoExpand 的循环
      const child = firstData[0]
      drillStack.value.push({
        level: child.level,
        id: child.id,
        name: child.name,
        companyCodes: child.level === 'sector' ? computeChildCompanyCodes(child) : []
      })
      // 继续展开（depth 从 1 开始，因为已经手动下钻一层了）
      await continueAutoExpand(myToken)
    }
  } catch (e) {
    if (myToken !== requestToken) return
    console.error('下钻失败:', e)
    ElMessage.error('下钻失败')
  } finally {
    if (myToken === requestToken) loading.value = false
  }
}

/**
 * continueAutoExpand：从当前栈顶开始继续单子节点自动下钻。
 * 与 loadAndAutoExpand 的区别：loadAndAutoExpand 先发一次请求，
 * continueAutoExpand 假设首层已经加载完毕，从第二层开始循环。
 */
async function continueAutoExpand(myToken) {
  const top = drillStack.value[drillStack.value.length - 1]
  if (!top) return
  let currentLevel = top.level
  let currentId = top.id
  let currentCodes = top.companyCodes
  let depth = 0
  const MAX_DEPTH = 3

  while (depth <= MAX_DEPTH) {
    // 当前 chartData 已加载，检查是否需要继续下钻
    const cur = chartData.value
    if (!cur || cur.length === 0) return
    const isCompanyLevel = cur[0].level === 'company'
    const isMultiNode = cur.length >= 2
    if (isCompanyLevel || isMultiNode) return

    // 单子节点 → 加载下一层
    const child = cur[0]
    const childCodes = child.level === 'sector' ? computeChildCompanyCodes(child) : []
    const nextData = await loadLevelData(child.level, child.id, childCodes)
    if (myToken !== requestToken) return  // 旧请求丢弃
    if (!nextData || nextData.length === 0) return  // 没下层数据，停在当前

    drillStack.value.push({
      level: child.level,
      id: child.id,
      name: child.name,
      companyCodes: childCodes
    })
    chartData.value = nextData
    currentLevel = child.level
    currentId = child.id
    currentCodes = childCodes
    depth++
  }
}

/**
 * 计算被点击的子节点（来自 chartData）对应的可见公司码。
 * 仅 sector → company 下钻时需要（getCompanyComparison 按 companyCodes 过滤）。
 * unit → sector 不调用此函数（后端用 unit_id 自己算）。
 *
 * 注：用宽松类型匹配（Number/String 互转），防止后端不同接口返回的 id 类型不一致。
 */
function computeChildCompanyCodes(clicked) {
  const pruned = pruneHierarchy(props.orgHierarchy, props.userCompanyCodes)
  const targetId = String(clicked.id)  // 统一转字符串比较

  if (clicked.level === 'unit') {
    for (const g of pruned) {
      const u = (g.units || []).find(x => String(x.id) === targetId)
      if (u) return collectCompanyCodesUnder(u, 'unit')
    }
  }
  if (clicked.level === 'sector') {
    for (const g of pruned) {
      for (const u of (g.units || [])) {
        const s = (u.sectors || []).find(x => String(x.id) === targetId)
        if (s) return collectCompanyCodesUnder(s, 'sector')
      }
    }
    // 数据不一致兜底：hierarchy 找不到该 sector，但 chartData 里有
    // 此时无法计算公司码，返回空让上层提示
  }
  if (clicked.level === 'company') {
    return [clicked.id]  // company 的 id 就是 company_code
  }
  return []
}

// 面包屑跳转：回到指定层级
async function goToLevel(targetIdx) {
  if (targetIdx < 0 || targetIdx >= drillStack.value.length - 1) return
  const myToken = ++requestToken
  // 截断到 targetIdx
  drillStack.value = drillStack.value.slice(0, targetIdx + 1)
  singleCompanyMode.value = false
  loading.value = true
  try {
    await loadAndAutoExpand(myToken)
  } catch (e) {
    if (myToken !== requestToken) return
    console.error('返回失败:', e)
    ElMessage.error('返回失败')
  } finally {
    if (myToken === requestToken) loading.value = false
  }
}

// 重置到起点
async function resetToStart() {
  await initStart()
}

// ============ ECharts 配置 ============

// 当前是否为公司层（最深）→ 决定用饼图还是横向柱状图
const isCompanyLevel = computed(() =>
  chartData.value.length > 0 && chartData.value[0].level === 'company'
)

const drillChartOption = computed(() => {
  // 公司层：公司名通常较长，饼图标签必然挤，改用横向柱状图
  if (isCompanyLevel.value) {
    return buildCompanyBarOption()
  }
  // 事业部/板块层：用环形饼图（扇区数较少，名称适中）
  return buildUnitSectorPieOption()
})

// 事业部/板块层：环形饼图
function buildUnitSectorPieOption() {
  const data = chartData.value.map(d => ({
    name: d.name,
    value: d.value,
    id: d.id,
    level: d.level
  }))
  return {
    tooltip: {
      trigger: 'item',
      formatter: p => {
        const leaf = '<br/><small style="color:#909399">点击下钻</small>'
        return `${p.name}<br/>${formatMoney(p.value)} 元 (${p.percent}%)${leaf}`
      }
    },
    legend: {
      type: 'scroll', orient: 'vertical',
      right: 10, top: 30, bottom: 30,
      textStyle: { fontSize: 12 }
    },
    series: [{
      name: '组织占比',
      type: 'pie',
      radius: ['45%', '72%'],
      center: ['38%', '50%'],
      avoidLabelOverlap: true,
      itemStyle: { borderRadius: 8, borderColor: '#fff', borderWidth: 2 },
      label: {
        show: true,
        formatter: p => (p.percent >= 5 ? `{b|${p.name}}\n{d|${p.percent}%}` : `{d|${p.percent}%}`),
        rich: {
          b: { fontSize: 12, color: '#303133', lineHeight: 16 },
          d: { fontSize: 11, color: '#909399' }
        }
      },
      labelLine: { length: 8, length2: 8, smooth: true },
      labelLayout: { hideOverlap: true },
      data
    }]
  }
}

// 公司层：横向柱状图，公司名做 Y 轴类别（名称不再挤压）
function buildCompanyBarOption() {
  // 按金额升序，最大的显示在最上方
  const sorted = [...chartData.value].sort((a, b) => a.value - b.value)
  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: p => {
        const d = sorted[p[0].dataIndex]
        return `${d.name}<br/>${formatMoney(d.value)} 元`
      }
    },
    // containLabel 自动避让左侧长公司名
    grid: { left: 10, right: 50, top: 20, bottom: 20, containLabel: true },
    xAxis: {
      type: 'value',
      axisLabel: { formatter: v => formatMoney(v) }
    },
    yAxis: {
      type: 'category',
      data: sorted.map(d => d.name),
      axisLabel: { width: 180, overflow: 'truncate', lineHeight: 16, fontSize: 12 }
    },
    series: [{
      name: '公司采购金额',
      type: 'bar',
      data: sorted.map(d => d.value),
      itemStyle: { color: '#5470c6', borderRadius: [0, 4, 4, 0] },
      label: {
        show: true,
        position: 'right',
        formatter: p => formatMoney(p.value),
        fontSize: 11,
        color: '#606266'
      }
    }]
  }
}

const singleCompanyChartOption = computed(() => {
  const data = (singleCompanyDist.value || []).map(c => ({
    name: c.major_category || '未分类',
    value: c.amount_cny
  }))
  return {
    tooltip: {
      trigger: 'item',
      formatter: p => `${p.name}<br/>${formatMoney(p.value)} 元 (${p.percent}%)`
    },
    legend: {
      type: 'scroll', orient: 'vertical',
      right: 10, top: 30, bottom: 30,
      textStyle: { fontSize: 12 }
    },
    series: [{
      name: '物料大类',
      type: 'pie',
      radius: ['45%', '72%'],
      center: ['38%', '50%'],
      avoidLabelOverlap: true,
      itemStyle: { borderRadius: 8, borderColor: '#fff', borderWidth: 2 },
      label: {
        show: true,
        formatter: p => (p.percent >= 5 ? `{b|${p.name}}\n{d|${p.percent}%}` : `{d|${p.percent}%}`),
        rich: {
          b: { fontSize: 12, color: '#303133', lineHeight: 16 },
          d: { fontSize: 11, color: '#909399' }
        }
      },
      labelLine: { length: 8, length2: 8, smooth: true },
      labelLayout: { hideOverlap: true },
      data
    }]
  }
})

// ============ 工具函数 ============

function formatMoney(v) {
  if (v === null || v === undefined) return '0'
  const num = Number(v)
  if (!isFinite(num)) return '0'
  // 大额数字自动单位化
  const abs = Math.abs(num)
  if (abs >= 1e8) return (num / 1e8).toFixed(2) + ' 亿'
  if (abs >= 1e4) return (num / 1e4).toFixed(2) + ' 万'
  return num.toLocaleString('zh-CN')
}

// ============ 生命周期 ============

// filters 变化时防抖重置（OrgFilter 连续 emit 合并为一次请求）
const debouncedReset = debounce(() => resetToStart(), 300)
watch(
  () => JSON.stringify(props.filters),
  () => { debouncedReset() }
)

// 组织层级加载完成后初始化
watch(
  () => props.orgHierarchy,
  (val) => {
    if (val && val.length > 0) resetToStart()
  }
)

onMounted(() => {
  if (props.orgHierarchy && props.orgHierarchy.length > 0) {
    resetToStart()
  }
})

// 组件卸载时丢弃所有挂起请求，避免内存泄漏和回调错乱
onBeforeUnmount(() => {
  requestToken++  // 让所有挂起请求的回调失效
})
</script>

<style scoped>
.org-drill-chart {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-width: 0;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
  padding-bottom: 12px;
  border-bottom: 1px solid #ebeef5;
  flex-wrap: wrap;
}
.chart-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}
.chart-header .sub {
  font-size: 12px;
  color: #909399;
  margin-left: 8px;
}
.header-left {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  min-width: 0;
}

.breadcrumb-row {
  margin-bottom: 12px;
  padding: 4px 0;
}
.crumb-link {
  color: #409eff;
  cursor: pointer;
  text-decoration: none;
}
.crumb-link:hover {
  text-decoration: underline;
}
.crumb-current {
  color: #303133;
  font-weight: 600;
}

.state-block {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 380px;
  color: #909399;
  font-size: 14px;
}

.single-company-mode {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.single-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  background: #ecf5ff;
  border: 1px solid #d9ecff;
  border-radius: 4px;
  color: #409eff;
  font-size: 12px;
  line-height: 1.5;
}
</style>
