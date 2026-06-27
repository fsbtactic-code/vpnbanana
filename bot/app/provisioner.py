import json
import logging
import os
import secrets
import shutil
import subprocess
import time
import uuid

import requests

from app import config as C
from app import db

log = logging.getLogger("vpnbanana.provisioner")


def _xray_test(path):
    subprocess.run(["xray", "-test", "-c", path], check=True, capture_output=True, text=True)


def _restart_xray():
    subprocess.run(["systemctl", "restart", "xray"], check=True)


def rebuild_xray(conn, env):
    path = env["XRAY_CONFIG"]
    data = json.loads(open(path, encoding="utf-8").read())

    actives = db.active_users(conn)

    clients = []
    if C.OWNER_UUID:
        clients.append({"id": C.OWNER_UUID, "flow": C.REALITY_FLOW})
    for u in actives:
        clients.append({"id": u["xray_uuid"], "flow": C.REALITY_FLOW, "email": u["token"]})

    xclients = []
    if C.OWNER_UUID:
        xclients.append({"id": C.OWNER_UUID})
    for u in actives:
        xclients.append({"id": u["xray_uuid"], "email": u["token"]})
    for inb in data["inbounds"]:
        if inb.get("tag") == "reality-personal":
            inb["settings"]["clients"] = clients
        elif inb.get("tag") == "xhttp-personal":
            inb["settings"]["clients"] = xclients


    torrent_ok = [u["token"] for u in actives if not u["torrent_block"]]
    rules = data["routing"]["rules"]
    rules = [r for r in rules if not (r.get("protocol") == ["bittorrent"] and "user" in r)]
    if torrent_ok:
        idx = next((i for i, r in enumerate(rules)
                    if r.get("protocol") == ["bittorrent"] and "user" not in r), len(rules))
        rules.insert(idx, {"type": "field", "protocol": ["bittorrent"],
                           "user": torrent_ok, "outboundTag": "direct"})
    data["routing"]["rules"] = rules


    tmp = os.path.join(os.path.dirname(os.path.abspath(path)), "_bvpn_candidate.json")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    try:
        _xray_test(tmp)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    shutil.copy(path, path + ".bak")
    os.replace(tmp, path)
    _restart_xray()
    try:
        from app import de
        de.rebuild_de(conn)
    except Exception:
        log.exception("rebuild_de (вторая локация) failed - основной веб-сервер не задет")


def kick_hysteria(env, token):
    url = env.get("HY_MAIN_STATS")
    if not url:
        return
    try:
        r = requests.post(f"{url}/kick", json=[token],
                          headers={"Authorization": env.get("HYSTERIA_STATS_SECRET", "")},
                          timeout=4)
        if r.status_code >= 300:
            log.warning("kick %s -> HTTP %s", token, r.status_code)
    except Exception:
        log.warning("kick %s failed", token, exc_info=True)


def new_user(conn, env, *, tg_id, username, traffic_limit_bytes, device_limit,
             torrent_block, days=30):
    token = secrets.token_hex(16)
    hy_pass = secrets.token_urlsafe(18)
    xuuid = str(uuid.uuid4())
    expires = int(time.time()) + days * 86400
    db.create_user(conn, tg_id=tg_id, username=username, token=token, hy_pass=hy_pass,
                   xray_uuid=xuuid, traffic_limit_bytes=traffic_limit_bytes,
                   device_limit=device_limit, torrent_block=torrent_block, expires_at=expires)
    try:
        rebuild_xray(conn, env)
    except Exception:
        db.delete_user(conn, token)
        raise
    return token
