#!/bin/bash
# reality-failover build: pool-latency + split-sql + pool-file (2026-04-08)
# =============================================================================
# REALITY SNI picker for 3x-ui (SQLite)
#
# Пул SNI: если читается CANDIDATES_FILE (по умолчанию
# /usr/local/share/reality-failover/sni-candidates.txt), хосты берутся оттуда
# (как в data/sni-candidates.txt в репо). Иначе — встроенный короткий список.
#
# Логика каждого прогона:
#   - Замер «задержки» до каждого хоста из пула CANDIDATES (TLS 1.3 + время curl)
#   - Выбор хоста с минимальным временем среди ответивших
#   - Если он отличается от текущего target/dest в БД — обновить JSON и restart x-ui
#   - Если тот же — только лог, без рестарта
#
# Режимы:
#   once | (пусто)  — один прогон
#   watch           — цикл раз в WATCH_INTERVAL_SEC (по умолчанию 1800 = 30 мин)
#
# Клиенты: после смены SNI обнови subscription / sni= в vless.
#
# Install:
#   sudo apt install -y jq curl sqlite3 util-linux
#   sudo curl -fSL -o /usr/local/bin/reality-failover.sh \
#     'https://raw.githubusercontent.com/fsbtactic-code/vpnbanana/main/scripts/reality-failover.sh'
#   sudo chmod +x /usr/local/bin/reality-failover.sh
#   sudo mkdir -p /usr/local/share/reality-failover
#   sudo curl -fSL -o /usr/local/share/reality-failover/sni-candidates.txt \
#     'https://raw.githubusercontent.com/fsbtactic-code/vpnbanana/main/data/sni-candidates.txt'
#
# Cron каждые 30 минут:
#   */30 * * * * root /usr/local/bin/reality-failover.sh once >> /var/log/reality-failover.log 2>&1
#
# Systemd:
#   sudo systemctl daemon-reload && sudo systemctl restart reality-watcher
#
# Env: XUI_DB, CANDIDATES_FILE, TIMEOUT_CONNECT, TIMEOUT_TOTAL, WATCH_INTERVAL_SEC (default 1800)
# =============================================================================

set -euo pipefail

XUI_DB="${XUI_DB:-/etc/x-ui/x-ui.db}"
LOCK="/run/reality-failover.lock"
LOG_TAG="[reality-failover]"
TIMEOUT_CONNECT="${TIMEOUT_CONNECT:-3}"
TIMEOUT_TOTAL="${TIMEOUT_TOTAL:-6}"
# 30 минут между полными замерами пула
WATCH_INTERVAL_SEC="${WATCH_INTERVAL_SEC:-1800}"

CANDIDATES_FILE="${CANDIDATES_FILE:-/usr/local/share/reality-failover/sni-candidates.txt}"

fill_candidates_from_file() {
  local f="$1"
  CANDIDATES=()
  local -A seen=()
  local line h
  local -a lines=()
  mapfile -t lines < "$f" || true
  for line in "${lines[@]}"; do
    line="${line%%#*}"
    line="$(echo "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    [[ -z "$line" || "$line" == \#* ]] && continue
    h="${line%%/*}"
    h="$(echo "$h" | tr '[:upper:]' '[:lower:]')"
    h="${h//$'\r'/}"
    [[ -z "$h" ]] && continue
    [[ -n "${seen[$h]:-}" ]] && continue
    seen[$h]=1
    CANDIDATES+=("$h")
  done
}

CANDIDATES=()
if [[ -r "$CANDIDATES_FILE" ]]; then
  fill_candidates_from_file "$CANDIDATES_FILE"
fi
if [[ ${#CANDIDATES[@]} -eq 0 ]]; then
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
fi

log() { echo "$(date -Iseconds) $LOG_TAG $*"; }

# «Пинг» в сторону HTTPS: полное время запроса (секунды, float)
probe_ms() {
  curl -so /dev/null \
    --connect-timeout "$TIMEOUT_CONNECT" \
    --max-time "$TIMEOUT_TOTAL" \
    --tlsv1.3 \
    -w "%{time_total}" \
    "https://$1/" 2>/dev/null || return 1
}

host_lc() { echo "$1" | tr '[:upper:]' '[:lower:]'; }

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

  local INBOUND_ID STREAM_JSON current_dest current_host best_host best_ms NEW_JSON TMPJSON
  local cur_lc best_lc h ms summary

  INBOUND_ID=$(sqlite3 "$XUI_DB" "SELECT id FROM inbounds WHERE enable = 1 AND port = 443 AND protocol = 'vless' LIMIT 1;" | tr -d '\r\n' || true)
  if [ -z "$INBOUND_ID" ]; then
    log "no enabled vless inbound on 443 — create in panel"
    return 0
  fi
  if ! [[ "$INBOUND_ID" =~ ^[0-9]+$ ]]; then
    log "invalid inbound id: $INBOUND_ID"
    return 0
  fi

  STREAM_JSON=$(sqlite3 "$XUI_DB" "SELECT stream_settings FROM inbounds WHERE id = ${INBOUND_ID};" || true)
  if [ -z "$STREAM_JSON" ]; then
    log "empty stream_settings for id=$INBOUND_ID"
    return 0
  fi

  current_dest=$(echo "$STREAM_JSON" | jq -r '.realitySettings.target // .realitySettings.dest // empty' 2>/dev/null || true)
  current_host="${current_dest%%:*}"

  if [ -z "$current_host" ] || [ "$current_host" = "null" ]; then
    current_host="${CANDIDATES[0]}"
    log "no target/dest in DB, compare against pool using placeholder current=$current_host"
  fi

  summary=""
  best_host=""
  best_ms=""
  for h in "${CANDIDATES[@]}"; do
    ms=$(probe_ms "$h" 2>/dev/null) || ms=""
    if [ -n "$ms" ]; then
      summary="${summary}${summary:+ }${h}=${ms}s"
      if [ -z "$best_host" ]; then
        best_host=$h
        best_ms=$ms
      elif awk -v a="$ms" -v b="$best_ms" 'BEGIN { exit !(a+0 < b+0) }'; then
        best_host=$h
        best_ms=$ms
      fi
    else
      summary="${summary}${summary:+ }${h}=FAIL"
    fi
  done
  log "pool probe: $summary"

  if [ -z "$best_host" ]; then
    log "ERROR: no host in pool responded — config unchanged"
    return 0
  fi

  cur_lc=$(host_lc "$current_host")
  best_lc=$(host_lc "$best_host")

  if [ "$cur_lc" = "$best_lc" ]; then
    log "KEEP current=$current_host (fastest in pool, ${best_ms}s)"
    return 0
  fi

  log "SWITCH $current_host -> $best_host (best latency ${best_ms}s in pool)"

  NEW_JSON=$(echo "$STREAM_JSON" | jq -c --arg h "$best_host" '
    .realitySettings.target = ($h + ":443")
    | .realitySettings.dest = ($h + ":443")
    | .realitySettings.serverNames = [$h]
  ')

  TMPJSON=$(mktemp)
  trap 'rm -f "$TMPJSON"' RETURN
  printf '%s' "$NEW_JSON" > "$TMPJSON"
  sqlite3 "$XUI_DB" "UPDATE inbounds SET stream_settings = readfile('$TMPJSON') WHERE id = ${INBOUND_ID};"
  systemctl restart x-ui
  log "UPDATED id=$INBOUND_ID target/dest=${best_host}:443 — x-ui restarted (refresh subscription / sni)"
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
    log "watcher start, interval=${WATCH_INTERVAL_SEC}s (default 1800 = 30 min)"
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
    echo "  once  — single run: pick fastest SNI in pool, update if changed" >&2
    echo "  watch — repeat every WATCH_INTERVAL_SEC (default 1800)" >&2
    exit 1
    ;;
esac
