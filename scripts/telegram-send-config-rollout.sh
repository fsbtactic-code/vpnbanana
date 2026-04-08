#!/bin/bash
# Telegram broadcast helper for VPN config rollout.
# Supports:
# - Generic broadcast to comma-separated CHAT_IDS
# - Personalized mode from TSV: chat_id <tab> name <tab> subscription_url
# - Optional QR generation via qrencode (sendPhoto)
#
# Usage:
#   sudo TELEGRAM_BOT_TOKEN=... CHAT_IDS="111,222" ./telegram-send-config-rollout.sh
#   sudo TELEGRAM_BOT_TOKEN=... SUBS_FILE=/root/subscribers.tsv ./telegram-send-config-rollout.sh
#
# If TELEGRAM_BOT_TOKEN/CHAT_IDS are empty, script tries 3x-ui settings:
# - tgBotToken
# - tgBotChatId (comma-separated chat IDs)

set -euo pipefail

XUI_DB="${XUI_DB:-/etc/x-ui/x-ui.db}"
TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
CHAT_IDS="${CHAT_IDS:-}"
SUBS_FILE="${SUBS_FILE:-}"            # TSV: chat_id \t name \t subscription_url
MESSAGE_FILE="${MESSAGE_FILE:-}"      # optional plain text
QR_TMP_DIR="${QR_TMP_DIR:-/tmp/tg-config-qr}"

log() { echo "[$(date -Iseconds)] [tg-rollout] $*"; }
die() { echo "ERROR: $*" >&2; exit 1; }

xui_setting_get() {
  local key="$1"
  local v=""
  v="$(sqlite3 "$XUI_DB" "SELECT value FROM settings WHERE key='${key}';" 2>/dev/null | tr -d '\r\n' || true)"
  [[ -z "$v" ]] && v="$(sqlite3 "$XUI_DB" "SELECT value FROM setting WHERE key='${key}';" 2>/dev/null | tr -d '\r\n' || true)"
  printf '%s' "$v"
}

if [[ -z "$TELEGRAM_BOT_TOKEN" && -r "$XUI_DB" ]]; then
  TELEGRAM_BOT_TOKEN="$(xui_setting_get tgBotToken)"
fi
if [[ -z "$CHAT_IDS" && -r "$XUI_DB" ]]; then
  CHAT_IDS="$(xui_setting_get tgBotChatId)"
fi

[[ -n "$TELEGRAM_BOT_TOKEN" ]] || die "TELEGRAM_BOT_TOKEN is empty"

default_message() {
  cat <<'EOF'
Обновление VPN завершено, можно пользоваться дальше.
Подключили к авторотации SNI лучшие российские CDN и снизили пинг.

Что улучшили:
1) Добавили дополнительную маскировку (decryption rollout).
2) Увеличили и стабилизировали пул SNI.
3) Снизили ошибки при обновлении подписки.

Если VPN перестает работать:
1. Отключите VPN.
2. Обновите подписку.
3. Включите VPN снова.

Клиенты:
- Android (v2rayNG): https://github.com/2dust/v2rayNG/releases
- Android/Windows/macOS (Hiddify): https://hiddify.com/app/
- Windows (v2rayN): https://github.com/2dust/v2rayN/releases
- iOS (поддерживаемый клиент из App Store, например Hiddify/Happ): https://hiddify.com/app/

Рекомендации (необязательно):
- Обновлять подписку после уведомлений.
- Оставить автообновление подписки.
- При проблемах сменить сеть (Wi-Fi/LTE) и переподключиться.
EOF
}

if [[ -n "$MESSAGE_FILE" ]]; then
  [[ -r "$MESSAGE_FILE" ]] || die "MESSAGE_FILE not readable: $MESSAGE_FILE"
  MESSAGE="$(cat "$MESSAGE_FILE")"
else
  MESSAGE="$(default_message)"
fi

tg_send_message() {
  local chat_id="$1"
  local text="$2"
  curl -fsS -m 20 -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    --data-urlencode "chat_id=${chat_id}" \
    --data-urlencode "text=${text}" 2>/dev/null
}

tg_send_qr() {
  local chat_id="$1"
  local caption="$2"
  local image_path="$3"
  curl -fsS -m 25 -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendPhoto" \
    -F "chat_id=${chat_id}" \
    -F "caption=${caption}" \
    -F "photo=@${image_path}" 2>/dev/null
}

if [[ -n "$SUBS_FILE" ]]; then
  [[ -r "$SUBS_FILE" ]] || die "SUBS_FILE not readable: $SUBS_FILE"
  mkdir -p "$QR_TMP_DIR"
  has_qr=0
  if command -v qrencode >/dev/null; then
    has_qr=1
  fi

  sent=0
  while IFS=$'\t' read -r chat_id name sub_url || [[ -n "${chat_id:-}" ]]; do
    [[ -z "${chat_id:-}" ]] && continue
    [[ "${chat_id:0:1}" == "#" ]] && continue
    name="${name:-пользователь}"
    sub_url="${sub_url:-}"

    text="${MESSAGE}"
    if [[ -n "$sub_url" ]]; then
      text="${text}

Персональная подписка для ${name}:
${sub_url}"
    fi

    if tg_send_message "$chat_id" "$text"; then
      log "sent message to chat_id=${chat_id}"
      sent=$((sent + 1))
    else
      log "failed sendMessage chat_id=${chat_id}"
    fi

    if [[ $has_qr -eq 1 && -n "$sub_url" ]]; then
      qr_file="${QR_TMP_DIR}/${chat_id}.png"
      qrencode -o "$qr_file" -s 8 -m 2 "$sub_url"
      tg_send_qr "$chat_id" "QR для быстрой установки конфигурации (${name})" "$qr_file" >/dev/null || true
    fi
  done <"$SUBS_FILE"

  log "done personalized mode: sent=${sent}"
  exit 0
fi

[[ -n "$CHAT_IDS" ]] || die "CHAT_IDS is empty and SUBS_FILE not provided"

sent=0
IFS=',' read -ra ids <<< "$CHAT_IDS"
for raw in "${ids[@]}"; do
  id="$(echo "$raw" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
  [[ -z "$id" ]] && continue
  if tg_send_message "$id" "$MESSAGE"; then
    log "sent broadcast to chat_id=${id}"
    sent=$((sent + 1))
  else
    log "failed sendMessage chat_id=${id}"
  fi
done

log "done broadcast mode: sent=${sent}"
