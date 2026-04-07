#!/bin/bash
# =============================================================================
# REALITY SNI / dest failover for 3x-ui (SQLite)
#
# Logic:
#   - If current reality host answers (TLS 1.3 HTTPS) -> exit
#   - Else pick fastest host from CANDIDATES that answers
#   - Update inbound stream_settings (port 443, vless, enabled) and restart x-ui
#
# IMPORTANT — clients:
#   After SNI change, old vless:// links with old "sni=" stop matching server.
#   Use x-ui subscription in the client and refresh subscription after switch,
#   or re-export the node from the panel.
#
# Install:
#   sudo apt install -y jq curl sqlite3
#   sudo cp reality-failover.sh /usr/local/bin/reality-failover.sh
#   sudo chmod +x /usr/local/bin/reality-failover.sh
#
# Cron (every 10 minutes):
#   echo '*/10 * * * * root /usr/local/bin/reality-failover.sh >> /var/log/reality-failover.log 2>&1' | sudo tee /etc/cron.d/reality-failover
#
# Env overrides: XUI_DB, TIMEOUT_CONNECT, TIMEOUT_TOTAL
# =============================================================================

set -euo pipefail

XUI_DB="${XUI_DB:-/etc/x-ui/x-ui.db}"
LOCK="/run/reality-failover.lock"
LOG_TAG="[reality-failover]"
TIMEOUT_CONNECT="${TIMEOUT_CONNECT:-3}"
TIMEOUT_TOTAL="${TIMEOUT_TOTAL:-6}"

# Hostnames only (no :443). Earlier = tie-break if same speed.
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

exec 200>"$LOCK"
if ! flock -n 200; then
  log "another instance running, exit"
  exit 0
fi

for bin in jq curl sqlite3; do
  command -v "$bin" >/dev/null || { log "missing $bin — apt install -y jq curl sqlite3"; exit 1; }
done

if [ ! -r "$XUI_DB" ]; then
  log "DB not readable: $XUI_DB"
  exit 1
fi

ROW=$(sqlite3 "$XUI_DB" "SELECT id, stream_settings FROM inbounds WHERE enable = 1 AND port = 443 AND protocol = 'vless' LIMIT 1;" || true)
if [ -z "$ROW" ]; then
  log "no enabled vless inbound on 443 — create it in the panel first"
  exit 0
fi

INBOUND_ID=$(echo "$ROW" | cut -d'|' -f1)
STREAM_JSON=$(echo "$ROW" | cut -d'|' -f2-)

if [ -z "$INBOUND_ID" ] || [ -z "$STREAM_JSON" ]; then
  log "failed to read inbound"
  exit 1
fi

current_dest=$(echo "$STREAM_JSON" | jq -r '.realitySettings.dest // empty' 2>/dev/null || true)
current_host="${current_dest%%:*}"

if [ -z "$current_host" ] || [ "$current_host" = "null" ]; then
  current_host="${CANDIDATES[0]}"
  log "no dest in DB, treat current as $current_host"
fi

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

if is_up "$current_host"; then
  log "OK current=$current_host"
  exit 0
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
  exit 1
fi

log "PICK best=$best_host time=${best_ms}s"

NEW_JSON=$(echo "$STREAM_JSON" | jq -c --arg h "$best_host" '
  .realitySettings.dest = ($h + ":443")
  | .realitySettings.serverNames = [$h]
')

TMPJSON=$(mktemp)
trap 'rm -f "$TMPJSON"' EXIT
printf '%s' "$NEW_JSON" > "$TMPJSON"

# sqlite3 readfile() (SQLite 3.35+); path must not contain '
sqlite3 "$XUI_DB" "UPDATE inbounds SET stream_settings = readfile('$TMPJSON') WHERE id = ${INBOUND_ID};"

systemctl restart x-ui

log "UPDATED id=$INBOUND_ID dest=${best_host}:443 — x-ui restarted (refresh client subscription / sni)"
exit 0
