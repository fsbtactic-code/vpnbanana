import hashlib
import hmac
import json as _json
import logging
import os
import time as _t
from urllib.parse import parse_qsl

import requests
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse
from pydantic import BaseModel

from app import config as C
from app import db, auth_ids, subgen, devices
from backend import landing_tpl, webapp_tpl, admin_tpl

log = logging.getLogger("bananavpn.backend")

env = C.load_env()
CONN = db.connect(env["DB_PATH"]); db.init_schema(CONN)


def _load_routing():
    p = os.path.join(os.path.dirname(__file__), "routing.deeplink")
    try:
        return open(p, encoding="utf-8").read().strip()
    except OSError:
        return ""


ROUTING_DEEPLINK = _load_routing()

if not C.LEGACY_HY_AUTH:
    log.warning("LEGACY_HY_AUTH пуст: legacy-подписки владельца НЕ пройдут http-auth. Проверь .env (LEGACY_HY_MAIN/TURBO).")
if not ROUTING_DEEPLINK:
    log.warning("routing.deeplink отсутствует: RU-обход не включится у подписок.")

app = FastAPI()


@app.post("/auth")
async def auth(req: Request):
    try:
        body = await req.json()
    except Exception:
        body = {}
    a = body.get("auth", "")
    if a in C.LEGACY_HY_AUTH:
        return {"ok": True, "id": C.LEGACY_HY_AUTH[a]}
    try:
        return auth_ids.resolve(CONN, a)
    except Exception:
        log.exception("auth resolve failed for non-legacy")
        return {"ok": False}


def _sub_headers(user):
    h = {
        "profile-title": C.PROFILE_TITLE,
        "profile-update-interval": C.PROFILE_UPDATE_INTERVAL,
        "support-url": C.SUPPORT_URL,
        "subscription-userinfo": subgen.userinfo_header(
            user["traffic_used_bytes"], user["traffic_limit_bytes"], user["expires_at"]),
        "profile-web-page-url": subgen.landing_url(user["token"]),
        "Cache-Control": "no-store",
    }
    if ROUTING_DEEPLINK:
        h["routing"] = ROUTING_DEEPLINK
        h["routing-enable"] = "true"
    return h


@app.get("/s/{token}")
def subscription(token: str, request: Request):
    user = db.get_user_by_token(CONN, token)
    if not user:
        raise HTTPException(status_code=404)
    headers = _sub_headers(user)
    if user["status"] != "active":
        return PlainTextResponse(subgen.info_node("⚠ Подписка неактивна"),
                                 headers=headers)
    ip = request.client.host if request.client else ""
    hwid, os_, model = devices.extract(dict(request.headers), ip)
    if not devices.allow(CONN, token, hwid, os_, model):
        return PlainTextResponse(subgen.info_node("⚠ Лимит устройств - удали лишнее в кабинете"),
                                 headers=headers)
    return PlainTextResponse(subgen.subscription_b64(user), headers=headers)


_online_cache = {"ts": 0, "map": {}}


def _online_snapshot():
    now = int(_t.time())
    if now - _online_cache["ts"] < 8 and _online_cache["map"] is not None:
        return _online_cache["map"]
    _online_cache["ts"] = now
    try:
        r = requests.get(f"{env['HY_MAIN_STATS']}/online",
                         headers={"Authorization": env["HYSTERIA_STATS_SECRET"]}, timeout=2)
        r.raise_for_status()
        _online_cache["map"] = r.json()
    except Exception:
        log.warning("hysteria /online unavailable", exc_info=True)
    return _online_cache["map"] or {}


def hy_online(token):
    return int(_online_snapshot().get(token, 0))


def _human_ago(ts):
    d = int(_t.time()) - int(ts)
    if d < 60:
        return "только что"
    if d < 3600:
        return f"{d // 60} мин назад"
    if d < 86400:
        return f"{d // 3600} ч назад"
    return f"{d // 86400} дн назад"


def _state(user, online):
    used = user["traffic_used_bytes"]
    limit = user["traffic_limit_bytes"]
    if limit is None:
        limit_label, pct = "Безлимит", 0.0
    else:
        limit_label = f"{limit / 1024**3:.0f} ГБ"
        pct = min(100.0, used / limit * 100) if limit else 0.0
    devs = [{"hwid": d["hwid"], "short": d["hwid"][:12],
             "os": d["os"] or "", "model": d["model"] or "",
             "last_seen_h": _human_ago(d["last_seen"])}
            for d in db.list_devices(CONN, user["token"])]
    return {
        "status": user["status"],
        "used_gb": round(used / 1024**3, 2),
        "limit_label": limit_label,
        "unlimited": limit is None,
        "pct": round(pct, 1),
        "days_left": max(0, (user["expires_at"] - int(_t.time())) // 86400),
        "device_limit": user["device_limit"],
        "device_count": len(devs),
        "online": online,
        "devices": devs,
    }


class DelBody(BaseModel):
    hwid: str = ""


@app.get("/u/{token}/state")
def state(token: str):
    user = db.get_user_by_token(CONN, token)
    if not user:
        raise HTTPException(status_code=404)
    return JSONResponse(_state(user, hy_online(token)))


@app.post("/u/{token}/device/delete")
def device_delete(token: str, body: DelBody):
    user = db.get_user_by_token(CONN, token)
    if not user:
        raise HTTPException(status_code=404)
    if body.hwid:
        db.delete_device(CONN, token, body.hwid)
    return JSONResponse(_state(user, hy_online(token)))


@app.get("/u/{token}", response_class=HTMLResponse)
def landing(token: str):
    user = db.get_user_by_token(CONN, token)
    if not user:
        raise HTTPException(status_code=404)
    oneclick = _ensure_crypt5(user)
    return landing_tpl.render(C.PROFILE_TITLE, token, oneclick, ROUTING_DEEPLINK,
                              subgen.sub_url(token), _state(user, hy_online(token)))


def _ensure_crypt5(user):
    oneclick = user["crypt5"] or ""
    if not oneclick:
        try:
            oneclick = subgen.crypt5_link(subgen.sub_url(user["token"]))
            db.set_crypt5(CONN, user["token"], oneclick)
        except Exception:
            log.warning("crypt5 unavailable for %s", user["token"])
            oneclick = ""
    return oneclick


def validate_init_data(init_data, bot_token, max_age=86400):
    if not init_data or not bot_token:
        return None
    try:
        data = dict(parse_qsl(init_data, keep_blank_values=True))
    except Exception:
        return None
    recv = data.pop("hash", None)
    if not recv:
        return None
    check = "\n".join(f"{k}={data[k]}" for k in sorted(data))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calc = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc, recv):
        return None
    try:
        if max_age and (int(_t.time()) - int(data.get("auth_date", "0"))) > max_age:
            return None
    except ValueError:
        return None
    try:
        u = _json.loads(data.get("user", "{}"))
    except Exception:
        u = {}
    if not u.get("id"):
        return None
    return {"tg_id": int(u["id"]), "username": u.get("username", "")}


def _webapp_payload(user, online):
    s = _state(user, online)
    s["landing_url"] = subgen.landing_url(user["token"])
    s["sub_url"] = subgen.sub_url(user["token"])
    s["crypt5"] = _ensure_crypt5(user)
    return s


class AppStateBody(BaseModel):
    initData: str = ""


class AppDelBody(BaseModel):
    initData: str = ""
    hwid: str = ""


@app.get("/app", response_class=HTMLResponse)
def webapp():
    return webapp_tpl.render(C.PROFILE_TITLE)


@app.post("/app/state")
def app_state(body: AppStateBody):
    info = validate_init_data(body.initData, env["BOT_TOKEN"])
    if not info:
        raise HTTPException(status_code=403)
    user = db.get_user_by_tg(CONN, info["tg_id"])
    if not user:
        return JSONResponse({"no_sub": True, "username": info["username"]})
    return JSONResponse(_webapp_payload(user, hy_online(user["token"])))


@app.post("/app/device/delete")
def app_device_delete(body: AppDelBody):
    info = validate_init_data(body.initData, env["BOT_TOKEN"])
    if not info:
        raise HTTPException(status_code=403)
    user = db.get_user_by_tg(CONN, info["tg_id"])
    if not user:
        return JSONResponse({"no_sub": True})
    if body.hwid:
        db.delete_device(CONN, user["token"], body.hwid)
    return JSONResponse(_webapp_payload(user, hy_online(user["token"])))


def _admin_info(init_data):

    info = validate_init_data(init_data, env["BOT_TOKEN"], max_age=3600)
    if not info or info["tg_id"] != env["ADMIN_ID"]:
        return None
    return info


def _admin_state():
    snap = _online_snapshot()
    now = int(_t.time())
    users = db.all_users(CONN)
    rows = []
    for u in users:
        limit = u["traffic_limit_bytes"]
        rows.append({
            "username": u["username"] or "-", "tg_id": u["tg_id"], "token": u["token"],
            "used_gb": round(u["traffic_used_bytes"] / 1024**3, 2),
            "limit_label": "∞" if limit is None else f"{limit / 1024**3:.0f}",
            "online": int(snap.get(u["token"], 0)),
            "devices": db.device_count(CONN, u["token"]), "device_limit": u["device_limit"],
            "days_left": max(0, (u["expires_at"] - now) // 86400),
            "status": u["status"], "torrent_block": u["torrent_block"],
        })
    return {
        "users": rows, "count": len(users),
        "active": sum(1 for u in users if u["status"] == "active"),
        "online_total": sum(int(snap.get(u["token"], 0)) for u in users),
        "total_gb": round(sum(u["traffic_used_bytes"] for u in users) / 1024**3, 2),
    }


class AdminBody(BaseModel):
    initData: str = ""
    action: str = ""
    token: str = ""


@app.get("/admin", response_class=HTMLResponse)
def admin_page():
    return admin_tpl.render(C.PROFILE_TITLE)


@app.post("/admin/state")
def admin_state(body: AdminBody):
    if not _admin_info(body.initData):
        raise HTTPException(status_code=403)
    return JSONResponse(_admin_state())


@app.post("/admin/action")
def admin_action(body: AdminBody):
    if not _admin_info(body.initData):
        raise HTTPException(status_code=403)
    from app import provisioner
    user = db.get_user_by_token(CONN, body.token)
    if not user:
        raise HTTPException(status_code=404)
    a = body.action
    if a == "extend":
        db.extend(CONN, body.token, 30)
        provisioner.rebuild_xray(CONN, env)
    elif a == "disable":
        db.set_status(CONN, body.token, "disabled")
        provisioner.rebuild_xray(CONN, env)
        provisioner.kick_hysteria(env, body.token)
    elif a == "enable":
        db.set_status(CONN, body.token, "active")
        provisioner.rebuild_xray(CONN, env)
    elif a == "delete":
        db.delete_user(CONN, body.token)
        provisioner.rebuild_xray(CONN, env)
        provisioner.kick_hysteria(env, body.token)
    else:
        raise HTTPException(status_code=400)
    return JSONResponse(_admin_state())
