import time
from app import db, accounting


def setup(tmp_path):
    conn = db.connect(str(tmp_path / "t.sqlite")); db.init_schema(conn)
    db.create_user(conn, tg_id=1, username="a", token="tok", hy_pass="p",
                   xray_uuid="u", traffic_limit_bytes=100, device_limit=1,
                   torrent_block=1, expires_at=int(time.time())+86400)
    return conn


def test_parse_hysteria_traffic():
    data = {"tok": {"tx": 10, "rx": 20}, "legacy-personal": {"tx": 1, "rx": 2}}
    assert accounting.parse_hy_traffic(data) == {"tok": 30, "legacy-personal": 3}


def test_parse_xray_stats():
    payload = {"stat": [
        {"name": "user>>>tok>>>traffic>>>uplink", "value": "40"},
        {"name": "user>>>tok>>>traffic>>>downlink", "value": "60"},
        {"name": "user>>>other>>>traffic>>>uplink", "value": "5"},
    ]}
    assert accounting.parse_xray_stats(payload) == {"tok": 100, "other": 5}


def test_meter_delta_cumulative(tmp_path):
    conn = db.connect(str(tmp_path / "t.sqlite")); db.init_schema(conn)
    assert db.meter_delta(conn, "hy:tok", 70) == 70
    assert db.meter_delta(conn, "hy:tok", 110) == 40
    assert db.meter_delta(conn, "hy:tok", 30) == 30


def test_apply_totals_and_quota(tmp_path):
    conn = setup(tmp_path)
    accounting.apply_totals(conn, "hy-main", {"tok": 70})
    accounting.apply_totals(conn, "hy-main", {"tok": 110})
    assert db.get_user_by_token(conn, "tok")["traffic_used_bytes"] == 110
    killed = accounting.enforce(conn)
    assert "tok" in killed
    assert db.get_user_by_token(conn, "tok")["status"] == "expired"
