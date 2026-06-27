from app import config as C
from app import db


def resolve(conn, auth_str):
    if auth_str in C.LEGACY_HY_AUTH:
        return {"ok": True, "id": C.LEGACY_HY_AUTH[auth_str]}
    user = db.get_user_by_hypass(conn, auth_str)
    if user and user["status"] == "active":
        return {"ok": True, "id": user["token"]}
    return {"ok": False}
