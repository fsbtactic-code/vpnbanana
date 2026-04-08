#!/bin/bash
# С сервера: проверяет домены на пригодность как публичный TLS-dest для VLESS+REALITY
# (резолв DNS + HTTPS с TLS 1.3 и проверкой сертификата под имя хоста — как у curl без -k).
# Сохраняет отсортированный по задержке список для reality-failover.
#
# Рекомендуемая база: data/SNICDN.txt (CDN-focused).
# Широкий fallback: data/sni-candidates.txt (или merge-sni-pools.sh).
#
# Usage:
#   sudo ./scripts/build-sni-rotation-pool.sh
#   SOURCE=/path/in.txt OUT=/path/out.txt TOP_N=80 PARALLEL=40 ./scripts/build-sni-rotation-pool.sh
#
# Env:
#   SOURCE          — входной список хостов (по умолчанию /usr/local/share/reality-failover/sni-cdn.txt)
#   OUT             — куда писать пул лучших CDN (по умолчанию /usr/local/share/reality-failover/SNICDNBEST.txt)
#   TOP_N           — максимум хостов в пуле (по умолчанию 120; 0 = без лимита)
#   PARALLEL        — параллельные curl (по умолчанию 30)
#   TIMEOUT_CONNECT, TIMEOUT_TOTAL — как в reality-failover
#   CURL_INSECURE=1 — ослабить до curl -k (не рекомендуется для REALITY)
#   STRICT_OPENSSL=1 — дополнительно openssl s_client -tls1_3 (медленнее, нужен openssl)
#
# Install:
#   sudo curl -fSL -o /usr/local/bin/build-sni-rotation-pool.sh \
#     'https://raw.githubusercontent.com/fsbtactic-code/vpnbanana/main/scripts/build-sni-rotation-pool.sh'
#   sudo chmod +x /usr/local/bin/build-sni-rotation-pool.sh

set -euo pipefail

TIMEOUT_CONNECT="${TIMEOUT_CONNECT:-3}"
TIMEOUT_TOTAL="${TIMEOUT_TOTAL:-6}"
SOURCE="${SOURCE:-/usr/local/share/reality-failover/sni-cdn.txt}"
OUT="${OUT:-/usr/local/share/reality-failover/SNICDNBEST.txt}"
TOP_N="${TOP_N:-120}"
PARALLEL="${PARALLEL:-30}"
STRICT_OPENSSL="${STRICT_OPENSSL:-0}"

if [[ ! -r "$SOURCE" ]]; then
  echo "SOURCE not readable: $SOURCE" >&2
  echo "Скачай: curl -fSL -o $SOURCE 'https://raw.githubusercontent.com/fsbtactic-code/vpnbanana/main/data/SNICDN.txt'" >&2
  exit 1
fi

command -v curl >/dev/null || { echo "need curl" >&2; exit 1; }

tmp_hosts="$(mktemp)"
tmp_out="$(mktemp)"
trap 'rm -f "$tmp_hosts" "$tmp_out"' EXIT

while IFS= read -r line || [[ -n "$line" ]]; do
  line="${line%%#*}"
  line="$(echo "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
  [[ -z "$line" || "$line" == \#* ]] && continue
  h="${line%%/*}"
  h="$(echo "$h" | tr '[:upper:]' '[:lower:]')"
  h="${h//$'\r'/}"
  [[ -n "$h" ]] && echo "$h"
done <"$SOURCE" | sort -u >"$tmp_hosts"

host_count="$(wc -l <"$tmp_hosts")"
echo "[build-sni-rotation-pool] unique hosts: $host_count" >&2

if [[ "${CURL_INSECURE:-0}" == "1" ]]; then
  CURL_EXTRA_INSECURE=1
else
  CURL_EXTRA_INSECURE=
fi
export TIMEOUT_CONNECT TIMEOUT_TOTAL STRICT_OPENSSL CURL_EXTRA_INSECURE

xargs -P "$PARALLEL" -a "$tmp_hosts" -I{} bash -c '
  h="$1"
  if ! getent ahosts "$h" 2>/dev/null | head -1 | grep -q .; then
    printf "FAIL\t%s\t-\tno_dns\n" "$h"
    exit 0
  fi
  insecure=""
  [[ -n "${CURL_EXTRA_INSECURE:-}" ]] && insecure="-k"
  ms=""
  ms="$(curl -so /dev/null $insecure \
    --connect-timeout "$TIMEOUT_CONNECT" \
    --max-time "$TIMEOUT_TOTAL" \
    --tlsv1.3 \
    -w "%{time_total}" \
    "https://$h/" 2>/dev/null)" || ms=""
  if [[ -z "$ms" ]]; then
    printf "FAIL\t%s\t-\ttls_or_http\n" "$h"
    exit 0
  fi
  if [[ "${STRICT_OPENSSL:-0}" == "1" ]] && command -v openssl >/dev/null; then
    if ! echo | timeout 5 openssl s_client -connect "${h}:443" -servername "$h" -tls1_3 </dev/null 2>/dev/null | grep -qi "TLSv1.3"; then
      printf "FAIL\t%s\t-\topenssl_tls13\n" "$h"
      exit 0
    fi
  fi
  printf "OK\t%s\t%s\n" "$h" "$ms"
' _ {} >"$tmp_out"

ok_lines="$(grep -c '^OK' "$tmp_out" 2>/dev/null || true)"
fail_lines="$(grep -c '^FAIL' "$tmp_out" 2>/dev/null || true)"
echo "[build-sni-rotation-pool] probe OK=$ok_lines FAIL=$fail_lines" >&2

sorted_ok="$(mktemp)"
awk -F '\t' '$1=="OK"{print}' "$tmp_out" | sort -t $'\t' -k3,3n >"$sorted_ok"
if [[ "${TOP_N:-0}" =~ ^[0-9]+$ ]] && (( TOP_N > 0 )); then
  head -n "$TOP_N" "$sorted_ok" >"${sorted_ok}.cap"
  mv "${sorted_ok}.cap" "$sorted_ok"
fi

out_dir="$(dirname "$OUT")"
mkdir -p "$out_dir"

{
  echo "# Пул для reality-failover (только прошедшие проверку REALITY-dest, по возрастанию задержки)."
  echo "# Сборка: build-sni-rotation-pool.sh | SOURCE=$SOURCE | TOP_N=$TOP_N | $(date -Iseconds 2>/dev/null || date)"
  echo "#"
  awk -F '\t' '{print $2}' "$sorted_ok"
} >"$OUT"

host_lines="$(grep -vE '^[[:space:]]*(#|$)' "$OUT" 2>/dev/null | wc -l | tr -d ' ')"
echo "[build-sni-rotation-pool] wrote $OUT ($host_lines hosts)" >&2
