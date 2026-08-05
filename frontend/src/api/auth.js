import request from './request'

// 登录
export function login(username, password) {
  return request.post('/auth/login', { username, password })
}

// 获取当前用户信息
export function getMe() {
  return request.get('/auth/me')
}

// 修改密码
export function changePassword(oldPassword, newPassword) {
  return request.post('/auth/change-password', {
    old_password: oldPassword,
    new_password: newPassword,
  })
}
