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
#   - Замер «задержки» до каждого хоста из пула CANDIDATES (TLS 1.3 + время curl), по умолчанию параллельно (PROBE_PARALLEL)
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
# Env: XUI_DB, CANDIDATES_FILE, ROTATION_POOL, WIDE_POOL, TIMEOUT_CONNECT, TIMEOUT_TOTAL,
#      WATCH_INTERVAL_SEC (default 1800),
#      SUB_UPDATES_HOURS (после смены SNI: интервал в заголовке Profile-Update-Interval, часы),
#      BUMP_SUB_ANNOUNCE (1/0 — обновить Announce в БД 3x-ui, чтобы клиенты заметили смену подписки)
#      PROBE_PARALLEL (одновременных curl; по умолчанию 30; 1 = по одному как раньше)
#      POOL_PROBE_FULL=1 — в лог весь pool probe (host=time); иначе краткая сводка + sample
#      BUMP_SUB_ON_KEEP=1 — при KEEP всё равно обновить subUpdates/subAnnounce (клиенты чаще тянут подписку)
#      RESTART_XUI_ON_KEEP=1 — после KEEP перезапустить x-ui (тяжелее; обычно не нужно)
#
# Push на телефон (подписка по HTTP сама push не шлёт — только опрос):
#   NOTIFY_URL — POST text/plain в тело (удобно для https://ntfy.sh/ТВОЙ_топик)
#   NOTIFY_TITLE — заголовок пуша (ntfy: заголовок уведомления)
#   NOTIFY_ON_SWITCH=1 — уведомлять при смене SNI (по умолчанию 1)
#   NOTIFY_ON_KEEP=0 — уведомлять при KEEP+BUMP заголовков (по умолчанию 0, шумно)
#   TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID — дублировать текст в Telegram (sendMessage)
# =============================================================================

set -euo pipefail

XUI_DB="${XUI_DB:-/etc/x-ui/x-ui.db}"
LOCK="/run/reality-failover.lock"
LOG_TAG="[reality-failover]"
TIMEOUT_CONNECT="${TIMEOUT_CONNECT:-3}"
TIMEOUT_TOTAL="${TIMEOUT_TOTAL:-6}"
# 30 минут между полными замерами пула
WATCH_INTERVAL_SEC="${WATCH_INTERVAL_SEC:-1800}"
# Параллельные HTTPS-пробы к хостам пула (xargs -P)
PROBE_PARALLEL="${PROBE_PARALLEL:-30}"

ROTATION_POOL="${ROTATION_POOL:-/usr/local/share/reality-failover/sni-rotation-pool.txt}"
WIDE_POOL="${WIDE_POOL:-/usr/local/share/reality-failover/sni-candidates.txt}"

rotation_pool_nonempty() {
  [[ -r "$1" ]] && [[ "$(grep -vE '^[[:space:]]*(#|$)' "$1" 2>/dev/null | wc -l | tr -d ' ')" -gt 0 ]]
}

if [[ -z "${CANDIDATES_FILE:-}" ]]; then
  if rotation_pool_nonempty "$ROTATION_POOL"; then
    CANDIDATES_FILE="$ROTATION_POOL"
  else
    CANDIDATES_FILE="$WIDE_POOL"
  fi
fi

# SUB_UPDATES_HOURS: в 3x-ui ключ settings.subUpdates = часы для заголовка Profile-Update-Interval (см. subController.go)
SUB_UPDATES_HOURS="${SUB_UPDATES_HOURS:-1}"
BUMP_SUB_ANNOUNCE="${BUMP_SUB_ANNOUNCE:-1}"
BUMP_SUB_ON_KEEP="${BUMP_SUB_ON_KEEP:-1}"
RESTART_XUI_ON_KEEP="${RESTART_XUI_ON_KEEP:-0}"
NOTIFY_ON_SWITCH="${NOTIFY_ON_SWITCH:-1}"
NOTIFY_ON_KEEP="${NOTIFY_ON_KEEP:-0}"

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

# Подтолкнуть клиентов к перезагрузке подписки: минимальный интервал в заголовке + новый Announce.
# Push: ntfy (NOTIFY_URL = https://ntfy.sh/secret-topic) или Telegram.
push_notify() {
  local event="$1"
  local prev_h="$2"
  local new_h="$3"
  local msg="VPN REALITY: SNI ${new_h}. Обнови подписку в клиенте (serverName/sni)."
  if [[ "$event" == "SWITCH" ]]; then
    msg="VPN REALITY: смена SNI ${prev_h} → ${new_h}. Обнови подписку в клиенте."
  elif [[ "$event" == "KEEP" ]]; then
    msg="VPN REALITY: SNI без смены (${new_h}), заголовки подписки обновлены — обнови подписку в клиенте."
  fi

  if [[ -n "${NOTIFY_URL:-}" ]]; then
    local curlargs=(-fsS -m 15 -X POST -H "Content-Type: text/plain; charset=UTF-8" --data-binary "$msg")
    [[ -n "${NOTIFY_TITLE:-}" ]] && curlargs+=(-H "Title: ${NOTIFY_TITLE}")
    if curl "${curlargs[@]}" "$NOTIFY_URL" 2>/dev/null; then
      log "push notify sent → NOTIFY_URL ($event)"
    else
      log "push notify failed (NOTIFY_URL)"
    fi
  fi

  if [[ -n "${TELEGRAM_BOT_TOKEN:-}" && -n "${TELEGRAM_CHAT_ID:-}" ]]; then
    if curl -fsS -m 15 -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
      --data-urlencode "chat_id=${TELEGRAM_CHAT_ID}" \
      --data-urlencode "text=${msg}" 2>/dev/null; then
      log "push notify sent → Telegram ($event)"
    else
      log "push notify failed (Telegram)"
    fi
  fi
}

bump_subscription_headers() {
  local hours="$1"
  local stamp esc
  [[ ! -r "$XUI_DB" ]] && return 0
  [[ "$hours" =~ ^[0-9]+$ ]] || hours=1
  sqlite3 "$XUI_DB" "UPDATE settings SET value='$hours' WHERE key='subUpdates';" 2>/dev/null \
    || sqlite3 "$XUI_DB" "UPDATE setting SET value='$hours' WHERE key='subUpdates';" 2>/dev/null || true
  if [[ "${BUMP_SUB_ANNOUNCE}" == "1" ]]; then
    stamp="$(date -Iseconds 2>/dev/null || date)"
    esc="${stamp//\'/\'\'}"
    sqlite3 "$XUI_DB" "UPDATE settings SET value='SNI sync ${esc}' WHERE key='subAnnounce';" 2>/dev/null \
      || sqlite3 "$XUI_DB" "UPDATE setting SET value='SNI sync ${esc}' WHERE key='subAnnounce';" 2>/dev/null || true
  fi
}

run_once() {
  for bin in jq curl sqlite3; do
    if ! command -v "$bin" >/dev/null; then
      log "missing $bin — apt install -y jq curl sqlite3"
      return 1
    fi
  done
  if [[ "$PROBE_PARALLEL" =~ ^[0-9]+$ ]] && (( PROBE_PARALLEL > 1 )) && ! command -v xargs >/dev/null; then
    log "missing xargs — apt install -y findutils (или поставь PROBE_PARALLEL=1)"
    return 1
  fi

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

  best_host=""
  best_ms=""
  summary=""
  local hostfile probeout okc fc sample_line
  hostfile="$(mktemp)"
  probeout="$(mktemp)"

  printf '%s\n' "${CANDIDATES[@]}" >"$hostfile"

  if [[ "$PROBE_PARALLEL" =~ ^[0-9]+$ ]] && (( PROBE_PARALLEL > 1 )); then
    export TIMEOUT_CONNECT TIMEOUT_TOTAL
    xargs -P "$PROBE_PARALLEL" -a "$hostfile" -I{} bash -c '
      h="$1"
      ms="$(curl -so /dev/null \
        --connect-timeout "$TIMEOUT_CONNECT" \
        --max-time "$TIMEOUT_TOTAL" \
        --tlsv1.3 \
        -w "%{time_total}" \
        "https://$h/" 2>/dev/null)" || ms=""
      if [[ -n "$ms" ]]; then printf "%s\t%s\n" "$h" "$ms"
      else printf "_FAIL_\t%s\n" "$h"; fi
    ' _ {} >"$probeout"
  else
    : >"$probeout"
    while IFS= read -r h; do
      [[ -z "$h" ]] && continue
      ms=$(probe_ms "$h" 2>/dev/null) || ms=""
      if [[ -n "$ms" ]]; then printf '%s\t%s\n' "$h" "$ms"
      else printf '_FAIL_\t%s\n' "$h"; fi
    done <"$hostfile" >>"$probeout"
  fi

  okc=$(grep -cv '^_FAIL_' "$probeout" 2>/dev/null || true)
  fc=$(grep -c '^_FAIL_' "$probeout" 2>/dev/null || true)

  best_line="$(set +o pipefail; grep -v '^_FAIL_' "$probeout" 2>/dev/null | sort -t $'\t' -k2,2n | head -1)"
  if [[ -n "$best_line" ]]; then
    IFS=$'\t' read -r best_host best_ms <<<"$best_line"
  fi

  if [[ "${POOL_PROBE_FULL:-0}" == "1" ]]; then
    while IFS=$'\t' read -r c1 c2; do
      if [[ "$c1" == "_FAIL_" ]]; then
        summary="${summary}${summary:+ }${c2}=FAIL"
      else
        summary="${summary}${summary:+ }${c1}=${c2}s"
      fi
    done <"$probeout"
    log "pool probe (parallel=${PROBE_PARALLEL}): $summary"
  else
    sample_line=""
    while IFS=$'\t' read -r hh mm; do
      [[ "$hh" == "_FAIL_" || -z "$hh" ]] && continue
      sample_line="${sample_line}${sample_line:+ }${hh}=${mm}s"
    done < <(set +o pipefail; grep -v '^_FAIL_' "$probeout" 2>/dev/null | sort -t $'\t' -k2,2n | head -8)
    log "pool probe: parallel=${PROBE_PARALLEL} ok=${okc} fail=${fc} fastest=${best_host:-none} ${best_ms:--}s sample:${sample_line:+ $sample_line}"
  fi

  rm -f "$hostfile" "$probeout"

  if [ -z "$best_host" ]; then
    log "ERROR: no host in pool responded — config unchanged"
    return 0
  fi

  cur_lc=$(host_lc "$current_host")
  best_lc=$(host_lc "$best_host")

  if [ "$cur_lc" = "$best_lc" ]; then
    log "KEEP current=$current_host (fastest in pool, ${best_ms}s)"
    if [[ "${BUMP_SUB_ON_KEEP}" == "1" ]]; then
      bump_subscription_headers "$SUB_UPDATES_HOURS"
      log "subscription headers refreshed on KEEP (subUpdates=${SUB_UPDATES_HOURS}h, subAnnounce) — refetch subscription in client"
      if [[ "${RESTART_XUI_ON_KEEP}" == "1" ]]; then
        systemctl restart x-ui
        log "x-ui restarted (RESTART_XUI_ON_KEEP=1)"
      fi
      if [[ "${NOTIFY_ON_KEEP}" == "1" ]]; then
        push_notify KEEP "$current_host" "$best_host"
      fi
    fi
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
  bump_subscription_headers "$SUB_UPDATES_HOURS"
  systemctl restart x-ui
  log "UPDATED id=$INBOUND_ID target/dest=${best_host}:443 — x-ui restarted; subUpdates=${SUB_UPDATES_HOURS}h + subAnnounce bump (Profile-Update-Interval / Announce)"
  if [[ "${NOTIFY_ON_SWITCH}" == "1" ]]; then
    push_notify SWITCH "$current_host" "$best_host"
  fi
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
    log "watcher start, interval=${WATCH_INTERVAL_SEC}s, pool=$CANDIDATES_FILE (${#CANDIDATES[@]} hosts), PROBE_PARALLEL=$PROBE_PARALLEL"
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
