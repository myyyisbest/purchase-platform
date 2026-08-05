import request from './request'

// 组织架构完整层级（用于全局筛选器）
export function getOrgHierarchy() {
  return request.get('/org/hierarchy')
}

// 组织架构树
export function getOrgTree() {
  return request.get('/org/tree')
}

// ========== 集团 ==========
export function getGroups() {
  return request.get('/org/groups')
}

export function createGroup(data) {
  return request.post('/org/groups', data)
}

export function updateGroup(id, data) {
  return request.put(`/org/groups/${id}`, data)
}

export function deleteGroup(id) {
  return request.delete(`/org/groups/${id}`)
}

// ========== 事业部 ==========
export function getUnits(groupId) {
  const params = groupId ? { group_id: groupId } : {}
  return request.get('/org/units', { params })
}

export function createUnit(data) {
  return request.post('/org/units', data)
}

export function updateUnit(id, data) {
  return request.put(`/org/units/${id}`, data)
}

export function deleteUnit(id) {
  return request.delete(`/org/units/${id}`)
}

// ========== 板块 ==========
export function getSectors(unitId) {
  const params = unitId ? { unit_id: unitId } : {}
  return request.get('/org/sectors', { params })
}

export function createSector(data) {
  return request.post('/org/sectors', data)
}

export function updateSector(id, data) {
  return request.put(`/org/sectors/${id}`, data)
}

export function deleteSector(id) {
  return request.delete(`/org/sectors/${id}`)
}

// ========== 公司 ==========
export function getCompanies(sectorId) {
  const params = sectorId ? { sector_id: sectorId } : {}
  return request.get('/org/companies', { params })
}

export function getCompany(id) {
  return request.get(`/org/companies/${id}`)
}

export function createCompany(data) {
  return request.post('/org/companies', data)
}

export function updateCompany(id, data) {
  return request.put(`/org/companies/${id}`, data)
}

export function deleteCompany(id) {
  return request.delete(`/org/companies/${id}`)
}
