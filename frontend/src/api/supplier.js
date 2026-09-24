import request from './request'

export function listSuppliers(params = {}) {
  return request.get('/suppliers', { params })
}

export function getSupplier(id) {
  return request.get(`/suppliers/${id}`)
}

export function createSupplier(data) {
  return request.post('/suppliers', data)
}

export function updateSupplier(id, data) {
  return request.put(`/suppliers/${id}`, data)
}

export function deleteSupplier(id) {
  return request.delete(`/suppliers/${id}`)
}

export function syncSuppliersFromRecords() {
  return request.post('/suppliers/sync-from-records')
}
