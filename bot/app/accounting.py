import json
import logging
import subprocess

import requests

from app import config as C
from app import db

log = logging.getLogger("bananavpn.accounting")


def parse_hy_traffic(data):
    return {k: int(v.get("tx", 0)) + int(v.get("rx", 0)) for k, v in data.items()}


def parse_xray_stats(payload):
    out = {}
    for s in payload.get("stat", []):
        parts = s["name"].split(">>>")
        if len(parts) == 4 and parts[0] == "user" and parts[2] == "traffic":
            out[parts[1]] = out.get(parts[1], 0) + int(s.get("value", 0))
    return out


def fetch_hy_total(url, secret):

    r = requests.get(f"{url}/traffic", headers={"Authorization": secret}, timeout=5)
    r.raise_for_status()
    return parse_hy_traffic(r.json())


def fetch_xray_total(api_addr):

    p = subprocess.run(["xray", "api", "statsquery", f"--server={api_addr}", "-pattern", "user>>>"],
                       capture_output=True, text=True, timeout=8)
    return parse_xray_stats(json.loads(p.stdout or "{}"))


def _ssh(host, cmd):
    r = subprocess.run(["ssh", "-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=10",
                        f"root@{host}", cmd], capture_output=True, text=True, timeout=25)
    return r.stdout


def fetch_hy_total_ssh(host, port, secret):
    out = _ssh(host, f"curl -s --max-time 5 -H 'Authorization: {secret}' http://127.0.0.1:{port}/traffic")
    return parse_hy_traffic(json.loads(out or "{}"))


def fetch_xray_total_ssh(host, api_addr):
    out = _ssh(host, f"xray api statsquery --server={api_addr} -pattern user>>>")
    return parse_xray_stats(json.loads(out or "{}"))


def apply_totals(conn, source, id_to_total):
    for token, total in id_to_total.items():
        delta = db.meter_delta(conn, f"{source}:{token}", total)
        if delta > 0:
            db.add_traffic(conn, token, delta)


def enforce(conn):
    killed = []
    for u in db.users_over_quota(conn) + db.users_expired(conn):
        if u["token"] not in killed:
            db.set_status(conn, u["token"], "expired")
            killed.append(u["token"])
    return killed


def collect_once(conn, env):
    errors = []
    try:
        apply_totals(conn, "hy-main", fetch_hy_total(env["HY_MAIN_STATS"], env["HYSTERIA_STATS_SECRET"]))
    except Exception as e:
        log.exception("hysteria main stats failed")
        errors.append(f"hy-main: {e}")
    try:
        apply_totals(conn, "xray", fetch_xray_total(env["XRAY_API"]))
    except Exception as e:
        log.exception("xray stats failed")
        errors.append(f"xray: {e}")

    if C.PL_ENABLED and C.PL_SSH_HOST:
        for port, src in ((9443, "de-hy-main"), (9444, "de-hy-turbo")):
            try:
                apply_totals(conn, src, fetch_hy_total_ssh(C.PL_SSH_HOST, port, C.PL_STATS_SECRET))
            except Exception as e:
                log.exception("de hysteria stats failed")
                errors.append(f"{src}: {e}")
        try:
            apply_totals(conn, "de-xray", fetch_xray_total_ssh(C.PL_SSH_HOST, "127.0.0.1:10085"))
        except Exception as e:
            log.exception("de xray stats failed")
            errors.append(f"de-xray: {e}")
    return enforce(conn), errors
