import time
from app import db


def make(tmp_path):
    conn = db.connect(str(tmp_path / "t.sqlite"))
    db.init_schema(conn)
    return conn


def test_create_and_get_user(tmp_path):
    conn = make(tmp_path)
    db.create_user(conn, tg_id=111, username="vasya", token="tok1",
                   hy_pass="p1", xray_uuid="uuid1",
                   traffic_limit_bytes=100*1024**3, device_limit=2,
                   torrent_block=1, expires_at=int(time.time())+30*86400)
    got = db.get_user_by_token(conn, "tok1")
    assert got["username"] == "vasya"
    assert got["status"] == "active"
    assert got["traffic_used_bytes"] == 0
    assert db.get_user_by_tg(conn, 111)["token"] == "tok1"


def test_add_traffic_and_quota(tmp_path):
    conn = make(tmp_path)
    db.create_user(conn, tg_id=1, username="a", token="t", hy_pass="p",
                   xray_uuid="u", traffic_limit_bytes=10, device_limit=1,
                   torrent_block=1, expires_at=int(time.time())+86400)
    db.add_traffic(conn, "t", 7)
    db.add_traffic(conn, "t", 5)
    assert db.get_user_by_token(conn, "t")["traffic_used_bytes"] == 12
    over = db.users_over_quota(conn)
    assert any(x["token"] == "t" for x in over)


def test_device_seen(tmp_path):
    conn = make(tmp_path)
    db.create_user(conn, tg_id=1, username="a", token="t", hy_pass="p",
                   xray_uuid="u", traffic_limit_bytes=None, device_limit=2,
                   torrent_block=1, expires_at=int(time.time())+86400)
    assert db.touch_device(conn, "t", "hw1", "iOS", "iPhone") == 1
    assert db.touch_device(conn, "t", "hw1", "iOS", "iPhone") == 1
    assert db.touch_device(conn, "t", "hw2", "iOS", "iPad") == 2
    assert db.device_count(conn, "t") == 2


def test_device_count_window(tmp_path):
    conn = make(tmp_path)
    db.create_user(conn, tg_id=1, username="a", token="t", hy_pass="p",
                   xray_uuid="u", traffic_limit_bytes=None, device_limit=2,
                   torrent_block=1, expires_at=int(time.time())+86400)
    db.touch_device(conn, "t", "hw1", "", "")
    future = int(time.time()) + 1000
    assert db.device_count(conn, "t", since=future) == 0
    assert db.device_count(conn, "t", since=0) == 1


def test_set_status_and_active_users(tmp_path):
    conn = make(tmp_path)
    db.create_user(conn, tg_id=1, username="a", token="t", hy_pass="p",
                   xray_uuid="u", traffic_limit_bytes=None, device_limit=1,
                   torrent_block=0, expires_at=int(time.time())+86400)
    assert len(db.active_users(conn)) == 1
    db.set_status(conn, "t", "disabled")
    assert len(db.active_users(conn)) == 0


def test_list_and_delete_device(tmp_path):
    conn = make(tmp_path)
    db.create_user(conn, tg_id=1, username="a", token="t", hy_pass="p",
                   xray_uuid="u", traffic_limit_bytes=None, device_limit=2,
                   torrent_block=1, expires_at=int(time.time())+86400)
    db.touch_device(conn, "t", "hw1", "iOS", "iPhone")
    db.touch_device(conn, "t", "hw2", "Android", "Pixel")
    lst = db.list_devices(conn, "t")
    assert {d["hwid"] for d in lst} == {"hw1", "hw2"}
    assert lst[0]["os"] in ("iOS", "Android")
    db.delete_device(conn, "t", "hw1")
    assert db.device_count(conn, "t") == 1
    assert [d["hwid"] for d in db.list_devices(conn, "t")] == ["hw2"]


def test_delete_user(tmp_path):
    conn = make(tmp_path)
    db.create_user(conn, tg_id=1, username="a", token="t", hy_pass="p",
                   xray_uuid="u", traffic_limit_bytes=None, device_limit=1,
                   torrent_block=1, expires_at=int(time.time())+86400)
    db.touch_device(conn, "t", "hw", "", "")
    db.delete_user(conn, "t")
    assert db.get_user_by_token(conn, "t") is None
    assert db.device_count(conn, "t") == 0
