import request from './request'

// ========== 物料大类维护 API ==========

// 分页查询
export function listMaterialMajorCategories(params) {
  return request.get('/material-major-categories', { params })
}

// 模糊搜索（用于下拉/自动补全）
export function searchMaterialMajorCategories(keyword, limit = 20) {
  return request.get('/material-major-categories', {
    params: { keyword, page: 1, page_size: limit }
  })
}

// 获取所有物料大类下拉
export function getMajorCategoryOptions(companyCode) {
  const params = companyCode ? { company_code: companyCode } : {}
  return request.get('/material-major-categories/options', { params })
}

// 获取详情
export function getMaterialMajorCategory(id) {
  return request.get(`/material-major-categories/${id}`)
}

// 新增
export function createMaterialMajorCategory(data) {
  return request.post('/material-major-categories', data)
}

// 更新
export function updateMaterialMajorCategory(id, data) {
  return request.put(`/material-major-categories/${id}`, data)
}

// 删除
export function deleteMaterialMajorCategory(id) {
  return request.delete(`/material-major-categories/${id}`)
}
