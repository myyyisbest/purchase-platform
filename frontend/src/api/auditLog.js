import request from './request'

export function listAuditLogs(params = {}) {
  return request.get('/audit-logs', { params })
}
