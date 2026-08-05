import request from './request'

// 获取物料滚动13个月单价趋势
export function getMaterialTrend(materialCode, months = 13, extra = {}) {
  return request.get(`/price-trend/trend/${materialCode}`, { params: { months, ...extra } })
}

// 获取TOP N物料编码列表
export function getTopMaterials(limit = 20, extra = {}) {
  return request.get('/price-trend/top', { params: { limit, ...extra } })
}

// 批量获取TOP N物料的单价趋势（一次请求拿全部）
export function getTopMaterialTrends(limit = 20, months = 13, extra = {}) {
  return request.get('/price-trend/top/trends', { params: { limit, months, ...extra } })
}

// 搜索物料（编码或名称模糊匹配）
export function searchMaterials(keyword, limit = 20, extra = {}) {
  return request.get('/price-trend/search', { params: { keyword, limit, ...extra } })
}
