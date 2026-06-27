#!/usr/bin/env bash
# Конфиг-генераторы (heredoc). Источник значений - переменные окружения из .env.

render_hysteria() {
  local listen_port="$1" stats_port="$2" with_obfs="$3" auth_mode="$4"

  printf 'listen: :%s\n' "$listen_port"
  printf 'tls:\n  cert: /etc/hysteria/cert.pem\n  key: /etc/hysteria/key.pem\n'

  if [ "$auth_mode" = http ]; then
    printf 'auth:\n  type: http\n  http:\n    url: http://127.0.0.1:%s/auth\n    insecure: false\n' "$BACKEND_PORT"
  else
    printf 'auth:\n  type: password\n  password: %s\n' "$HY_STATIC_PASSWORD"
  fi

  if [ "$with_obfs" = yes ]; then
    printf 'obfs:\n  type: salamander\n  salamander:\n    password: %s\n' "$OBFS_PASSWORD"
  fi

  printf 'masquerade:\n  type: proxy\n  proxy:\n    url: "%s"\n    rewriteHost: true\n' "$MASQ_URL"
  printf 'trafficStats:\n  listen: 127.0.0.1:%s\n  secret: %s\n' "$stats_port" "$HYSTERIA_STATS_SECRET"
  printf 'resolver:\n  type: https\n  https:\n    addr: 1.1.1.1:443\n    sni: cloudflare-dns.com\n    timeout: 10s\n'
  printf 'quic:\n  initStreamReceiveWindow: 8388608\n  maxStreamReceiveWindow: 8388608\n'
  printf '  initConnReceiveWindow: 20971520\n  maxConnReceiveWindow: 20971520\n'
  printf 'udpIdleTimeout: 90s\n'
}

render_xray() {
  local owner_block="" owner_xblock=""
  if [ -n "${OWNER_UUID:-}" ]; then
    owner_block="{ \"id\": \"$OWNER_UUID\", \"flow\": \"$REALITY_FLOW\" }"
    owner_xblock="{ \"id\": \"$OWNER_UUID\" }"
  fi

  cat <<JSON
{
  "log": { "loglevel": "warning" },
  "stats": {},
  "api": { "tag": "api", "services": ["StatsService", "HandlerService"] },
  "policy": {
    "levels": { "0": { "statsUserUplink": true, "statsUserDownlink": true } },
    "system": { "statsInboundUplink": true, "statsInboundDownlink": true }
  },
  "inbounds": [
    {
      "tag": "api", "listen": "127.0.0.1", "port": 10085, "protocol": "dokodemo-door",
      "settings": { "address": "127.0.0.1" }
    },
    {
      "tag": "reality-personal", "listen": "0.0.0.0", "port": ${REALITY_PORT}, "protocol": "vless",
      "settings": { "clients": [ ${owner_block} ], "decryption": "none" },
      "streamSettings": {
        "network": "tcp", "security": "reality",
        "realitySettings": {
          "show": false, "dest": "${REALITY_SNI}:443", "xver": 0,
          "serverNames": ["${REALITY_SNI}"], "privateKey": "${REALITY_PRIV}",
          "shortIds": ["${REALITY_SID}"], "maxTimeDiff": 60000
        }
      },
      "sniffing": { "enabled": true, "destOverride": ["http", "tls", "quic"] }
    },
    {
      "tag": "xhttp-personal", "listen": "127.0.0.1", "port": ${XHTTP_NL_PORT}, "protocol": "vless",
      "settings": { "clients": [ ${owner_xblock} ], "decryption": "none" },
      "streamSettings": {
        "network": "xhttp",
        "xhttpSettings": { "path": "${XHTTP_PATH}", "mode": "packet-up" }
      },
      "sniffing": { "enabled": true, "destOverride": ["http", "tls", "quic"] }
    }
  ],
  "outbounds": [
    { "tag": "direct", "protocol": "freedom", "settings": { "domainStrategy": "UseIPv4" } },
    { "tag": "block", "protocol": "blackhole" }
  ],
  "routing": {
    "domainStrategy": "AsIs",
    "rules": [
      { "type": "field", "inboundTag": ["api"], "outboundTag": "api" },
      { "type": "field", "ip": ["geoip:private"], "outboundTag": "block" },
      { "type": "field", "protocol": ["bittorrent"], "outboundTag": "block" }
    ]
  },
  "dns": { "servers": ["1.1.1.1", "8.8.8.8"], "queryStrategy": "UseIPv4" }
}
JSON
}

render_nginx() {
  local tmpl="$1"
  sed \
    -e "s|@@DOMAIN@@|${DOMAIN}|g" \
    -e "s|@@XHTTP_PATH@@|${XHTTP_PATH}|g" \
    -e "s|@@XHTTP_NL_PORT@@|${XHTTP_NL_PORT}|g" \
    -e "s|@@BACKEND_PORT@@|${BACKEND_PORT}|g" \
    -e "s|@@WEBROOT@@|${WEBROOT}|g" \
    "$tmpl"
}
