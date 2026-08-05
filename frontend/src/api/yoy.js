import request from './request'

// 获取可用年份
export function getYears() {
  return request.get('/yoy/years')
}

// 获取可用公司列表
export function getCompanies(year, companyCodes) {
  const params = { year }
  if (companyCodes && companyCodes.length > 0) params.company_codes = companyCodes
  return request.get('/yoy/companies', { params })
}

// 获取可用物料列表
export function getMaterials(year, companyName, extra = {}) {
  return request.get('/yoy/materials', { params: { year, company_name: companyName, ...extra } })
}

// 执行同期对比分析
export function analyze(params) {
  return request.get('/yoy/analyze', { params })
}

// 导出分析结果
export function exportAnalysis(params) {
  return request.get('/yoy/export', { params, responseType: 'blob' })
}