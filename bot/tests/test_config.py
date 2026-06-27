import importlib
from app import config


def test_defaults_are_env_driven():
    assert config.DOMAIN == ""
    assert config.HY_MAIN_PORT == 443
    assert config.HY_TURBO_PORT == 8444
    assert config.REALITY_PORT == 8443
    assert config.REALITY_SNI == "www.samsung.com"
    assert config.PROFILE_TITLE == "BananaVPN"


def test_secrets_from_env(monkeypatch):
    monkeypatch.setenv("OBFS_PASSWORD", "obfsX")
    monkeypatch.setenv("LEGACY_HY_MAIN", "MAINPW")
    monkeypatch.setenv("LEGACY_HY_TURBO", "TURBOPW")
    importlib.reload(config)
    assert config.OBFS_PASSWORD == "obfsX"
    assert config.LEGACY_HY_AUTH == {"MAINPW": "legacy-personal", "TURBOPW": "legacy-turbo"}
    monkeypatch.undo()
    importlib.reload(config)


def test_runtime_env_loaded(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "abc")
    monkeypatch.setenv("ADMIN_ID", "999999")
    e = config.load_env()
    assert e["BOT_TOKEN"] == "abc"
    assert e["ADMIN_ID"] == 999999


def test_admin_id_defaults_to_zero():
    e = config.load_env()
    assert e["ADMIN_ID"] == 0
