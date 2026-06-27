#!/usr/bin/env bash
set -euo pipefail
# Останавливает и удаляет узел. Пакеты hysteria/xray/nginx НЕ сносит (могут быть нужны),
# только конфиги и сервисы проекта. .env остаётся - удали вручную если нужно.

say() { printf '\033[1;33m==>\033[0m %s\n' "$*"; }
[ "$(id -u)" = 0 ] || { echo "root нужен" >&2; exit 1; }

for s in vpnbanana-bot vpnbanana-accounting.timer vpnbanana-backend warp-health.timer \
         hysteria-server hysteria-server@turbo; do
  systemctl disable --now "$s" 2>/dev/null || true
done

rm -f /etc/nginx/sites-enabled/vpnbanana.conf /etc/nginx/sites-available/vpnbanana.conf
rm -f /etc/nginx/sites-enabled/vpnbanana-acme.conf /etc/nginx/sites-available/vpnbanana-acme.conf
nginx -t 2>/dev/null && systemctl reload nginx 2>/dev/null || true

rm -f /etc/hysteria/config.yaml /etc/hysteria/turbo.yaml
rm -f /etc/systemd/system/vpnbanana-*.service /etc/systemd/system/vpnbanana-*.timer
rm -f /etc/systemd/system/warp-health.service /etc/systemd/system/warp-health.timer
rm -f /etc/sysctl.d/99-vpn.conf
systemctl daemon-reload

say "узел остановлен. .env и LE-сертификаты не тронуты."
