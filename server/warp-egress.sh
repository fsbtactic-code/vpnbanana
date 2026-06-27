#!/usr/bin/env bash
set -euo pipefail
# Опционально: гео-чувствительные AI-сервисы и весь диапазон Google через Cloudflare WARP.

XRAY_CONFIG="${XRAY_CONFIG:-/usr/local/etc/xray/config.json}"
say() { printf '\033[1;33m==>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }
[ "$(id -u)" = 0 ] || die "запусти от root"

AI_DOMAINS='["domain:google.com","domain:googleapis.com","domain:gstatic.com","domain:googleusercontent.com","domain:googlevideo.com","domain:ggpht.com","domain:labs.google","domain:notebooklm.google","domain:google.dev","domain:openai.com","domain:chatgpt.com","domain:oaistatic.com","domain:oaiusercontent.com","domain:elevenlabs.io","domain:x.ai","domain:grok.com","domain:claude.ai"]'

say "wireguard + wgcf"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq wireguard-tools curl jq python3 >/dev/null
if ! command -v wgcf >/dev/null; then
  ARCH="$(dpkg --print-architecture)"; case "$ARCH" in amd64) A=amd64;; arm64) A=arm64;; *) A=amd64;; esac
  curl -fsSL -o /usr/local/bin/wgcf "$(curl -fsSL https://api.github.com/repos/ViRb3/wgcf/releases/latest | jq -r ".assets[] | select(.name|test(\"linux_${A}$\")) | .browser_download_url")"
  chmod +x /usr/local/bin/wgcf
fi

if [ ! -f /etc/wireguard/warp.conf ]; then
  cd /root
  [ -f wgcf-account.toml ] || wgcf register --accept-tos
  wgcf generate
  sed -e 's/^DNS = .*//' \
      -e '/\[Interface\]/a Table = off' \
      -e '/\[Interface\]/a MTU = 1280' \
      -e '/\[Peer\]/a PersistentKeepalive = 25' \
      wgcf-profile.conf >/etc/wireguard/warp.conf
  chmod 600 /etc/wireguard/warp.conf
fi

systemctl enable --now wg-quick@warp || systemctl restart wg-quick@warp

say "Google IP-диапазоны (ловит QUIC/IP-only мимо доменов)"
GOOG="$(curl -fsSL https://www.gstatic.com/ipranges/goog.json | jq -r '[.prefixes[].ipv4Prefix | select(. != null)]')"

say "патчу xray (warp-out outbound + правила AI/Google -> warp)"
TMP="$(dirname "$XRAY_CONFIG")/_warp_candidate.json"
python3 - "$XRAY_CONFIG" "$TMP" "$AI_DOMAINS" "$GOOG" <<'PY'
import json, sys
path, tmp, ai, goog = sys.argv[1], sys.argv[2], json.loads(sys.argv[3]), json.loads(sys.argv[4])
cfg = json.load(open(path, encoding="utf-8"))
outs = cfg.setdefault("outbounds", [])
if not any(o.get("tag") == "warp-out" for o in outs):
    outs.append({"tag": "warp-out", "protocol": "freedom",
                 "settings": {"domainStrategy": "UseIPv4"},
                 "streamSettings": {"sockopt": {"interface": "warp"}}})
rules = cfg.setdefault("routing", {}).setdefault("rules", [])
rules = [r for r in rules if r.get("outboundTag") != "warp-out"]
insert = next((i for i, r in enumerate(rules) if r.get("outboundTag") == "block"), 0)
rules[insert:insert] = [
    {"type": "field", "ip": goog, "outboundTag": "warp-out"},
    {"type": "field", "domain": ai, "outboundTag": "warp-out"},
]
cfg["routing"]["rules"] = rules
json.dump(cfg, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
PY
xray -test -c "$TMP" >/dev/null || die "новый xray-конфиг невалиден, live не тронут"
mv "$TMP" "$XRAY_CONFIG"
systemctl restart xray

say "health-таймер warp (keepalive + авто-рестарт)"
cat >/usr/local/sbin/warp-health.sh <<'SH'
#!/usr/bin/env bash
if ! curl -fsS --interface warp --max-time 5 https://www.cloudflare.com/cdn-cgi/trace 2>/dev/null | grep -q 'warp=on'; then
  systemctl restart wg-quick@warp
fi
SH
chmod +x /usr/local/sbin/warp-health.sh
cat >/etc/systemd/system/warp-health.service <<'UNIT'
[Unit]
Description=WARP health check
[Service]
Type=oneshot
ExecStart=/usr/local/sbin/warp-health.sh
UNIT
cat >/etc/systemd/system/warp-health.timer <<'UNIT'
[Unit]
Description=WARP health check timer
[Timer]
OnBootSec=1min
OnUnitActiveSec=45s
[Install]
WantedBy=timers.target
UNIT
systemctl daemon-reload
systemctl enable --now warp-health.timer

say "ГОТОВО. AI/Google идут через WARP. Проверка: curl --interface warp https://www.cloudflare.com/cdn-cgi/trace"
