#!/bin/bash
# =========================================
# 每日月度增量同步脚本
# 由 cron 每日凌晨 2:00 触发
# 调用后端 API /api/hana-sync/sync/monthly
# 同步当月 + 上月 HANA 采购数据，覆盖更新 origin 与 purchase_records
#
# 修复记录（2026-07-27）：
#   - 修正后端端口：41800 → 8081（41800 上无服务监听）
#   - 修正 API 路径：/api/hana-sync/monthly → /api/hana-sync/sync/monthly
#     （FastAPI 路由实际为 prefix=/api/hana-sync + @router.post("/sync/monthly")）
#   - 增加同步前健康检查，端口/路由错时立即告警
#   - 增加 HTTP 超时（max-time），避免 curl 永远挂住导致 cron 卡死
#   - 失败时退出码非 0，便于外部监控
# =========================================
set -euo pipefail

# ── 配置 ──
BACKEND_HOST="127.0.0.1"
BACKEND_PORT="8081"
API_BASE="http://${BACKEND_HOST}:${BACKEND_PORT}"
SYNC_URL="${API_BASE}/api/hana-sync/sync/monthly"
HEALTH_URL="${API_BASE}/api/hana-sync/status"

# 日志目录：可通过环境变量覆盖，默认为脚本同级目录下的 logs
LOG_DIR="${SYNC_LOG_DIR:-$(dirname "$0")/../logs}"
LOG_FILE="${LOG_DIR}/daily_monthly_sync_$(date +%Y%m%d).log"
RESP_FILE="/tmp/monthly_sync_resp_$$.json"

# 同步超时：月度同步涉及当月+上月，最长 10 分钟
CURL_TIMEOUT=600
# 健康检查超时
HEALTH_TIMEOUT=5

mkdir -p "$LOG_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"
}

log "========== 月度定时同步开始 =========="
log "目标: ${SYNC_URL}"

# ── 1. 同步前健康检查：避免端口/路由错配时白跑 ──
health_http=$(curl -s -o /dev/null -w "%{http_code}" -m "$HEALTH_TIMEOUT" "$HEALTH_URL" 2>/dev/null || echo "000")
if [ "$health_http" != "200" ]; then
    log "ERROR 健康检查失败 HTTP=${health_http} (${HEALTH_URL})"
    log "可能原因: 后端未运行 / 端口变更 / 路由变更"
    log "========== 月度定时同步异常终止 =========="
    exit 1
fi
log "健康检查通过 (HTTP ${health_http})"

# ── 2. 触发月度同步 ──
sync_start=$(date +%s)
http_code=$(curl -s -o "$RESP_FILE" -w "%{http_code}" \
    -m "$CURL_TIMEOUT" \
    -X POST "$SYNC_URL" 2>> "$LOG_FILE" || echo "000")
sync_elapsed=$(( $(date +%s) - sync_start ))
resp_body=$(cat "$RESP_FILE" 2>/dev/null || echo "(无响应体)")

log "HTTP: ${http_code}, 耗时 ${sync_elapsed}s"
log "Response: ${resp_body}"

# ── 3. 结果判定 ──
if [ "$http_code" = "200" ]; then
    log "状态: 成功"
    rm -f "$RESP_FILE"
    log "========== 月度定时同步结束 =========="
    echo ""
    exit 0
else
    log "ERROR 状态: 失败 (HTTP ${http_code})"
    log "========== 月度定时同步异常结束 =========="
    echo ""
    exit 2
fi
