#!/usr/bin/env bash
set -euo pipefail

SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SELF/.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"

say() { printf '\033[1;33m==>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" = 0 ] || die "запусти от root"
[ -f "$ENV_FILE" ] || die "сначала server/install.sh (нет $ENV_FILE)"
# shellcheck disable=SC1090
. "$ENV_FILE"

BOT_TOKEN="${BOT_TOKEN:-${1:-}}"
ADMIN_ID="${ADMIN_ID:-${2:-}}"
[ -n "$BOT_TOKEN" ] || die "укажи токен бота: BOT_TOKEN=... ADMIN_ID=... $0  (токен у @BotFather, id у @userinfobot)"
[ -n "$ADMIN_ID" ] || die "укажи свой Telegram id: ADMIN_ID=...  (узнать у @userinfobot)"

put() {
  local k="$1" v="$2"
  if grep -q "^$k=" "$ENV_FILE"; then sed -i "s|^$k=.*|$k=$v|" "$ENV_FILE"; else printf '%s=%s\n' "$k" "$v" >>"$ENV_FILE"; fi
  export "$k=$v"
}
put BOT_TOKEN "$BOT_TOKEN"
put ADMIN_ID "$ADMIN_ID"
put DB_PATH "${DB_PATH:-$SELF/db.sqlite}"
put XRAY_CONFIG "${XRAY_CONFIG:-/usr/local/etc/xray/config.json}"
put XRAY_API "${XRAY_API:-127.0.0.1:10085}"
put HY_MAIN_STATS "http://127.0.0.1:${HY_MAIN_STATS_PORT:-9443}"
put HY_TURBO_STATS "http://127.0.0.1:${HY_TURBO_STATS_PORT:-9444}"
put SUPPORT_URL "${SUPPORT_URL:-}"

say "python venv"
export DEBIAN_FRONTEND=noninteractive
apt-get install -y -qq python3 python3-venv python3-pip >/dev/null 2>&1 || { apt-get update -qq && apt-get install -y -qq python3 python3-venv python3-pip >/dev/null; }
[ -d "$SELF/.venv" ] || python3 -m venv "$SELF/.venv"
"$SELF/.venv/bin/pip" install -q -r "$SELF/requirements.txt"

say "RU-обход (Happ routing deeplink)"
python3 "$REPO_ROOT/rules/build_happ_routing.py" >/dev/null || true
cp "$REPO_ROOT/rules/happ-routing.deeplink" "$SELF/backend/routing.deeplink" 2>/dev/null || true

say "Hysteria -> http-auth (пер-юзер подписки)"
put HY_AUTH_MODE http
. "$REPO_ROOT/server/lib/render.sh"
render_hysteria "${HY_MAIN_PORT:-443}"  "${HY_MAIN_STATS_PORT:-9443}"  yes http >/etc/hysteria/config.yaml
render_hysteria "${HY_TURBO_PORT:-8444}" "${HY_TURBO_STATS_PORT:-9444}" no  http >/etc/hysteria/turbo.yaml
chown hysteria:hysteria /etc/hysteria/config.yaml /etc/hysteria/turbo.yaml 2>/dev/null || true
chmod 640 /etc/hysteria/config.yaml /etc/hysteria/turbo.yaml

say "systemd"
for u in vpnbanana-backend.service vpnbanana-bot.service vpnbanana-accounting.service vpnbanana-accounting.timer; do
  sed -e "s#/root/vpnbanana#$REPO_ROOT#g" -e "s#--port 8090#--port ${BACKEND_PORT:-8090}#g" "$SELF/systemd/$u" >/etc/systemd/system/"$u"
done
systemctl daemon-reload
systemctl enable vpnbanana-backend.service vpnbanana-bot.service vpnbanana-accounting.timer >/dev/null 2>&1 || true
systemctl restart vpnbanana-backend.service
systemctl restart hysteria-server hysteria-server@turbo
systemctl restart vpnbanana-bot.service
systemctl restart vpnbanana-accounting.timer 2>/dev/null || systemctl start vpnbanana-accounting.timer

say "health-check /auth"
ok=0
for _ in $(seq 1 15); do
  r="$(curl -fsS -X POST "http://127.0.0.1:${BACKEND_PORT:-8090}/auth" -H 'Content-Type: application/json' -d "{\"auth\":\"$LEGACY_HY_MAIN\"}" || true)"
  case "$r" in *'"ok":true'*) ok=1; break;; esac
  sleep 0.5
done
[ "$ok" = 1 ] || die "backend не отвечает на /auth - проверь: journalctl -u vpnbanana-backend -n50"

echo
say "ГОТОВО. Бот выдачи подписок поднят."
cat <<SUMMARY

  Бот:     открой его в Telegram, /start от своего аккаунта (id $ADMIN_ID = админ).
  Меню:    /start у админа -> кнопка "Выдать подписку"; /users, /stats.
  Кабинет: каждому юзеру даётся ссылка вида https://$DOMAIN/u/<token> + Mini App /app.
  Узлы в подписке: Reality, XHTTP$([ -n "${CF_HOST:-}" ] && echo ", XHTTP+CDN"), Hysteria, Hysteria turbo.
$([ -z "${CF_HOST:-}" ] && echo "  (XHTTP+CDN выключен: задай CF_HOST в .env и перезапусти, чтобы добавить CF-узел.)")
SUMMARY
