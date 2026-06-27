import time
from app import db, devices


def setup(tmp_path, limit):
    conn = db.connect(str(tmp_path / "t.sqlite")); db.init_schema(conn)
    db.create_user(conn, tg_id=1, username="a", token="tok", hy_pass="p",
                   xray_uuid="u", traffic_limit_bytes=None, device_limit=limit,
                   torrent_block=1, expires_at=int(time.time())+86400)
    return conn


def test_extract_hwid_primary():
    hdrs = {"x-hwid": "HW-1", "x-device-os": "iOS", "x-device-model": "iPhone15"}
    hw, os_, model = devices.extract(hdrs, ip="1.2.3.4")
    assert hw == "HW-1" and os_ == "iOS" and model == "iPhone15"


def test_fallback_ua_only_ignores_ip():
    hw1, _, _ = devices.extract({"user-agent": "Happ/1.0"}, ip="1.2.3.4")
    hw2, _, _ = devices.extract({"user-agent": "Happ/1.0"}, ip="9.9.9.9")
    assert hw1.startswith("ua:") and hw1 == hw2


def test_synthetic_failopen_not_counted(tmp_path):
    conn = setup(tmp_path, limit=1)
    hw, _, _ = devices.extract({"user-agent": "X"}, ip="1.1.1.1")
    assert devices.allow(conn, "tok", hw, "", "") is True
    assert devices.allow(conn, "tok", hw, "", "") is True
    assert db.device_count(conn, "tok") == 0


def test_allowed_existing_device_under_limit(tmp_path):
    conn = setup(tmp_path, limit=2)
    assert devices.allow(conn, "tok", "HW-1", "iOS", "iPhone") is True
    assert devices.allow(conn, "tok", "HW-1", "iOS", "iPhone") is True
    assert devices.allow(conn, "tok", "HW-2", "iOS", "iPad") is True


def test_blocked_new_device_over_limit(tmp_path):
    conn = setup(tmp_path, limit=1)
    assert devices.allow(conn, "tok", "HW-1", "", "") is True
    assert devices.allow(conn, "tok", "HW-2", "", "") is False
    assert devices.allow(conn, "tok", "HW-1", "", "") is True
