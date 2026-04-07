#!/bin/bash
# ============================================
# neurocloud VPN — Full Install Script
# VLESS + REALITY on Debian/Ubuntu
# Usage: sudo bash install.sh
# ============================================

set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()    { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

[ "$EUID" -ne 0 ] && error "Run as root: sudo bash install.sh"

SERVER_IP=$(curl -4 -s ifconfig.me)
PANEL_PORT=24443
VLESS_PORT=443

info "Server IP: $SERVER_IP"

# ---- 1. System update ----
info "Updating system..."
apt update && apt -y upgrade
apt -y install curl wget unzip jq openssl ufw fail2ban ca-certificates sqlite3 socat procps cron
systemctl enable --now fail2ban

# ---- 2. Network tuning ----
info "Tuning network (BBR + buffers)..."
cat >> /etc/sysctl.conf << 'EOF'
net.core.default_qdisc=fq
net.ipv4.tcp_congestion_control=bbr
net.core.rmem_max=67108864
net.core.wmem_max=67108864
net.ipv4.tcp_rmem=4096 87380 67108864
net.ipv4.tcp_wmem=4096 65536 67108864
net.ipv4.tcp_fastopen=3
net.ipv4.tcp_mtu_probing=1
net.ipv4.tcp_tw_reuse=1
net.ipv4.ip_forward=1
EOF
sysctl -p

# ---- 3. Firewall ----
info "Configuring UFW..."
ufw allow 22/tcp
ufw allow 443/tcp
ufw allow 80/tcp
ufw allow "$PANEL_PORT"/tcp
ufw --force enable

# ---- 4. Install 3x-ui ----
info "Installing 3x-ui panel..."
curl -fL https://raw.githubusercontent.com/mhsanaei/3x-ui/master/install.sh | bash

# Standalone Xray (from Xray-install) conflicts with x-ui embedded Xray — disable it
if systemctl is-enabled xray &>/dev/null; then
  systemctl disable --now xray
  warn "Disabled standalone xray.service (x-ui manages its own Xray binary)"
fi

# ---- 5. Install SSL (acme.sh) ----
info "SSL setup..."
curl https://get.acme.sh | sh -s email=admin@example.com
~/.acme.sh/acme.sh --set-default-ca --server letsencrypt

# ---- 6. Watchdog (enable ONLY after VLESS inbound on 443 exists) ----
info "Installing watchdog unit (disabled by default)..."
cat > /etc/systemd/system/xray-watchdog.service << 'WDEOF'
[Unit]
Description=Xray Watchdog (restart x-ui if nothing listens on 443)
After=network.target x-ui.service

[Service]
Type=simple
ExecStart=/bin/bash -c 'while true; do if ! ss -ltnH "( sport = :443 )" 2>/dev/null | grep -q .; then systemctl restart x-ui; echo "$(date): no listener on 443, restarted x-ui" >> /var/log/xray-watchdog.log; fi; sleep 60; done'
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
WDEOF

systemctl daemon-reload
systemctl disable --now xray-watchdog 2>/dev/null || true
warn "Watchdog is OFF. After you add inbound on 443 in the panel: systemctl enable --now xray-watchdog"

# ---- 7. Status tool ----
info "Installing vpn-status tool..."
cat > /usr/local/bin/vpn-status << 'STEOF'
#!/bin/bash
echo "=== VPN Status $(date) ==="
echo ""
echo "--- Services ---"
systemctl is-active x-ui       && echo "x-ui:     RUNNING" || echo "x-ui:     STOPPED"
systemctl is-active xray-watchdog && echo "watchdog: RUNNING" || echo "watchdog: STOPPED"
echo ""
echo "--- Ports ---"
ss -ltnp | grep -E ':443|:24443|:2096' || echo "none"
echo ""
echo "--- Active VPN connections ---"
ss -tnp | grep ':443' | wc -l | xargs echo "Count:"
echo ""
echo "--- Traffic ---"
cat /proc/net/dev | grep -E 'eth0|ens4|ens5' | awk '{print "RX:"int($2/1024/1024)"MB TX:"int($10/1024/1024)"MB"}'
echo ""
echo "--- Watchdog log (last 5) ---"
tail -5 /var/log/xray-watchdog.log 2>/dev/null || echo "No events"
STEOF
chmod +x /usr/local/bin/vpn-status

# ---- 8. Weekly Xray update ----
cat > /etc/cron.weekly/update-xray << 'CREOF'
#!/bin/bash
bash <(curl -Ls https://raw.githubusercontent.com/XTLS/Xray-install/main/install-release.sh) install
systemctl disable --now xray 2>/dev/null || true
systemctl restart x-ui
echo "$(date): Xray updated" >> /var/log/xray-update.log
CREOF
chmod +x /etc/cron.weekly/update-xray

# ---- Done ----
info "=============================="
info " Installation complete!"
info "=============================="
info "Panel port  : $PANEL_PORT"
info "VPN port    : $VLESS_PORT"
info "Server IP   : $SERVER_IP"
info ""
info "Run 'vpn-status' to check system"
info "Run 'x-ui' to manage panel"
info ""
info "Next: panel -> Inbound VLESS REALITY port 443, then:"
info "  systemctl enable --now xray-watchdog"
