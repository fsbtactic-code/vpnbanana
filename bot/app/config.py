import os


DOMAIN = os.environ.get("DOMAIN", "")
SERVER_IP = os.environ.get("SERVER_IP", "")

HY_MAIN_PORT = int(os.environ.get("HY_MAIN_PORT", "443"))
HY_TURBO_PORT = int(os.environ.get("HY_TURBO_PORT", "8444"))
REALITY_PORT = int(os.environ.get("REALITY_PORT", "8443"))


XHTTP_PATH = os.environ.get("XHTTP_PATH", "")
XHTTP_NL_PORT = int(os.environ.get("XHTTP_NL_PORT", "8091"))


CF_HOST = os.environ.get("CF_HOST", "")

CF_DE_HOST = os.environ.get("CF_DE_HOST", "")

PL_XHTTP_ALT_PORT = int(os.environ.get("PL_XHTTP_ALT_PORT", "2053"))

REALITY_PBK = os.environ.get("REALITY_PBK", "")
REALITY_SNI = os.environ.get("REALITY_SNI", "www.samsung.com")
REALITY_SID = os.environ.get("REALITY_SID", "")
REALITY_FLOW = os.environ.get("REALITY_FLOW", "xtls-rprx-vision")

REALITY_FP = os.environ.get("REALITY_FP", "firefox")

SUPPORT_URL = os.environ.get("SUPPORT_URL", "")
PROFILE_TITLE = os.environ.get("PROFILE_TITLE", "BananaVPN")
PROFILE_UPDATE_INTERVAL = os.environ.get("PROFILE_UPDATE_INTERVAL", "12")

CRYPT5_API = os.environ.get("CRYPT5_API", "https://crypto.happ.su/api-v2.php")


OWNER_UUID = os.environ.get("OWNER_UUID", "")


PL_ENABLED = os.environ.get("PL_ENABLED", "") == "1"
PL_HOST = os.environ.get("PL_HOST", "")
PL_REALITY_PORT = int(os.environ.get("PL_REALITY_PORT", "443"))
PL_REALITY_PBK = os.environ.get("PL_REALITY_PBK", "")
PL_REALITY_SNI = os.environ.get("PL_REALITY_SNI", "www.samsung.com")
PL_REALITY_SID = os.environ.get("PL_REALITY_SID", "")

PL_OBFS_PASSWORD = os.environ.get("PL_OBFS_PASSWORD", "")
PL_HY_MAIN_PORT = int(os.environ.get("PL_HY_MAIN_PORT", "443"))
PL_HY_TURBO_PORT = int(os.environ.get("PL_HY_TURBO_PORT", "8444"))
PL_XHTTP_PORT = int(os.environ.get("PL_XHTTP_PORT", "8443"))

PL_REALITY_PRIV = os.environ.get("PL_REALITY_PRIV", "")
PL_STATS_SECRET = os.environ.get("PL_STATS_SECRET", "")
PL_SSH_HOST = os.environ.get("PL_SSH_HOST", "") or PL_HOST


OBFS_PASSWORD = os.environ.get("OBFS_PASSWORD", "")


def _build_legacy():
    m = {}
    if os.environ.get("LEGACY_HY_MAIN"):
        m[os.environ["LEGACY_HY_MAIN"]] = "legacy-personal"
    if os.environ.get("LEGACY_HY_TURBO"):
        m[os.environ["LEGACY_HY_TURBO"]] = "legacy-turbo"
    return m


LEGACY_HY_AUTH = _build_legacy()


def load_env():
    return {
        "BOT_TOKEN": os.environ.get("BOT_TOKEN", ""),
        "ADMIN_ID": int(os.environ.get("ADMIN_ID", "0")),
        "HYSTERIA_STATS_SECRET": os.environ.get("HYSTERIA_STATS_SECRET", ""),
        "HY_MAIN_STATS": os.environ.get("HY_MAIN_STATS", "http://127.0.0.1:9443"),
        "HY_TURBO_STATS": os.environ.get("HY_TURBO_STATS", "http://127.0.0.1:9444"),
        "XRAY_API": os.environ.get("XRAY_API", "127.0.0.1:10085"),
        "DB_PATH": os.environ.get("DB_PATH", "db.sqlite"),
        "XRAY_CONFIG": os.environ.get("XRAY_CONFIG", "/usr/local/etc/xray/config.json"),
    }
