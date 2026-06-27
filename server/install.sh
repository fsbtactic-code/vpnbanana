#!/usr/bin/env bash
set -euo pipefail

SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SELF/.." && pwd)"
ENV_FILE="${ENV_FILE:-$REPO_ROOT/.env}"
. "$SELF/lib/render.sh"

WEBROOT="${WEBROOT:-/var/www/vpnbanana}"

say()  { printf '\033[1;33m==>\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" = 0 ] || die "запусти от root"
command -v apt-get >/dev/null || die "поддерживается Debian/Ubuntu (apt)"

DOMAIN="${DOMAIN:-${1:-}}"
[ -n "$DOMAIN" ] || die "укажи домен: DOMAIN=vpn.example.com $0  (DNS A-запись должна указывать на этот сервер)"

touch "$ENV_FILE"; chmod 600 "$ENV_FILE"
# shellcheck disable=SC1090
. "$ENV_FILE"

put() {
  local k="$1" v="$2"
  if grep -q "^$k=" "$ENV_FILE"; then
    sed -i "s|^$k=.*|$k=$v|" "$ENV_FILE"
  else
    printf '%s=%s\n' "$k" "$v" >>"$ENV_FILE"
  fi
  export "$k=$v"
}
keep() {
  local k="$1" gen="$2" cur
  cur="$(grep "^$k=" "$ENV_FILE" | head -1 | cut -d= -f2-)"
  if [ -n "$cur" ]; then export "$k=$cur"; else put "$k" "$gen"; fi
}

say "пакеты"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq curl openssl nginx certbot ufw jq ca-certificates >/dev/null

command -v hysteria >/dev/null || { say "ставлю hysteria2"; bash <(curl -fsSL https://get.hy2.sh/) >/dev/null; }
command -v xray >/dev/null || { say "ставлю xray"; bash -c "$(curl -fsSL https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install >/dev/null; }

say "секреты"
put DOMAIN "$DOMAIN"
put SERVER_IP "$(curl -fsS4 https://api.ipify.org || hostname -I | awk '{print $1}')"
put HY_MAIN_PORT      "${HY_MAIN_PORT:-443}"
put HY_TURBO_PORT     "${HY_TURBO_PORT:-8444}"
put REALITY_PORT      "${REALITY_PORT:-8443}"
put XHTTP_NL_PORT     "${XHTTP_NL_PORT:-8091}"
put BACKEND_PORT      "${BACKEND_PORT:-8090}"
put HY_MAIN_STATS_PORT  "${HY_MAIN_STATS_PORT:-9443}"
put HY_TURBO_STATS_PORT "${HY_TURBO_STATS_PORT:-9444}"
put REALITY_SNI  "${REALITY_SNI:-www.samsung.com}"
put REALITY_FLOW "${REALITY_FLOW:-xtls-rprx-vision}"
put REALITY_FP   "${REALITY_FP:-firefox}"
put MASQ_URL     "${MASQ_URL:-https://www.samsung.com/}"
put PROFILE_TITLE "${PROFILE_TITLE:-BananaVPN}"
put CF_HOST      "${CF_HOST:-}"
put HY_AUTH_MODE "${HY_AUTH_MODE:-static}"

keep OWNER_UUID          "$(cat /proc/sys/kernel/random/uuid)"
keep REALITY_SID         "$(openssl rand -hex 8)"
keep XHTTP_PATH          "/$(openssl rand -hex 6)"
keep OBFS_PASSWORD       "$(openssl rand -base64 18 | tr -d '/+=')"
keep HY_STATIC_PASSWORD  "$(openssl rand -base64 18 | tr -d '/+=')"
keep HYSTERIA_STATS_SECRET "$(openssl rand -hex 16)"
keep OWNER_SUB_TOKEN     "$(openssl rand -hex 16)"

if [ -z "${REALITY_PRIV:-}" ]; then
  KP="$(xray x25519)"
  put REALITY_PRIV "$(printf '%s\n' "$KP" | awk '/Private/{print $NF}')"
  put REALITY_PBK  "$(printf '%s\n' "$KP" | awk '/Public/{print $NF}')"
fi
put LEGACY_HY_MAIN  "$HY_STATIC_PASSWORD"
put LEGACY_HY_TURBO "$HY_STATIC_PASSWORD"

say "TLS-сертификат ($DOMAIN)"
mkdir -p "$WEBROOT/.well-known/acme-challenge"
if [ ! -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
  cat >/etc/nginx/sites-available/vpnbanana-acme.conf <<NGINX
server {
    listen 80;
    server_name $DOMAIN;
    location /.well-known/acme-challenge/ { root $WEBROOT; }
    location / { return 200 ok; }
}
NGINX
  ln -sf /etc/nginx/sites-available/vpnbanana-acme.conf /etc/nginx/sites-enabled/vpnbanana-acme.conf
  rm -f /etc/nginx/sites-enabled/default
  nginx -t && systemctl reload nginx
  certbot certonly --webroot -w "$WEBROOT" -d "$DOMAIN" \
    --non-interactive --agree-tos --register-unsafely-without-email
  rm -f /etc/nginx/sites-enabled/vpnbanana-acme.conf
fi

cat >/etc/letsencrypt/renewal-hooks/deploy/vpnbanana.sh <<HOOK
#!/usr/bin/env bash
cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem /etc/hysteria/cert.pem
cp /etc/letsencrypt/live/$DOMAIN/privkey.pem   /etc/hysteria/key.pem
chown hysteria:hysteria /etc/hysteria/cert.pem /etc/hysteria/key.pem 2>/dev/null || true
systemctl restart hysteria-server hysteria-server@turbo 2>/dev/null || true
systemctl reload nginx 2>/dev/null || true
HOOK
chmod +x /etc/letsencrypt/renewal-hooks/deploy/vpnbanana.sh
bash /etc/letsencrypt/renewal-hooks/deploy/vpnbanana.sh

say "конфиги"
render_hysteria "$HY_MAIN_PORT"  "$HY_MAIN_STATS_PORT"  yes "$HY_AUTH_MODE" >/etc/hysteria/config.yaml
render_hysteria "$HY_TURBO_PORT" "$HY_TURBO_STATS_PORT" no  "$HY_AUTH_MODE" >/etc/hysteria/turbo.yaml
chown hysteria:hysteria /etc/hysteria/config.yaml /etc/hysteria/turbo.yaml 2>/dev/null || true
chmod 640 /etc/hysteria/config.yaml /etc/hysteria/turbo.yaml
render_xray >/usr/local/etc/xray/config.json
xray -test -c /usr/local/etc/xray/config.json >/dev/null

cp "$SELF/templates/sysctl-99-vpn.conf" /etc/sysctl.d/99-vpn.conf
sysctl -p /etc/sysctl.d/99-vpn.conf >/dev/null || true

mkdir -p /etc/systemd/system/xray.service.d
cp "$SELF/templates/systemd/xray.service.d-override.conf" /etc/systemd/system/xray.service.d/override.conf

say "firewall"
ufw allow 22/tcp >/dev/null 2>&1 || true
ufw allow 80/tcp >/dev/null 2>&1 || true
ufw allow 443/tcp >/dev/null 2>&1 || true
ufw allow "$HY_MAIN_PORT"/udp >/dev/null 2>&1 || true
ufw allow "$REALITY_PORT"/tcp >/dev/null 2>&1 || true
ufw allow "$HY_TURBO_PORT"/udp >/dev/null 2>&1 || true
ufw --force enable >/dev/null 2>&1 || true

say "nginx + rules"
mkdir -p "$WEBROOT/rules" "$WEBROOT/sub"
cp "$REPO_ROOT/rules/ru-whitelist.json" "$REPO_ROOT/rules/ru-whitelist-clash.yaml" "$REPO_ROOT/rules/ru-whitelist.txt" "$WEBROOT/rules/" 2>/dev/null || true
WEBROOT="$WEBROOT" render_nginx "$SELF/templates/nginx-vpn.conf.tmpl" >/etc/nginx/sites-available/vpnbanana.conf
rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/vpnbanana.conf /etc/nginx/sites-enabled/vpnbanana.conf
nginx -t && systemctl reload nginx

say "systemd"
if [ ! -f /etc/systemd/system/hysteria-server@.service ] && [ ! -f /lib/systemd/system/hysteria-server@.service ]; then
  cat >/etc/systemd/system/hysteria-server@.service <<'UNIT'
[Unit]
Description=Hysteria Server Service (%i.yaml)
After=network.target
[Service]
Type=simple
ExecStart=/usr/local/bin/hysteria server --config /etc/hysteria/%i.yaml
WorkingDirectory=/etc/hysteria
Restart=on-failure
[Install]
WantedBy=multi-user.target
UNIT
fi
systemctl daemon-reload
systemctl enable xray hysteria-server hysteria-server@turbo >/dev/null 2>&1 || true
systemctl restart xray hysteria-server hysteria-server@turbo

owner_sub() {
  local nodes
  nodes="hysteria2://$HY_STATIC_PASSWORD@$DOMAIN:$HY_MAIN_PORT?obfs=salamander&obfs-password=$OBFS_PASSWORD&sni=$DOMAIN#BananaVPN-Hysteria"$'\n'
  nodes+="hysteria2://$HY_STATIC_PASSWORD@$DOMAIN:$HY_TURBO_PORT?sni=$DOMAIN#BananaVPN-Turbo"$'\n'
  nodes+="vless://$OWNER_UUID@$DOMAIN:$REALITY_PORT?encryption=none&flow=$REALITY_FLOW&security=reality&sni=$REALITY_SNI&fp=$REALITY_FP&pbk=$REALITY_PBK&sid=$REALITY_SID&type=tcp#BananaVPN-Reality"$'\n'
  nodes+="vless://$OWNER_UUID@$DOMAIN:443?encryption=none&security=tls&sni=$DOMAIN&fp=$REALITY_FP&type=xhttp&path=$XHTTP_PATH&host=$DOMAIN&mode=packet-up#BananaVPN-XHTTP"
  if [ -n "${CF_HOST:-}" ]; then
    nodes+=$'\n'"vless://$OWNER_UUID@$CF_HOST:443?encryption=none&security=tls&sni=$CF_HOST&fp=$REALITY_FP&type=xhttp&path=$XHTTP_PATH&host=$CF_HOST&mode=packet-up#BananaVPN-XHTTP-CDN"
  fi
  printf '%s' "$nodes" | base64 -w0
}
owner_sub >"$WEBROOT/sub/$OWNER_SUB_TOKEN"

echo
say "ГОТОВО. Узел поднят."
cat <<SUMMARY

  Домен:        $DOMAIN  ($SERVER_IP)
  DNS:          A  $DOMAIN  ->  $SERVER_IP   (проверь: dig +short $DOMAIN)
  Порты (ufw):  ${HY_MAIN_PORT}/udp Hysteria · ${HY_TURBO_PORT}/udp turbo · ${REALITY_PORT}/tcp Reality · 443/tcp nginx+XHTTP · 80/tcp ACME
  Личная подписка (владелец):
                https://$DOMAIN/sub/$OWNER_SUB_TOKEN
  Список обхода: https://$DOMAIN/rules/ru-whitelist.json
  .env:         $ENV_FILE

  Дальше - бот выдачи подписок: см. prompts/02-add-bot.md  (bot/install.sh)
SUMMARY
