#!/bin/bash
# Mass rollout of VLESS decryption setting in 3x-ui SQLite.
# - Updates settings.decryption for selected VLESS inbounds
# - Bumps subscription headers (subUpdates/subAnnounce)
# - Restarts x-ui (optional)
#
# Usage:
#   sudo DECRYPTION="..." /usr/local/bin/rollout-vless-decryption.sh
#   sudo DECRYPTION="..." INBOUND_PORT=443 /usr/local/bin/rollout-vless-decryption.sh
#
# Env:
#   XUI_DB=/etc/x-ui/x-ui.db
#   DECRYPTION=...                 # required
#   INBOUND_PORT=443               # optional filter
#   ONLY_ENABLED=1                 # 1=only enabled inbounds (default), 0=all
#   SUB_UPDATES_HOURS=1            # bump Profile-Update-Interval
#   BUMP_SUB_ANNOUNCE=1            # update subAnnounce with timestamp
#   RESTART_XUI=1                  # restart x-ui after DB update
#   DRY_RUN=0                      # 1=print actions only

set -euo pipefail

XUI_DB="${XUI_DB:-/etc/x-ui/x-ui.db}"
DECRYPTION="${DECRYPTION:-}"
INBOUND_PORT="${INBOUND_PORT:-}"
ONLY_ENABLED="${ONLY_ENABLED:-1}"
SUB_UPDATES_HOURS="${SUB_UPDATES_HOURS:-1}"
BUMP_SUB_ANNOUNCE="${BUMP_SUB_ANNOUNCE:-1}"
RESTART_XUI="${RESTART_XUI:-1}"
DRY_RUN="${DRY_RUN:-0}"

log() { echo "[$(date -Iseconds)] [rollout-decryption] $*"; }
die() { echo "ERROR: $*" >&2; exit 1; }

command -v sqlite3 >/dev/null || die "sqlite3 not found"
command -v jq >/dev/null || die "jq not found"

[[ -r "$XUI_DB" ]] || die "DB not readable: $XUI_DB"
[[ -n "$DECRYPTION" ]] || die "DECRYPTION is required"

sql_where="protocol='vless'"
if [[ "$ONLY_ENABLED" == "1" ]]; then
  sql_where="$sql_where AND enable=1"
fi
if [[ -n "$INBOUND_PORT" ]]; then
  sql_where="$sql_where AND port=${INBOUND_PORT}"
fi

ids="$(sqlite3 "$XUI_DB" "SELECT id FROM inbounds WHERE ${sql_where};" | tr -d '\r')"
[[ -n "$ids" ]] || die "No matching VLESS inbounds found for filters: ${sql_where}"

updated=0
unchanged=0

for id in $ids; do
  settings="$(sqlite3 "$XUI_DB" "SELECT settings FROM inbounds WHERE id=${id};" || true)"
  [[ -n "$settings" ]] || continue
  old_dec="$(printf '%s' "$settings" | jq -r '.decryption // "none"' 2>/dev/null || echo "none")"
  new_settings="$(printf '%s' "$settings" | jq -c --arg d "$DECRYPTION" '.decryption = $d')"
  new_dec="$(printf '%s' "$new_settings" | jq -r '.decryption // "none"')"

  if [[ "$old_dec" == "$new_dec" ]]; then
    unchanged=$((unchanged + 1))
    log "inbound id=${id}: already decryption='${new_dec}'"
    continue
  fi

  if [[ "$DRY_RUN" == "1" ]]; then
    log "DRY_RUN inbound id=${id}: '${old_dec}' -> '${new_dec}'"
    updated=$((updated + 1))
    continue
  fi

  tmp="$(mktemp)"
  printf '%s' "$new_settings" >"$tmp"
  sqlite3 "$XUI_DB" "UPDATE inbounds SET settings = readfile('$tmp') WHERE id = ${id};"
  rm -f "$tmp"
  updated=$((updated + 1))
  log "updated inbound id=${id}: '${old_dec}' -> '${new_dec}'"
done

if [[ "$DRY_RUN" != "1" ]]; then
  # Bump subscription refresh interval and announce message.
  sqlite3 "$XUI_DB" "UPDATE settings SET value='${SUB_UPDATES_HOURS}' WHERE key='subUpdates';" 2>/dev/null \
    || sqlite3 "$XUI_DB" "UPDATE setting SET value='${SUB_UPDATES_HOURS}' WHERE key='subUpdates';" 2>/dev/null || true

  if [[ "$BUMP_SUB_ANNOUNCE" == "1" ]]; then
    stamp="$(date -Iseconds 2>/dev/null || date)"
    esc="${stamp//\'/\'\'}"
    msg="VPN config updated (decryption rollout ${esc}). Refresh your subscription."
    msg="${msg//\'/\'\'}"
    sqlite3 "$XUI_DB" "UPDATE settings SET value='${msg}' WHERE key='subAnnounce';" 2>/dev/null \
      || sqlite3 "$XUI_DB" "UPDATE setting SET value='${msg}' WHERE key='subAnnounce';" 2>/dev/null || true
  fi

  if [[ "$RESTART_XUI" == "1" ]]; then
    systemctl restart x-ui
    log "x-ui restarted"
  fi
fi

log "done: updated=${updated}, unchanged=${unchanged}, dry_run=${DRY_RUN}"
