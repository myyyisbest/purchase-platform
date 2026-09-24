import request from './request'

export function getHanaStatus() {
  return request.get('/hana-sync/status')
}

export function getHanaState() {
  return request.get('/hana-sync/state')
}

export function triggerHanaSync(mode = 'full') {
  return request.post('/hana-sync/sync', null, {
    params: { mode },
    timeout: 600000,
  })
}

export function triggerMonthlySync() {
  return request.post('/hana-sync/sync/monthly', null, { timeout: 600000 })
}
