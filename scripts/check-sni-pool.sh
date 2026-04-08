#!/bin/bash
# check-sni-pool.sh — проверка доменов для SNI (HTTPS + TLS 1.3, те же таймауты, что reality-failover.sh)
#
# Usage:
#   ./check-sni-pool.sh [domains.txt]
#   ./check-sni-pool.sh - <domains.txt
#   cat domains.txt | ./check-sni-pool.sh -
#   DOMAINS_FILE=~/list.txt ./check-sni-pool.sh   # без аргумента
#
# Файл: по одному хосту в строке; пустые строки и # комментарии игнорируются;
# для строк вида yandex.ru/realty берётся только хост до «/»; дубликаты схлопываются.
#
# Env: TIMEOUT_CONNECT (default 3), TIMEOUT_TOTAL (default 6), PARALLEL (e.g. 25; пусто = по одному)
#
# Install с GitHub:
#   sudo curl -fSL -o /usr/local/bin/check-sni-pool.sh \
#     'https://raw.githubusercontent.com/fsbtactic-code/vpnbanana/main/scripts/check-sni-pool.sh'
#   sudo chmod +x /usr/local/bin/check-sni-pool.sh
# Список доменов из репо (мердж локального пула + russia-mobile-internet-whitelist):
#   curl -fSL -o ~/sni-candidates.txt \
#     'https://raw.githubusercontent.com/fsbtactic-code/vpnbanana/main/data/sni-candidates.txt'
# Обновить состав в репозитории: ./scripts/merge-sni-pools.sh (апстрим: github.com/hxehex/russia-mobile-internet-whitelist)
#
# Только OK-хосты в файл:
#   check-sni-pool.sh domains.txt | awk '$1=="OK"{print $2}' | sort -u > sni-ok.txt

set -uo pipefail

TIMEOUT_CONNECT="${TIMEOUT_CONNECT:-3}"
TIMEOUT_TOTAL="${TIMEOUT_TOTAL:-6}"
PARALLEL="${PARALLEL:-}"

tmpin=""
if [[ "${1:-}" == "-" ]]; then
  tmpin="$(mktemp)"
  cat >"$tmpin"
  f="$tmpin"
elif [[ -n "${1:-}" ]]; then
  f="$1"
else
  f="${DOMAINS_FILE:-$HOME/sni-candidates.txt}"
fi

if [[ ! -r "$f" ]]; then
  echo "usage: $0 [- | путь/к/domains.txt]" >&2
  echo "  нет файла: скачай с GitHub: curl -fSL -o ~/sni-candidates.txt \\" >&2
  echo "    'https://raw.githubusercontent.com/fsbtactic-code/vpnbanana/main/data/sni-candidates.txt'" >&2
  echo "  или: nano $HOME/sni-candidates.txt" >&2
  echo "  или передай файл: $0 /path/to/domains.txt" >&2
  echo "  или со stdin: $0 - <domains.txt   или   cat domains.txt | $0 -" >&2
  echo "file not readable: $f" >&2
  exit 1
fi

tmp="$(mktemp)"
out="$(mktemp)"
cleanup() { rm -f "$tmp" "$out" ${tmpin:+"$tmpin"} 2>/dev/null; }
trap cleanup EXIT

while IFS= read -r line || [[ -n "$line" ]]; do
  line="${line%%#*}"
  line="$(echo "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
  [[ -z "$line" ]] && continue
  [[ "$line" == \#* ]] && continue
  h="${line%%/*}"
  h="$(echo "$h" | tr '[:upper:]' '[:lower:]')"
  [[ -z "$h" ]] && continue
  echo "$h"
done < "$f" | sort -u > "$tmp"

export TIMEOUT_CONNECT TIMEOUT_TOTAL

probe_line() {
  local h="$1"
  local ms=""
  ms="$(curl -so /dev/null \
    --connect-timeout "$TIMEOUT_CONNECT" \
    --max-time "$TIMEOUT_TOTAL" \
    --tlsv1.3 \
    -w '%{time_total}' \
    "https://$h/" 2>/dev/null)" || ms=""
  if [[ -n "$ms" ]]; then
    printf 'OK\t%s\t%s\n' "$h" "$ms"
  else
    printf 'FAIL\t%s\t-\n' "$h"
  fi
}

if [[ -n "$PARALLEL" ]] && [[ "$PARALLEL" =~ ^[0-9]+$ ]] && (( PARALLEL > 1 )); then
  xargs -P "$PARALLEL" -a "$tmp" -I{} bash -c '
    h="$1"
    ms=""
    ms="$(curl -so /dev/null \
      --connect-timeout "$TIMEOUT_CONNECT" \
      --max-time "$TIMEOUT_TOTAL" \
      --tlsv1.3 \
      -w "%{time_total}" \
      "https://$h/" 2>/dev/null)" || ms=""
    if [[ -n "$ms" ]]; then printf "OK\t%s\t%s\n" "$h" "$ms"
    else printf "FAIL\t%s\t-\n" "$h"; fi
  ' _ {} > "$out"
else
  : > "$out"
  while IFS= read -r h; do
    [[ -z "$h" ]] && continue
    probe_line "$h" >> "$out"
  done < "$tmp"
fi

# OK — по возрастанию задержки (колонка 3); FAIL — по имени хоста
awk -F '\t' '$1=="OK"{print}' "$out" | sort -t $'\t' -k3,3n
awk -F '\t' '$1=="FAIL"{print}' "$out" | sort -t $'\t' -k2,2
ok=$(grep -c '^OK' "$out" || true)
fail=$(grep -c '^FAIL' "$out" || true)
echo "--- итого: OK=$ok FAIL=$fail (уникальных хостов: $(wc -l <"$tmp"))" >&2
