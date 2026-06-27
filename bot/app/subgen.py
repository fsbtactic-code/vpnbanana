import base64
from urllib.parse import quote

import requests

from app import config as C


def _main_uri(pwd):
    q = f"obfs=salamander&obfs-password={C.OBFS_PASSWORD}&sni={C.DOMAIN}"
    return f"hysteria2://{pwd}@{C.DOMAIN}:{C.HY_MAIN_PORT}?{q}#" + quote("Hysteria · основной")


def _turbo_uri(pwd):
    q = f"sni={C.DOMAIN}"
    return f"hysteria2://{pwd}@{C.DOMAIN}:{C.HY_TURBO_PORT}?{q}#" + quote("Hysteria · турбо")


def _xhttp_uri(uuid):
    p = quote(C.XHTTP_PATH, safe="")
    q = (f"encryption=none&security=tls&sni={C.DOMAIN}&fp={C.REALITY_FP}"
         f"&type=xhttp&path={p}&host={C.DOMAIN}&mode=packet-up")
    return f"vless://{uuid}@{C.DOMAIN}:443?{q}#" + quote("XHTTP · обход блокировок")


def _cf_xhttp_uri(uuid):
    p = quote(C.XHTTP_PATH, safe="")
    q = (f"encryption=none&security=tls&sni={C.CF_HOST}&fp={C.REALITY_FP}"
         f"&type=xhttp&path={p}&host={C.CF_HOST}&mode=packet-up")
    return f"vless://{uuid}@{C.CF_HOST}:443?{q}#" + quote("XHTTP+CDN · обход блокировок")


def _reality_uri(uuid):
    q = (f"encryption=none&flow={C.REALITY_FLOW}&security=reality"
         f"&sni={C.REALITY_SNI}&fp={C.REALITY_FP}&pbk={C.REALITY_PBK}"
         f"&sid={C.REALITY_SID}&type=tcp")
    return f"vless://{uuid}@{C.DOMAIN}:{C.REALITY_PORT}?{q}#" + quote("Reality · резерв")


def _pl_main_uri(user):
    auth = f"{user['token']}:{user['hy_pass']}"
    q = f"obfs=salamander&obfs-password={C.PL_OBFS_PASSWORD}&sni={C.PL_HOST}"
    return f"hysteria2://{auth}@{C.PL_HOST}:{C.PL_HY_MAIN_PORT}?{q}#" + quote("Локация 2 · Hysteria")


def _pl_turbo_uri(user):
    auth = f"{user['token']}:{user['hy_pass']}"
    q = f"sni={C.PL_HOST}"
    return f"hysteria2://{auth}@{C.PL_HOST}:{C.PL_HY_TURBO_PORT}?{q}#" + quote("Локация 2 · Hysteria турбо")


def _pl_xhttp_uri(uuid):
    p = quote(C.XHTTP_PATH, safe="")
    q = (f"encryption=none&security=tls&sni={C.PL_HOST}&fp={C.REALITY_FP}"
         f"&type=xhttp&path={p}&host={C.PL_HOST}&mode=auto")
    return f"vless://{uuid}@{C.PL_HOST}:{C.PL_XHTTP_PORT}?{q}#" + quote("Локация 2 · XHTTP")


def _de_cf_xhttp_uri(uuid):
    p = quote(C.XHTTP_PATH, safe="")
    q = (f"encryption=none&security=tls&sni={C.CF_DE_HOST}&fp={C.REALITY_FP}"
         f"&type=xhttp&path={p}&host={C.CF_DE_HOST}&mode=packet-up")
    return f"vless://{uuid}@{C.CF_DE_HOST}:{C.PL_XHTTP_ALT_PORT}?{q}#" + quote("Локация 2 · XHTTP+CDN")


def _pl_reality_uri(uuid):
    q = (f"encryption=none&flow={C.REALITY_FLOW}&security=reality"
         f"&sni={C.PL_REALITY_SNI}&fp={C.REALITY_FP}&pbk={C.PL_REALITY_PBK}"
         f"&sid={C.PL_REALITY_SID}&type=tcp")
    return f"vless://{uuid}@{C.PL_HOST}:{C.PL_REALITY_PORT}?{q}#" + quote("Локация 2 · Reality")


def node_uris(user):
    nodes = [_main_uri(user["hy_pass"]), _turbo_uri(user["hy_pass"]), _xhttp_uri(user["xray_uuid"])]
    if C.CF_HOST:
        nodes.append(_cf_xhttp_uri(user["xray_uuid"]))
    nodes.append(_reality_uri(user["xray_uuid"]))
    if C.PL_ENABLED and C.PL_HOST and C.PL_REALITY_PBK:
        nodes += [_pl_main_uri(user), _pl_turbo_uri(user), _pl_xhttp_uri(user["xray_uuid"])]
        if C.CF_DE_HOST:
            nodes.append(_de_cf_xhttp_uri(user["xray_uuid"]))
        nodes.append(_pl_reality_uri(user["xray_uuid"]))
    return nodes


def subscription_b64(user):
    body = "\n".join(node_uris(user))
    return base64.b64encode(body.encode()).decode()


def info_node(text):
    uri = "hysteria2://disabled@127.0.0.1:1?#" + quote(text)
    return base64.b64encode(uri.encode()).decode()


def userinfo_header(used, limit_bytes, expire):
    total = limit_bytes if limit_bytes is not None else 0
    return f"upload=0; download={used}; total={total}; expire={expire}"


def sub_url(token):
    return f"https://{C.DOMAIN}/s/{token}"


def landing_url(token):
    return f"https://{C.DOMAIN}/u/{token}"


def crypt5_link(sub_url_value, timeout=8):
    r = requests.post(C.CRYPT5_API, json={"url": sub_url_value}, timeout=timeout)
    r.raise_for_status()
    return r.json()["encrypted_link"]
