import request from './request'

// 构建通用过滤参数
function buildFilterParams({
  fiscalYear,
  companyName,
  companyCodes,
  materialCode,
  materialKeyword,
  majorCategory
}) {
  const params = {}
  if (fiscalYear) params.fiscal_year = fiscalYear
  if (companyName) params.company_name = companyName
  if (companyCodes && companyCodes.length > 0) params.company_codes = companyCodes
  if (materialCode) params.material_code = materialCode
  if (materialKeyword) params.material_keyword = materialKeyword
  if (majorCategory) params.major_category = majorCategory
  return params
}

// Dashboard 数据 API - 通用全量
export function getDashboardFull(filters = {}) {
  return request.get('/dashboard/full', { params: buildFilterParams(filters) })
}

// KPI
export function getKpis(filters = {}) {
  return request.get('/dashboard/kpis', { params: buildFilterParams(filters) })
}

// 月度趋势
export function getMonthlyTrend(filters = {}) {
  return request.get('/dashboard/monthly-trend', { params: buildFilterParams(filters) })
}

// 季度分布
export function getQuarterly(filters = {}) {
  return request.get('/dashboard/quarterly', { params: buildFilterParams(filters) })
}

// 公司对比
export function getCompanyComparison(filters = {}) {
  return request.get('/dashboard/company-comparison', { params: buildFilterParams(filters) })
}

// 供应商 TOP
export function getTopSuppliers(filters = {}, limit = 20) {
  return request.get('/dashboard/top-suppliers', { params: { ...buildFilterParams(filters), limit } })
}

// 物料 TOP
export function getTopMaterials(filters = {}, limit = 20) {
  return request.get('/dashboard/top-materials', { params: { ...buildFilterParams(filters), limit } })
}

// 物料类别分布
export function getCategoryDistribution(filters = {}) {
  return request.get('/dashboard/category-distribution', { params: buildFilterParams(filters) })
}

// 物料大类分布
export function getMajorCategoryDistribution(filters = {}) {
  return request.get('/dashboard/major-category-distribution', { params: buildFilterParams(filters) })
}

// 采购用途分布
export function getPurposeDistribution(filters = {}) {
  return request.get('/dashboard/purpose-distribution', { params: buildFilterParams(filters) })
}

// 单价波动
export function getPriceVolatility(filters = {}, limit = 30) {
  return request.get('/dashboard/price-volatility', { params: { ...buildFilterParams(filters), limit } })
}

// 板块分布（按事业部ID）
export function getSectorDistributionByUnit(unitId, filters = {}) {
  return request.get(`/dashboard/sector-distribution/${unitId}`, { params: buildFilterParams(filters) })
}

// 公司月度矩阵
export function getCompanyMonthMatrix(filters = {}) {
  return request.get('/dashboard/company-month-matrix', { params: buildFilterParams(filters) })
}

// 物料搜索（从采购记录中搜索，用于筛选器自动补全）
export function searchMaterialsFromRecords(keyword, limit = 20, companyCodes) {
  const params = { keyword, limit }
  if (companyCodes && companyCodes.length > 0) params.company_codes = companyCodes
  return request.get('/dashboard/search-materials', { params })
}

// ========== 下钻查询 ==========

// 供应商下钻：查看该供应商的前10大物料
export function getSupplierDrill(supplierName, filters = {}) {
  const params = buildFilterParams(filters)
  params.supplier_name = supplierName
  return request.get('/dashboard/supplier-drill', { params })
}

// 物料下钻：查看该物料的前10大供应商
export function getMaterialDrill(materialCode, filters = {}) {
  const params = buildFilterParams(filters)
  params.material_code = materialCode
  return request.get('/dashboard/material-drill', { params })
}

// ========== 供应商深度分析 ==========

// 单源供应风险清单
export function getSingleSourceRisk(filters = {}, limit = 50) {
  const params = buildFilterParams(filters)
  params.limit = limit
  return request.get('/dashboard/single-source-risk', { params })
}

// 单源供应风险清单 - Excel导出
export function exportSingleSourceRiskExcel(filters = {}, limit = 200) {
  const params = buildFilterParams(filters)
  params.limit = limit
  return request.get('/dashboard/single-source-risk/export', {
    params,
    responseType: 'blob'
  })
}

// 供应商比价分析
export function getSupplierPriceComparison(materialCode, filters = {}) {
  const params = buildFilterParams(filters)
  params.material_code = materialCode
  return request.get('/dashboard/supplier-price-comparison', { params })
}
