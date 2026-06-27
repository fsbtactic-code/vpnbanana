#!/usr/bin/env bash
set -euo pipefail
# Запускается НА втором VPS (другая страна). Ставит базу для второй локации и печатает
# блок PL_* для вставки в .env ОСНОВНОГО сервера. Дальше основной сервер сам пушит
# пер-юзер конфиги по SSH (нужен его публичный ключ в authorized_keys этого бокса).

say() { printf '\033[1;33m==>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }
[ "$(id -u)" = 0 ] || die "запусти от root"

PL_HOST="${PL_HOST:-${1:-}}"
[ -n "$PL_HOST" ] || die "укажи домен локации: PL_HOST=de.example.com $0  (DNS A на этот бокс)"

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq curl openssl certbot ufw >/dev/null
command -v hysteria >/dev/null || bash <(curl -fsSL https://get.hy2.sh/) >/dev/null
command -v xray >/dev/null || bash -c "$(curl -fsSL https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install >/dev/null

say "TLS ($PL_HOST)"
ufw allow 22/tcp >/dev/null 2>&1 || true
ufw allow 80/tcp >/dev/null 2>&1 || true
[ -f "/etc/letsencrypt/live/$PL_HOST/fullchain.pem" ] || \
  certbot certonly --standalone -d "$PL_HOST" --non-interactive --agree-tos --register-unsafely-without-email
cp "/etc/letsencrypt/live/$PL_HOST/fullchain.pem" /etc/hysteria/cert.pem
cp "/etc/letsencrypt/live/$PL_HOST/privkey.pem"   /etc/hysteria/key.pem
chown hysteria:hysteria /etc/hysteria/cert.pem /etc/hysteria/key.pem 2>/dev/null || true
cp "/etc/letsencrypt/live/$PL_HOST/fullchain.pem" /usr/local/etc/xray/xhttp.crt
cp "/etc/letsencrypt/live/$PL_HOST/privkey.pem"   /usr/local/etc/xray/xhttp.key
chown nobody:nogroup /usr/local/etc/xray/xhttp.key 2>/dev/null || true
chmod 600 /usr/local/etc/xray/xhttp.key

say "секреты локации"
KP="$(xray x25519)"
PL_REALITY_PRIV="$(printf '%s\n' "$KP" | awk '/Private/{print $NF}')"
PL_REALITY_PBK="$(printf '%s\n' "$KP" | awk '/Public/{print $NF}')"
PL_REALITY_SID="$(openssl rand -hex 8)"
PL_OBFS_PASSWORD="$(openssl rand -base64 18 | tr -d '/+=')"
PL_STATS_SECRET="$(openssl rand -hex 16)"

say "firewall"
for p in 443/tcp 443/udp 8444/udp 8443/tcp 2053/tcp; do ufw allow "$p" >/dev/null 2>&1 || true; done
ufw --force enable >/dev/null 2>&1 || true

cat <<ENV

  Локация готова. Вставь в .env ОСНОВНОГО сервера и перезапусти бот:

PL_ENABLED=1
PL_HOST=$PL_HOST
PL_SSH_HOST=$PL_HOST
PL_REALITY_PRIV=$PL_REALITY_PRIV
PL_REALITY_PBK=$PL_REALITY_PBK
PL_REALITY_SID=$PL_REALITY_SID
PL_OBFS_PASSWORD=$PL_OBFS_PASSWORD
PL_STATS_SECRET=$PL_STATS_SECRET

  И добавь публичный SSH-ключ основного сервера в /root/.ssh/authorized_keys этого бокса
  (основной пушит конфиги по ssh root@$PL_HOST). Проверка с основного: ssh root@$PL_HOST 'echo ok'.
ENV
