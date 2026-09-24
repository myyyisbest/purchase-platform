import request from './request'

export function listAnomalyAlerts(params = {}) {
  return request.get('/anomaly-alerts/list', { params })
}

export function getAnomalyAlertSummary(params = {}) {
  return request.get('/anomaly-alerts/summary', { params })
}

export function scanAnomalyAlerts({ fiscalYear, companyCodes, volatilityThreshold = 20, forceRescan = false } = {}) {
  const params = {
    fiscal_year: fiscalYear,
    volatility_threshold: volatilityThreshold,
    force_rescan: forceRescan,
  }
  if (companyCodes && companyCodes.length) params.company_codes = companyCodes
  return request.post('/anomaly-alerts/scan', null, { params })
}

export function acknowledgeAnomalyAlert(id) {
  return request.post(`/anomaly-alerts/${id}/acknowledge`)
}

export function resolveAnomalyAlert(id) {
  return request.post(`/anomaly-alerts/${id}/resolve`)
}
