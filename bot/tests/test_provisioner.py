import json, time
import pytest
from app import db, provisioner

BASE = {
  "inbounds": [
    {"tag": "reality-personal", "settings": {"clients": []}},
    {"tag": "reality-guest", "settings": {"clients": [{"id": "keep-me"}]}}
  ],
  "outbounds": [{"tag": "direct"}, {"tag": "block"}],
  "routing": {"rules": [
     {"type": "field", "ip": ["geoip:private"], "outboundTag": "block"},
     {"type": "field", "protocol": ["bittorrent"], "outboundTag": "block"}
  ]}
}


@pytest.fixture(autouse=True)
def _owner(monkeypatch):
    monkeypatch.setattr(provisioner.C, "OWNER_UUID", "OWNER-X")


def setup(tmp_path):
    conn = db.connect(str(tmp_path / "t.sqlite")); db.init_schema(conn)
    cfg = tmp_path / "xray.json"; cfg.write_text(json.dumps(BASE))
    return conn, str(cfg)


def _stub_ok(monkeypatch):
    monkeypatch.setattr(provisioner, "_xray_test", lambda p: None)
    monkeypatch.setattr(provisioner, "_restart_xray", lambda: None)


def test_rebuild_adds_active_clients(tmp_path, monkeypatch):
    conn, cfg = setup(tmp_path); _stub_ok(monkeypatch)
    db.create_user(conn, tg_id=1, username="a", token="t1", hy_pass="p1",
                   xray_uuid="UU-1", traffic_limit_bytes=None, device_limit=1,
                   torrent_block=1, expires_at=int(time.time())+86400)
    db.create_user(conn, tg_id=2, username="b", token="t2", hy_pass="p2",
                   xray_uuid="UU-2", traffic_limit_bytes=None, device_limit=1,
                   torrent_block=0, expires_at=int(time.time())+86400)
    provisioner.rebuild_xray(conn, {"XRAY_CONFIG": cfg})
    data = json.loads(open(cfg).read())
    personal = next(i for i in data["inbounds"] if i["tag"] == "reality-personal")
    ids = {c["id"] for c in personal["settings"]["clients"]}
    assert ids == {"OWNER-X", "UU-1", "UU-2"}
    emails = {c.get("email") for c in personal["settings"]["clients"]}
    assert "t1" in emails and "t2" in emails
    guest = next(i for i in data["inbounds"] if i["tag"] == "reality-guest")
    assert guest["settings"]["clients"] == [{"id": "keep-me"}]
    allow = [r for r in data["routing"]["rules"]
             if r.get("protocol") == ["bittorrent"] and "user" in r]
    assert allow and allow[0]["user"] == ["t2"]


def test_rebuild_syncs_xhttp_clients(tmp_path, monkeypatch):
    conn, cfg = setup(tmp_path); _stub_ok(monkeypatch)
    data = json.loads(open(cfg).read())
    data["inbounds"].append({"tag": "xhttp-personal", "settings": {"clients": []}})
    open(cfg, "w").write(json.dumps(data))
    db.create_user(conn, tg_id=1, username="a", token="t1", hy_pass="p1",
                   xray_uuid="UU-1", traffic_limit_bytes=None, device_limit=1,
                   torrent_block=1, expires_at=int(time.time())+86400)
    provisioner.rebuild_xray(conn, {"XRAY_CONFIG": cfg})
    data = json.loads(open(cfg).read())
    xh = next(i for i in data["inbounds"] if i["tag"] == "xhttp-personal")
    ids = {c["id"] for c in xh["settings"]["clients"]}
    assert ids == {"OWNER-X", "UU-1"}
    assert all("flow" not in c for c in xh["settings"]["clients"])
    assert any(c.get("email") == "t1" for c in xh["settings"]["clients"])


def test_rebuild_drops_disabled(tmp_path, monkeypatch):
    conn, cfg = setup(tmp_path); _stub_ok(monkeypatch)
    db.create_user(conn, tg_id=1, username="a", token="t1", hy_pass="p1",
                   xray_uuid="UU-1", traffic_limit_bytes=None, device_limit=1,
                   torrent_block=1, expires_at=int(time.time())+86400)
    db.set_status(conn, "t1", "expired")
    provisioner.rebuild_xray(conn, {"XRAY_CONFIG": cfg})
    data = json.loads(open(cfg).read())
    personal = next(i for i in data["inbounds"] if i["tag"] == "reality-personal")
    ids = {c["id"] for c in personal["settings"]["clients"]}
    assert ids == {"OWNER-X"}


def test_invalid_config_leaves_live_untouched(tmp_path, monkeypatch):
    conn, cfg = setup(tmp_path)
    monkeypatch.setattr(provisioner, "_restart_xray", lambda: None)

    def boom(p):
        raise RuntimeError("invalid config")
    monkeypatch.setattr(provisioner, "_xray_test", boom)

    before = open(cfg).read()
    with pytest.raises(RuntimeError):
        provisioner.new_user(conn, {"XRAY_CONFIG": cfg}, tg_id=1, username="a",
                             traffic_limit_bytes=None, device_limit=1, torrent_block=1)
    assert db.all_users(conn) == []
    assert open(cfg).read() == before
