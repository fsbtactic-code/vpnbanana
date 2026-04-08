#!/bin/bash
# Объединяет локальный пул с whitelist SNI из сообщества (мобильный вайтлист РФ).
# Апстрим: https://github.com/hxehex/russia-mobile-internet-whitelist (файл whitelist.txt)
#
# Usage (из корня репозитория):
#   ./scripts/merge-sni-pools.sh
#   MOBILE_WHITELIST_URL=... ./scripts/merge-sni-pools.sh   # другой raw-URL
#
# Читает:  data/sni-candidates-local.txt
# Пишет:   data/sni-candidates.txt (перезапись)
#
# Зависимости: curl, sed, sort

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOCAL="${ROOT}/data/sni-candidates-local.txt"
OUT="${ROOT}/data/sni-candidates.txt"
URL="${MOBILE_WHITELIST_URL:-https://raw.githubusercontent.com/hxehex/russia-mobile-internet-whitelist/main/whitelist.txt}"

if [[ ! -r "$LOCAL" ]]; then
  echo "missing $LOCAL" >&2
  exit 1
fi

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

extract_hosts() {
  sed 's/\r$//' | sed 's/#.*//' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' \
    | grep -v '^[[:space:]]*$' | grep -v '^#' || true
}

normalize_pipe() {
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ -z "$line" ]] && continue
    h="${line%%/*}"
    h="$(echo "$h" | tr '[:upper:]' '[:lower:]' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    [[ -n "$h" ]] && printf '%s\n' "$h"
  done
}

{
  curl -fsSL "$URL" | extract_hosts | normalize_pipe
  extract_hosts <"$LOCAL" | normalize_pipe
} | sort -u >"$TMP"

{
  echo "# Автособранный пул SNI — не редактировать вручную."
  echo "# Запуск: ./scripts/merge-sni-pools.sh"
  echo "# Локальные дополнения: data/sni-candidates-local.txt"
  echo "# Внешний список (SNI): $URL"
  echo "# Репозиторий апстрима: https://github.com/hxehex/russia-mobile-internet-whitelist"
  echo "#"
  cat "$TMP"
} >"$OUT"

echo "wrote $OUT ($(wc -l <"$OUT") lines)" >&2
