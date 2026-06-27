import time, base64
from fastapi.testclient import TestClient
from app import db
from app import config as C
import backend.main as bm


def client(tmp_path, monkeypatch):
    conn = db.connect(str(tmp_path / "t.sqlite")); db.init_schema(conn)
    monkeypatch.setattr(C, "DOMAIN", "vpn.example.com")
    monkeypatch.setattr(C, "LEGACY_HY_AUTH", {"TESTLEGACY": "legacy-personal"})
    monkeypatch.setattr(C, "OBFS_PASSWORD", "TESTOBFS")
    monkeypatch.setattr(bm, "CONN", conn)
    monkeypatch.setattr(bm, "ROUTING_DEEPLINK", "happ://routing/onadd/XX")
    monkeypatch.setattr(bm, "hy_online", lambda token: 2)
    db.create_user(conn, tg_id=1, username="a", token="tok", hy_pass="UPWD",
                   xray_uuid="11111111-2222-3333-4444-555555555555",
                   traffic_limit_bytes=None, device_limit=2, torrent_block=1,
                   expires_at=int(time.time())+86400, crypt5="happ://crypt5/Z")
    return TestClient(bm.app), conn


def test_auth_endpoint_user(tmp_path, monkeypatch):
    c, _ = client(tmp_path, monkeypatch)
    r = c.post("/auth", json={"addr": "1.2.3.4:5", "auth": "UPWD", "tx": 0})
    assert r.json() == {"ok": True, "id": "tok"}


def test_auth_endpoint_legacy(tmp_path, monkeypatch):
    c, _ = client(tmp_path, monkeypatch)
    r = c.post("/auth", json={"addr": "1.2.3.4:5", "auth": "TESTLEGACY", "tx": 0})
    assert r.json() == {"ok": True, "id": "legacy-personal"}


def test_auth_robust_bad_body(tmp_path, monkeypatch):
    c, _ = client(tmp_path, monkeypatch)
    r = c.post("/auth", content=b"not-json", headers={"content-type": "application/json"})
    assert r.status_code == 200
    assert r.json() == {"ok": False}


def test_subscription_serves_nodes_and_headers(tmp_path, monkeypatch):
    c, _ = client(tmp_path, monkeypatch)
    r = c.get("/s/tok", headers={"x-hwid": "HW-1", "user-agent": "Happ/1.0"})
    assert r.status_code == 200
    decoded = base64.b64decode(r.text).decode()
    assert "hysteria2://UPWD@vpn.example.com:443" in decoded
    assert r.headers["subscription-userinfo"].startswith("upload=0; download=")
    assert r.headers["routing-enable"] == "true"


def test_subscription_device_limit(tmp_path, monkeypatch):
    c, conn = client(tmp_path, monkeypatch)
    db.set_status(conn, "tok", "active")

    c.get("/s/tok", headers={"x-hwid": "HW-1"})
    c.get("/s/tok", headers={"x-hwid": "HW-2"})
    r = c.get("/s/tok", headers={"x-hwid": "HW-3"})
    decoded = base64.b64decode(r.text).decode()
    assert "vless://" not in decoded
    assert "disabled@127.0.0.1" in decoded


def test_subscription_inactive(tmp_path, monkeypatch):
    c, conn = client(tmp_path, monkeypatch)
    db.set_status(conn, "tok", "expired")
    r = c.get("/s/tok", headers={"x-hwid": "HW-1"})
    decoded = base64.b64decode(r.text).decode()
    assert "vless://" not in decoded
    assert "disabled@127.0.0.1" in decoded


def test_state_endpoint(tmp_path, monkeypatch):
    c, conn = client(tmp_path, monkeypatch)
    db.touch_device(conn, "tok", "HW-1", "iOS", "iPhone15")
    s = c.get("/u/tok/state").json()
    assert s["online"] == 2
    assert s["device_count"] == 1
    assert s["device_limit"] == 2
    assert s["unlimited"] is True
    assert s["limit_label"] == "Безлимит"
    assert s["devices"][0]["os"] == "iOS" and s["devices"][0]["model"] == "iPhone15"


def test_state_pct_for_limited(tmp_path, monkeypatch):
    c, conn = client(tmp_path, monkeypatch)
    db.create_user(conn, tg_id=2, username="b", token="lt", hy_pass="LP",
                   xray_uuid="x", traffic_limit_bytes=100, device_limit=1, torrent_block=1,
                   expires_at=int(time.time())+86400)
    db.add_traffic(conn, "lt", 50)
    s = c.get("/u/lt/state").json()
    assert s["unlimited"] is False
    assert s["pct"] == 50.0
    assert s["limit_label"] == "0 ГБ"


def test_device_delete_endpoint(tmp_path, monkeypatch):
    c, conn = client(tmp_path, monkeypatch)
    db.touch_device(conn, "tok", "HW-1", "iOS", "iPhone")
    db.touch_device(conn, "tok", "HW-2", "iOS", "iPad")
    assert db.device_count(conn, "tok") == 2
    r = c.post("/u/tok/device/delete", json={"hwid": "HW-1"})
    assert r.status_code == 200
    assert r.json()["device_count"] == 1
    assert db.device_count(conn, "tok") == 1


def test_landing_dashboard(tmp_path, monkeypatch):
    c, _ = client(tmp_path, monkeypatch)
    r = c.get("/u/tok")
    assert r.status_code == 200
    assert "Трафик" in r.text and "Мои устройства" in r.text
    assert "happ://crypt5/Z" in r.text
    assert 'var TOKEN="tok"' in r.text
    assert '"device_count"' in r.text


def test_unknown_token_404(tmp_path, monkeypatch):
    c, _ = client(tmp_path, monkeypatch)
    assert c.get("/s/nope").status_code == 404
    assert c.get("/u/nope").status_code == 404
    assert c.get("/u/nope/state").status_code == 404


def test_landing_escapes_script_injection(tmp_path, monkeypatch):
    c, conn = client(tmp_path, monkeypatch)
    db.touch_device(conn, "tok", "HWX", "</script><img src=x>", "m")
    r = c.get("/u/tok")
    assert "</script><img" not in r.text
    assert "\\u003c/script" in r.text


def _make_init(token, uid=7, username="neo", age=0):
    import hashlib, hmac, json, time, urllib.parse
    user = json.dumps({"id": uid, "username": username})
    data = {"auth_date": str(int(time.time()) - age), "query_id": "q", "user": user}
    check = "\n".join(f"{k}={data[k]}" for k in sorted(data))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    h = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urllib.parse.urlencode({**data, "hash": h})


def test_validate_init_data():
    token = "12345:TESTTOKEN"
    init = _make_init(token, uid=7, username="neo")
    assert bm.validate_init_data(init, token) == {"tg_id": 7, "username": "neo"}
    assert bm.validate_init_data(init + "x", token) is None
    assert bm.validate_init_data(init, "wrong:token") is None
    assert bm.validate_init_data("", token) is None
    assert bm.validate_init_data(_make_init(token, age=999999), token) is None


def test_app_shell(tmp_path, monkeypatch):
    c, _ = client(tmp_path, monkeypatch)
    r = c.get("/app")
    assert r.status_code == 200
    assert "telegram-web-app.js" in r.text
    assert "Трафик" in r.text and "Подключение" in r.text


def test_app_state_ok(tmp_path, monkeypatch):
    c, _ = client(tmp_path, monkeypatch)
    monkeypatch.setattr(bm, "validate_init_data", lambda d, t, max_age=None: {"tg_id": 1, "username": "a"})
    s = c.post("/app/state", json={"initData": "x"}).json()
    assert s["online"] == 2
    assert s["landing_url"].endswith("/u/tok")
    assert s["sub_url"].endswith("/s/tok")
    assert s["crypt5"] == "happ://crypt5/Z"


def test_app_state_no_sub(tmp_path, monkeypatch):
    c, _ = client(tmp_path, monkeypatch)
    monkeypatch.setattr(bm, "validate_init_data", lambda d, t, max_age=None: {"tg_id": 999, "username": "x"})
    assert c.post("/app/state", json={"initData": "x"}).json() == {"no_sub": True, "username": "x"}


def test_app_state_forbidden(tmp_path, monkeypatch):
    c, _ = client(tmp_path, monkeypatch)
    monkeypatch.setattr(bm, "validate_init_data", lambda d, t, max_age=None: None)
    assert c.post("/app/state", json={"initData": "bad"}).status_code == 403


def test_app_device_delete(tmp_path, monkeypatch):
    c, conn = client(tmp_path, monkeypatch)
    monkeypatch.setattr(bm, "validate_init_data", lambda d, t, max_age=None: {"tg_id": 1, "username": "a"})
    db.touch_device(conn, "tok", "HW-X", "iOS", "iPhone")
    assert db.device_count(conn, "tok") == 1
    s = c.post("/app/device/delete", json={"initData": "x", "hwid": "HW-X"}).json()
    assert s["device_count"] == 0


def test_admin_state_admin_ok(tmp_path, monkeypatch):
    c, _ = client(tmp_path, monkeypatch)
    monkeypatch.setitem(bm.env, "ADMIN_ID", 777)
    monkeypatch.setattr(bm, "validate_init_data", lambda d, t, max_age=None: {"tg_id": 777, "username": "adm"})
    s = c.post("/admin/state", json={"initData": "x"}).json()
    assert s["count"] >= 1 and "users" in s and "total_gb" in s
    assert any(u["username"] == "a" for u in s["users"])

    assert "hy_pass" not in s["users"][0] and "xray_uuid" not in s["users"][0]


def test_admin_state_nonadmin_403(tmp_path, monkeypatch):
    c, _ = client(tmp_path, monkeypatch)
    monkeypatch.setattr(bm, "validate_init_data", lambda d, t, max_age=None: {"tg_id": 1, "username": "u"})
    assert c.post("/admin/state", json={"initData": "x"}).status_code == 403


def test_admin_state_noauth_403(tmp_path, monkeypatch):
    c, _ = client(tmp_path, monkeypatch)
    monkeypatch.setattr(bm, "validate_init_data", lambda d, t, max_age=None: None)
    assert c.post("/admin/state", json={"initData": "bad"}).status_code == 403


def test_admin_action_disable(tmp_path, monkeypatch):
    c, conn = client(tmp_path, monkeypatch)
    monkeypatch.setitem(bm.env, "ADMIN_ID", 777)
    monkeypatch.setattr(bm, "validate_init_data", lambda d, t, max_age=None: {"tg_id": 777})
    from app import provisioner
    monkeypatch.setattr(provisioner, "rebuild_xray", lambda conn, env: None)
    monkeypatch.setattr(provisioner, "kick_hysteria", lambda env, tok: None)
    r = c.post("/admin/action", json={"initData": "x", "action": "disable", "token": "tok"})
    assert r.status_code == 200
    assert db.get_user_by_token(conn, "tok")["status"] == "disabled"


def test_admin_action_nonadmin_403(tmp_path, monkeypatch):
    c, conn = client(tmp_path, monkeypatch)
    monkeypatch.setattr(bm, "validate_init_data", lambda d, t, max_age=None: {"tg_id": 1})
    r = c.post("/admin/action", json={"initData": "x", "action": "delete", "token": "tok"})
    assert r.status_code == 403
    assert db.get_user_by_token(conn, "tok") is not None


def test_admin_shell(tmp_path, monkeypatch):
    c, _ = client(tmp_path, monkeypatch)
    r = c.get("/admin")
    assert r.status_code == 200 and "telegram-web-app.js" in r.text and "Админка" in r.text
