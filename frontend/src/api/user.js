import request from './request'

// 获取用户列表
export function getUsers() {
  return request.get('/users/')
}

// 创建用户
export function createUser(data) {
  return request.post('/users/', data)
}

// CSV 批量导入用户
export function importUsers(file) {
  const formData = new FormData()
  formData.append('file', file)
  return request.post('/users/import', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

// 编辑用户
export function updateUser(userId, data) {
  return request.put(`/users/${userId}`, data)
}

// 删除用户
export function deleteUser(userId) {
  return request.delete(`/users/${userId}`)
}

// 重置密码
export function resetPassword(userId) {
  return request.post(`/users/${userId}/reset-password`)
}

// 更新用户公司授权
export function updateUserAccess(userId, companyCodes) {
  return request.put(`/users/${userId}/access`, { company_codes: companyCodes })
}
