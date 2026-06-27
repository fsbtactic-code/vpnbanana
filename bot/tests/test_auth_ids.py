import time
import pytest
from app import db, auth_ids


@pytest.fixture(autouse=True)
def _legacy(monkeypatch):
    monkeypatch.setattr(auth_ids.C, "LEGACY_HY_AUTH",
                        {"TESTLEGACY": "legacy-personal"})


def setup(tmp_path):
    conn = db.connect(str(tmp_path / "t.sqlite")); db.init_schema(conn)
    return conn


def test_legacy_password_ok(tmp_path):
    conn = setup(tmp_path)
    res = auth_ids.resolve(conn, "TESTLEGACY")
    assert res == {"ok": True, "id": "legacy-personal"}


def test_user_password_ok(tmp_path):
    conn = setup(tmp_path)
    db.create_user(conn, tg_id=1, username="a", token="tok", hy_pass="UPWD",
                   xray_uuid="u", traffic_limit_bytes=None, device_limit=1,
                   torrent_block=1, expires_at=int(time.time())+86400)
    assert auth_ids.resolve(conn, "UPWD") == {"ok": True, "id": "tok"}


def test_disabled_user_rejected(tmp_path):
    conn = setup(tmp_path)
    db.create_user(conn, tg_id=1, username="a", token="tok", hy_pass="UPWD",
                   xray_uuid="u", traffic_limit_bytes=None, device_limit=1,
                   torrent_block=1, expires_at=int(time.time())+86400)
    db.set_status(conn, "tok", "expired")
    assert auth_ids.resolve(conn, "UPWD") == {"ok": False}


def test_unknown_rejected(tmp_path):
    conn = setup(tmp_path)
    assert auth_ids.resolve(conn, "nope") == {"ok": False}
