/**
 * 格式化工具函数
 */

// 去除物料编码前导零（000000000010059105 → 10059105）
export function stripLeadingZeros(code) {
  if (code == null) return ''
  return String(code).replace(/^0+/, '') || '0'
}

// 金额格式化
export function formatMoney(v) {
  if (v === null || v === undefined) return '0'
  if (Math.abs(v) >= 1e8) return (v / 1e8).toFixed(2) + ' 亿'
  if (Math.abs(v) >= 1e4) return (v / 1e4).toFixed(2) + ' 万'
  return Number(v).toFixed(2)
}

// 数字格式化
export function formatNum(v) {
  if (v === null || v === undefined) return '0'
  return Number(v).toLocaleString('zh-CN', { maximumFractionDigits: 4 })
}
