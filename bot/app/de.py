import json
import subprocess

from app import config as C
from app import db


def _ssh(host, cmd, content=None):
    args = ["ssh", "-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=10", f"root@{host}", cmd]
    subprocess.run(args, input=(content.encode() if content else None), check=True, timeout=40,
                   capture_output=True)


def _xray_config(users):

    clients = []
    if C.OWNER_UUID:
        clients.append({"id": C.OWNER_UUID, "flow": C.REALITY_FLOW})
    for u in users:
        clients.append({"id": u["xray_uuid"], "flow": C.REALITY_FLOW, "email": u["token"]})

    xclients = []
    if C.OWNER_UUID:
        xclients.append({"id": C.OWNER_UUID})
    for u in users:
        xclients.append({"id": u["xray_uuid"], "email": u["token"]})
    rules = [{"type": "field", "inboundTag": ["api"], "outboundTag": "api"},
             {"type": "field", "ip": ["geoip:private"], "outboundTag": "block"}]
    tok = [u["token"] for u in users if not u["torrent_block"]]
    if tok:
        rules.append({"type": "field", "protocol": ["bittorrent"], "user": tok, "outboundTag": "direct"})
    rules.append({"type": "field", "protocol": ["bittorrent"], "outboundTag": "block"})
    cfg = {
        "log": {"loglevel": "warning"}, "stats": {},
        "api": {"tag": "api", "services": ["StatsService", "HandlerService"]},
        "policy": {"levels": {"0": {"statsUserUplink": True, "statsUserDownlink": True}},
                   "system": {"statsInboundUplink": True, "statsInboundDownlink": True}},
        "inbounds": [
            {"tag": "api", "listen": "127.0.0.1", "port": 10085, "protocol": "dokodemo-door",
             "settings": {"address": "127.0.0.1"}},
            {"tag": "reality-personal", "listen": "0.0.0.0", "port": C.PL_REALITY_PORT, "protocol": "vless",
             "settings": {"clients": clients, "decryption": "none"},
             "streamSettings": {"network": "tcp", "security": "reality",
                "realitySettings": {"show": False, "dest": f"{C.PL_REALITY_SNI}:443", "xver": 0,
                    "serverNames": [C.PL_REALITY_SNI], "privateKey": C.PL_REALITY_PRIV,
                    "shortIds": [C.PL_REALITY_SID], "maxTimeDiff": 60000}},
             "sniffing": {"enabled": True, "destOverride": ["http", "tls", "quic"]}},
            {"tag": "xhttp-personal", "listen": "0.0.0.0", "port": C.PL_XHTTP_PORT, "protocol": "vless",
             "settings": {"clients": xclients, "decryption": "none"},
             "streamSettings": {"network": "xhttp", "security": "tls",
                "tlsSettings": {"serverName": C.PL_HOST, "alpn": ["h2", "http/1.1"],
                    "certificates": [{"certificateFile": "/usr/local/etc/xray/xhttp.crt",
                                      "keyFile": "/usr/local/etc/xray/xhttp.key"}]},
                "xhttpSettings": {"path": C.XHTTP_PATH, "mode": "auto"}},
             "sniffing": {"enabled": True, "destOverride": ["http", "tls", "quic"]}},
            {"tag": "xhttp-personal-alt", "listen": "0.0.0.0", "port": C.PL_XHTTP_ALT_PORT, "protocol": "vless",
             "settings": {"clients": xclients, "decryption": "none"},
             "streamSettings": {"network": "xhttp", "security": "tls",
                "tlsSettings": {"serverName": C.PL_HOST, "alpn": ["h2", "http/1.1"],
                    "certificates": [{"certificateFile": "/usr/local/etc/xray/xhttp.crt",
                                      "keyFile": "/usr/local/etc/xray/xhttp.key"}]},
                "xhttpSettings": {"path": C.XHTTP_PATH, "mode": "auto"}},
             "sniffing": {"enabled": True, "destOverride": ["http", "tls", "quic"]}}],
        "outbounds": [{"tag": "direct", "protocol": "freedom", "settings": {"domainStrategy": "UseIPv4"}},
                      {"tag": "block", "protocol": "blackhole"}],
        "routing": {"domainStrategy": "AsIs", "rules": rules},
        "dns": {"servers": ["1.1.1.1", "8.8.8.8"], "queryStrategy": "UseIPv4"},
    }
    return json.dumps(cfg, ensure_ascii=False, indent=2)


def _userpass_block(users):
    up = {v: k for k, v in C.LEGACY_HY_AUTH.items()}
    for u in users:
        up[u["token"]] = u["hy_pass"]
    return "\n".join("    %s: %s" % (k, v) for k, v in up.items())


def _hy_config(users, listen_port, stats_port, with_obfs):
    up = _userpass_block(users)
    obfs = ("obfs:\n  type: salamander\n  salamander:\n    password: " + C.PL_OBFS_PASSWORD + "\n") if with_obfs else ""
    return (f"listen: :{listen_port}\ntls:\n  cert: /etc/hysteria/cert.pem\n  key: /etc/hysteria/key.pem\n"
            "auth:\n  type: userpass\n  userpass:\n" + up + "\n" + obfs +
            "masquerade:\n  type: proxy\n  proxy:\n    url: \"https://www.samsung.com/\"\n    rewriteHost: true\n"
            f"trafficStats:\n  listen: 127.0.0.1:{stats_port}\n  secret: {C.PL_STATS_SECRET}\n"
            "resolver:\n  type: https\n  https:\n    addr: 1.1.1.1:443\n    timeout: 10s\n    sni: cloudflare-dns.com\n"
            "udpIdleTimeout: 90s\n")


def rebuild_de(conn):
    if not (C.PL_ENABLED and C.PL_SSH_HOST and C.PL_REALITY_PRIV):
        return
    host = C.PL_SSH_HOST
    users = db.active_users(conn)
    _ssh(host, "cat > /usr/local/etc/xray/config.json", _xray_config(users))
    _ssh(host, "cat > /etc/hysteria/config.yaml", _hy_config(users, C.PL_HY_MAIN_PORT, 9443, True))
    _ssh(host, "cat > /etc/hysteria/turbo.yaml", _hy_config(users, C.PL_HY_TURBO_PORT, 9444, False))
    _ssh(host, "xray -test -c /usr/local/etc/xray/config.json >/dev/null && "
               "systemctl restart xray hysteria-server hysteria-server@turbo")
