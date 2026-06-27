import hashlib
import re

from app import db

HWID_HEADERS = ("x-hwid", "hwid", "x-device-id")
_CLEAN = re.compile(r'[<>"&\x00-\x1f]')


def _clean(s):
    return _CLEAN.sub("", (s or ""))[:48]


def extract(headers, ip=""):
    h = {k.lower(): v for k, v in headers.items()}
    for name in HWID_HEADERS:
        if h.get(name):
            return _clean(h[name]), _clean(h.get("x-device-os", "")), _clean(h.get("x-device-model", ""))
    ua = h.get("user-agent", "")
    return "ua:" + hashlib.sha1(ua.encode()).hexdigest()[:16], "", ""


def is_synthetic(hwid):
    return hwid.startswith("ua:")


def allow(conn, token, hwid, os_, model):
    user = db.get_user_by_token(conn, token)
    if not user:
        return False
    if is_synthetic(hwid):
        return True
    known = conn.execute("SELECT 1 FROM device_seen WHERE token=? AND hwid=?",
                         (token, hwid)).fetchone() is not None
    if not known and db.device_count(conn, token) >= user["device_limit"]:
        return False
    db.touch_device(conn, token, hwid, os_, model)
    return True
