import request from './request'

/** 分页查询采购记录明细 */
export function listPurchaseRecords(params) {
  return request.get('/purchase-records/list', { params })
}

/** 导出采购记录明细 Excel */
export function exportPurchaseRecords(params) {
  return request.get('/purchase-records/export', { params, responseType: 'blob' })
}
