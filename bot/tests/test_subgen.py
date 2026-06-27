import base64
import pytest
from app import subgen

USER = {"token": "tok", "hy_pass": "PWD123", "xray_uuid": "11111111-2222-3333-4444-555555555555"}


@pytest.fixture(autouse=True)
def _cfg(monkeypatch):
    monkeypatch.setattr(subgen.C, "DOMAIN", "vpn.example.com")
    monkeypatch.setattr(subgen.C, "OBFS_PASSWORD", "TESTOBFS")
    monkeypatch.setattr(subgen.C, "XHTTP_PATH", "/testpath")
    monkeypatch.setattr(subgen.C, "REALITY_PBK", "TESTPBK")
    monkeypatch.setattr(subgen.C, "REALITY_SID", "testsid")
    monkeypatch.setattr(subgen.C, "CF_HOST", "")
    monkeypatch.setattr(subgen.C, "CF_DE_HOST", "")


def test_node_uris(monkeypatch):
    monkeypatch.setattr(subgen.C, "PL_ENABLED", False)
    uris = subgen.node_uris(USER)
    assert len(uris) == 4
    assert uris[0].startswith("hysteria2://PWD123@vpn.example.com:443?")
    assert "obfs=salamander" in uris[0] and "obfs-password=TESTOBFS" in uris[0]
    assert uris[1].startswith("hysteria2://PWD123@vpn.example.com:8444?")
    assert "obfs" not in uris[1]
    assert uris[2].startswith("vless://11111111-2222-3333-4444-555555555555@vpn.example.com:443?")
    assert "type=xhttp" in uris[2] and "security=tls" in uris[2] and "flow=" not in uris[2]
    assert "path=%2Ftestpath" in uris[2] and "sni=vpn.example.com" in uris[2]
    assert uris[3].startswith("vless://11111111-2222-3333-4444-555555555555@vpn.example.com:8443?")
    assert "pbk=TESTPBK" in uris[3] and "flow=xtls-rprx-vision" in uris[3]
    assert "sni=www.samsung.com" in uris[3]


def test_cf_xhttp_node(monkeypatch):
    monkeypatch.setattr(subgen.C, "PL_ENABLED", False)
    monkeypatch.setattr(subgen.C, "CF_HOST", "cdn.example.com")
    uris = subgen.node_uris(USER)
    assert len(uris) == 5
    cf = uris[3]
    assert cf.startswith("vless://11111111-2222-3333-4444-555555555555@cdn.example.com:443?")
    assert "type=xhttp" in cf and "security=tls" in cf and "flow=" not in cf
    assert "sni=cdn.example.com" in cf and "host=cdn.example.com" in cf and "path=%2Ftestpath" in cf


def test_pl_full_stack_when_enabled(monkeypatch):
    monkeypatch.setattr(subgen.C, "PL_ENABLED", True)
    monkeypatch.setattr(subgen.C, "PL_HOST", "loc2.example.com")
    monkeypatch.setattr(subgen.C, "PL_OBFS_PASSWORD", "plobfs")
    monkeypatch.setattr(subgen.C, "PL_HY_MAIN_PORT", 443)
    monkeypatch.setattr(subgen.C, "PL_HY_TURBO_PORT", 8444)
    monkeypatch.setattr(subgen.C, "PL_REALITY_PORT", 443)
    monkeypatch.setattr(subgen.C, "PL_REALITY_PBK", "PLPBK123")
    monkeypatch.setattr(subgen.C, "PL_REALITY_SID", "plsid")
    monkeypatch.setattr(subgen.C, "PL_REALITY_SNI", "www.samsung.com")
    monkeypatch.setattr(subgen.C, "PL_XHTTP_PORT", 8443)
    uris = subgen.node_uris(USER)
    assert len(uris) == 8
    loc = uris[4:]
    assert loc[0].startswith("hysteria2://tok:PWD123@loc2.example.com:443?")
    assert "obfs-password=plobfs" in loc[0] and "insecure" not in loc[0]
    assert loc[1].startswith("hysteria2://tok:PWD123@loc2.example.com:8444?")
    assert loc[2].startswith("vless://11111111-2222-3333-4444-555555555555@loc2.example.com:8443?")
    assert "type=xhttp" in loc[2] and "flow=" not in loc[2]
    assert loc[3].startswith("vless://11111111-2222-3333-4444-555555555555@loc2.example.com:443?")
    assert "pbk=PLPBK123" in loc[3] and "security=reality" in loc[3]


def test_pl_node_absent_when_disabled(monkeypatch):
    monkeypatch.setattr(subgen.C, "PL_ENABLED", False)
    assert len(subgen.node_uris(USER)) == 4


def test_base64_subscription_roundtrip(monkeypatch):
    monkeypatch.setattr(subgen.C, "PL_ENABLED", False)
    decoded = base64.b64decode(subgen.subscription_b64(USER)).decode()
    assert decoded.count("\n") == 3
    assert "hysteria2://PWD123@vpn.example.com:443" in decoded
    assert "type=xhttp" in decoded


def test_userinfo_header():
    h = subgen.userinfo_header(used=1024, limit_bytes=100, expire=1800000000)
    assert h == "upload=0; download=1024; total=100; expire=1800000000"
    h2 = subgen.userinfo_header(used=5, limit_bytes=None, expire=0)
    assert h2 == "upload=0; download=5; total=0; expire=0"


def test_crypt5_link(monkeypatch):
    captured = {}

    class FakeResp:
        def raise_for_status(self): pass
        def json(self): return {"encrypted_link": "happ://crypt5/ABC"}

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        return FakeResp()

    monkeypatch.setattr(subgen.requests, "post", fake_post)
    link = subgen.crypt5_link("https://vpn.example.com/s/tok")
    assert link == "happ://crypt5/ABC"
    assert captured["url"] == "https://crypto.happ.su/api-v2.php"
    assert captured["json"] == {"url": "https://vpn.example.com/s/tok"}
