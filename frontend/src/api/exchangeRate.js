import request from './request'

// 获取币种列表（已维护的汇率币种）
export function getCurrencies() {
  return request.get('/exchange-rates/currencies')
}

// 获取采购订单中实际使用的币种列表
export function getOrderCurrencies() {
  return request.get('/exchange-rates/order-currencies')
}

// 获取汇率列表（分页 + 筛选）
export function getExchangeRates(params) {
  return request.get('/exchange-rates', { params })
}

// 获取汇率详情
export function getExchangeRate(id) {
  return request.get(`/exchange-rates/${id}`)
}

// 创建汇率
export function createExchangeRate(data) {
  return request.post('/exchange-rates', data)
}

// 更新汇率
export function updateExchangeRate(id, data) {
  return request.put(`/exchange-rates/${id}`, data)
}

// 删除汇率
export function deleteExchangeRate(id) {
  return request.delete(`/exchange-rates/${id}`)
}
