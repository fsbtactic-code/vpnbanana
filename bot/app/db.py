import sqlite3
import time


def connect(path):
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_schema(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tg_id INTEGER, username TEXT,
      token TEXT UNIQUE, hy_pass TEXT UNIQUE, xray_uuid TEXT,
      traffic_limit_bytes INTEGER,          -- NULL = безлимит
      traffic_used_bytes INTEGER NOT NULL DEFAULT 0,
      device_limit INTEGER NOT NULL DEFAULT 2,
      torrent_block INTEGER NOT NULL DEFAULT 1,
      crypt5 TEXT,
      created_at INTEGER NOT NULL,
      expires_at INTEGER NOT NULL,
      status TEXT NOT NULL DEFAULT 'active'  -- active | expired | disabled
    );
    CREATE TABLE IF NOT EXISTS device_seen (
      token TEXT, hwid TEXT, os TEXT, model TEXT,
      first_seen INTEGER, last_seen INTEGER,
      PRIMARY KEY (token, hwid)
    );
    CREATE TABLE IF NOT EXISTS meter (
      mkey TEXT PRIMARY KEY,                 -- "<source>:<token>", напр. hy-main:abc / xray:abc
      last_total INTEGER NOT NULL DEFAULT 0  -- последнее накопительное значение счетчика источника
    );
    """)
    conn.commit()


def create_user(conn, *, tg_id, username, token, hy_pass, xray_uuid,
                traffic_limit_bytes, device_limit, torrent_block, expires_at,
                crypt5=None):
    now = int(time.time())
    conn.execute(
        "INSERT INTO users (tg_id,username,token,hy_pass,xray_uuid,"
        "traffic_limit_bytes,device_limit,torrent_block,crypt5,created_at,expires_at,status) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?, 'active')",
        (tg_id, username, token, hy_pass, xray_uuid, traffic_limit_bytes,
         device_limit, torrent_block, crypt5, now, expires_at))
    conn.commit()
    return get_user_by_token(conn, token)


def delete_user(conn, token):
    conn.execute("DELETE FROM users WHERE token=?", (token,))
    conn.execute("DELETE FROM device_seen WHERE token=?", (token,))
    conn.commit()


def get_user_by_token(conn, token):
    r = conn.execute("SELECT * FROM users WHERE token=?", (token,)).fetchone()
    return dict(r) if r else None


def get_user_by_tg(conn, tg_id):
    r = conn.execute("SELECT * FROM users WHERE tg_id=? ORDER BY id DESC LIMIT 1",
                     (tg_id,)).fetchone()
    return dict(r) if r else None


def get_user_by_hypass(conn, hy_pass):
    r = conn.execute("SELECT * FROM users WHERE hy_pass=?", (hy_pass,)).fetchone()
    return dict(r) if r else None


def set_crypt5(conn, token, crypt5):
    conn.execute("UPDATE users SET crypt5=? WHERE token=?", (crypt5, token))
    conn.commit()


def add_traffic(conn, token, delta_bytes):
    if delta_bytes <= 0:
        return
    conn.execute("UPDATE users SET traffic_used_bytes=traffic_used_bytes+? WHERE token=?",
                 (int(delta_bytes), token))
    conn.commit()


def set_status(conn, token, status):
    conn.execute("UPDATE users SET status=? WHERE token=?", (status, token))
    conn.commit()


def extend(conn, token, days):
    conn.execute("UPDATE users SET expires_at=expires_at+?, status='active' WHERE token=?",
                 (days * 86400, token))
    conn.commit()


def active_users(conn):
    return [dict(r) for r in conn.execute("SELECT * FROM users WHERE status='active'")]


def all_users(conn):
    return [dict(r) for r in conn.execute("SELECT * FROM users ORDER BY id DESC")]


def users_over_quota(conn):
    rows = conn.execute(
        "SELECT * FROM users WHERE status='active' AND traffic_limit_bytes IS NOT NULL "
        "AND traffic_used_bytes >= traffic_limit_bytes")
    return [dict(r) for r in rows]


def users_expired(conn, now=None):
    now = now or int(time.time())
    rows = conn.execute("SELECT * FROM users WHERE status='active' AND expires_at <= ?", (now,))
    return [dict(r) for r in rows]


def touch_device(conn, token, hwid, os_="", model=""):
    now = int(time.time())
    cur = conn.execute("SELECT 1 FROM device_seen WHERE token=? AND hwid=?", (token, hwid)).fetchone()
    if cur:
        conn.execute("UPDATE device_seen SET last_seen=? WHERE token=? AND hwid=?", (now, token, hwid))
    else:
        conn.execute("INSERT INTO device_seen (token,hwid,os,model,first_seen,last_seen) "
                     "VALUES (?,?,?,?,?,?)", (token, hwid, os_, model, now, now))
    conn.commit()
    return device_count(conn, token)


def delete_device(conn, token, hwid):
    conn.execute("DELETE FROM device_seen WHERE token=? AND hwid=?", (token, hwid))
    conn.commit()


def list_devices(conn, token):
    rows = conn.execute("SELECT hwid, os, model, first_seen, last_seen FROM device_seen "
                        "WHERE token=? ORDER BY last_seen DESC", (token,))
    return [dict(r) for r in rows]


def device_count(conn, token, since=None):
    if since is None:
        r = conn.execute("SELECT COUNT(*) c FROM device_seen WHERE token=?", (token,)).fetchone()
    else:
        r = conn.execute("SELECT COUNT(*) c FROM device_seen WHERE token=? AND last_seen>=?",
                         (token, since)).fetchone()
    return r["c"]


def meter_delta(conn, mkey, now_total):
    now_total = int(now_total)
    r = conn.execute("SELECT last_total FROM meter WHERE mkey=?", (mkey,)).fetchone()
    last = r["last_total"] if r else 0
    delta = now_total if now_total < last else now_total - last
    conn.execute("INSERT INTO meter (mkey,last_total) VALUES (?,?) "
                 "ON CONFLICT(mkey) DO UPDATE SET last_total=excluded.last_total",
                 (mkey, now_total))
    conn.commit()
    return delta
