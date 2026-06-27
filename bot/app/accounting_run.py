import logging

import requests

from app import config as C
from app import db, accounting, provisioner

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bananavpn.accounting_run")


def _dm(bot_token, chat_id, text):
    if not bot_token or not chat_id:
        return
    try:
        requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage",
                      json={"chat_id": chat_id, "text": text}, timeout=8)
    except Exception:
        log.warning("DM to %s failed", chat_id, exc_info=True)


def main():
    env = C.load_env()
    conn = db.connect(env["DB_PATH"]); db.init_schema(conn)
    killed, errors = accounting.collect_once(conn, env)
    if errors:
        log.error("collect errors: %s", errors)
    if killed:

        for token in killed:
            u = db.get_user_by_token(conn, token)
            if u and u["tg_id"]:
                _dm(env["BOT_TOKEN"], u["tg_id"],
                    f"Подписка {C.PROFILE_TITLE} приостановлена (лимит трафика или истек срок). "
                    f"Чтобы продлить, напиши {C.SUPPORT_URL or 'администратору'}.")
        try:
            provisioner.rebuild_xray(conn, env)
            for token in killed:
                provisioner.kick_hysteria(env, token)
        except Exception:
            log.exception("rebuild_xray after enforce failed - погашенные юзеры все еще в Xray, "
                          "повтор на следующем тике")
    print(f"collected; killed={killed}; errors={len(errors)}")


if __name__ == "__main__":
    main()
