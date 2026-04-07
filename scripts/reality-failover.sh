#!/bin/bash
# =============================================================================
# REALITY SNI / dest failover for 3x-ui (SQLite)
#
# Modes:
#   (no args) | once   — один прогон (удобно для cron)
#   watch              — постоянный «слушатель»: раз в WATCH_INTERVAL_SEC секунд
#
# Logic (each run):
#   - If current reality host answers (TLS 1.3 HTTPS) -> OK
#   - Else pick fastest host from CANDIDATES that answers
#   - Update stream_settings, restart x-ui
#
# Clients: после смены SNI обнови subscription или vless (sni=).
#
# Install:
#   sudo apt install -y jq curl sqlite3 util-linux
#   sudo install -m 755 reality-failover.sh /usr/local/bin/reality-failover.sh
#
# Cron (раз в 10 мин):
#   */10 * * * * root /usr/local/bin/reality-failover.sh once >> /var/log/reality-failover.log 2>&1
#
# Systemd watcher (рекомендуется вместо cron):
#   sudo install -m 644 reality-watcher.service /etc/systemd/system/reality-watcher.service
#   sudo systemctl daemon-reload
#   sudo systemctl enable --now reality-watcher
#
# Env: XUI_DB, TIMEOUT_CONNECT, TIMEOUT_TOTAL, WATCH_INTERVAL_SEC (default 60)
# =============================================================================

set -euo pipefail

XUI_DB="${XUI_DB:-/etc/x-ui/x-ui.db}"
LOCK="/run/reality-failover.lock"
LOG_TAG="[reality-failover]"
TIMEOUT_CONNECT="${TIMEOUT_CONNECT:-3}"
TIMEOUT_TOTAL="${TIMEOUT_TOTAL:-6}"
WATCH_INTERVAL_SEC="${WATCH_INTERVAL_SEC:-60}"

CANDIDATES=(
  nalog.ru
  sovcombank.ru
  tinkoff.ru
  sberbank.ru
  mos.ru
  rt.ru
  yandex.ru
  vk.com
  aeroflot.ru
  mts.ru
)

log() { echo "$(date -Iseconds) $LOG_TAG $*"; }

probe_ms() {
  curl -so /dev/null \
    --connect-timeout "$TIMEOUT_CONNECT" \
    --max-time "$TIMEOUT_TOTAL" \
    --tlsv1.3 \
    -w "%{time_total}" \
    "https://$1/" 2>/dev/null || return 1
}

is_up() {
  probe_ms "$1" >/dev/null 2>&1
}

# One check cycle. Returns 0 always unless fatal misconfig (missing deps).
run_once() {
  for bin in jq curl sqlite3; do
    if ! command -v "$bin" >/dev/null; then
      log "missing $bin — apt install -y jq curl sqlite3"
      return 1
    fi
  done

  if [ ! -r "$XUI_DB" ]; then
    log "DB not readable: $XUI_DB"
    return 1
  fi

  local ROW INBOUND_ID STREAM_JSON current_dest current_host best_host best_ms ms NEW_JSON TMPJSON

  ROW=$(sqlite3 "$XUI_DB" "SELECT id, stream_settings FROM inbounds WHERE enable = 1 AND port = 443 AND protocol = 'vless' LIMIT 1;" || true)
  if [ -z "$ROW" ]; then
    log "no enabled vless inbound on 443 — create in panel"
    return 0
  fi

  INBOUND_ID=$(echo "$ROW" | cut -d'|' -f1)
  STREAM_JSON=$(echo "$ROW" | cut -d'|' -f2-)

  if [ -z "$INBOUND_ID" ] || [ -z "$STREAM_JSON" ]; then
    log "failed to read inbound"
    return 0
  fi

  current_dest=$(echo "$STREAM_JSON" | jq -r '.realitySettings.dest // empty' 2>/dev/null || true)
  current_host="${current_dest%%:*}"

  if [ -z "$current_host" ] || [ "$current_host" = "null" ]; then
    current_host="${CANDIDATES[0]}"
    log "no dest in DB, treat current as $current_host"
  fi

  if is_up "$current_host"; then
    log "OK current=$current_host"
    return 0
  fi

  log "DOWN current=$current_host — probing candidates..."

  best_host=""
  best_ms=""
  for h in "${CANDIDATES[@]}"; do
    ms=$(probe_ms "$h" 2>/dev/null) || continue
    if [ -z "$best_host" ]; then
      best_host=$h
      best_ms=$ms
      continue
    fi
    if awk -v a="$ms" -v b="$best_ms" 'BEGIN { exit !(a+0 < b+0) }'; then
      best_host=$h
      best_ms=$ms
    fi
  done

  if [ -z "$best_host" ]; then
    log "ERROR: no candidate responded — config unchanged"
    return 0
  fi

  log "PICK best=$best_host time=${best_ms}s"

  NEW_JSON=$(echo "$STREAM_JSON" | jq -c --arg h "$best_host" '
    .realitySettings.dest = ($h + ":443")
    | .realitySettings.serverNames = [$h]
  ')

  TMPJSON=$(mktemp)
  trap 'rm -f "$TMPJSON"' RETURN
  printf '%s' "$NEW_JSON" > "$TMPJSON"
  sqlite3 "$XUI_DB" "UPDATE inbounds SET stream_settings = readfile('$TMPJSON') WHERE id = ${INBOUND_ID};"
  systemctl restart x-ui
  log "UPDATED id=$INBOUND_ID dest=${best_host}:443 — x-ui restarted (refresh subscription / sni)"
  return 0
}

run_once_locked() {
  (
    flock -n 200 || { log "locked, skip this tick"; exit 0; }
    run_once
  ) 200>"$LOCK"
}

MODE="${1:-once}"
case "$MODE" in
  watch)
    log "watcher start, interval=${WATCH_INTERVAL_SEC}s"
    while true; do
      run_once_locked || true
      sleep "$WATCH_INTERVAL_SEC"
    done
    ;;
  once|run|"")
    run_once_locked
    ;;
  *)
    echo "Usage: $0 [once|watch]" >&2
    echo "  once  — single check (default)" >&2
    echo "  watch — loop every WATCH_INTERVAL_SEC (default 60)" >&2
    exit 1
    ;;
esac
