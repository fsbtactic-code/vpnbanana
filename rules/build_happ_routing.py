import base64
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

PROXY_SITES = [
    "google.com", "gstatic.com", "googleapis.com", "googleusercontent.com",
    "ggpht.com", "googlevideo.com", "withgoogle.com", "gvt1.com", "gvt2.com",
    "labs.google", "notebooklm.google", "google.dev",
    "openai.com", "chatgpt.com", "oaistatic.com", "oaiusercontent.com",
    "elevenlabs.io", "x.ai", "grok.com", "claude.ai",
]


def apexes_from(path):
    with open(path, encoding="utf-8") as f:
        raw = [l.strip().lower() for l in f]
    hosts = [h for h in raw if h and not h.startswith("#") and "." in h and " " not in h]
    return sorted({".".join(h.split(".")[-2:]) for h in hosts})


def main():
    apexes = apexes_from(os.path.join(HERE, "whitelist-src.txt"))
    prof = {
        "Name": "BananaVPN RU-direct",
        "GlobalProxy": "true",
        "UseChunkFiles": "true",
        "RemoteDns": "8.8.8.8",
        "DomesticDns": "77.88.8.8",
        "RemoteDNSType": "DoH",
        "RemoteDNSDomain": "https://8.8.8.8/dns-query",
        "RemoteDNSIP": "8.8.8.8",
        "DomesticDNSType": "DoH",
        "DomesticDNSDomain": "https://77.88.8.8/dns-query",
        "DomesticDNSIP": "77.88.8.8",
        "Geoipurl": "https://cdn.jsdelivr.net/gh/hydraponique/roscomvpn-geoip@202606220919/release/geoip.dat",
        "Geositeurl": "https://cdn.jsdelivr.net/gh/hydraponique/roscomvpn-geosite@202604152235/release/geosite.dat",
        "DnsHosts": {},
        "RouteOrder": "block-proxy-direct",
        "DirectSites": ["geosite:private", "geosite:whitelist"] + apexes,
        "DirectIp": ["geoip:private", "geoip:whitelist"],
        "ProxySites": PROXY_SITES,
        "ProxyIp": [],
        "BlockSites": [],
        "BlockIp": [],
        "DomainStrategy": "IPIfNonMatch",
        "FakeDNS": "false",
    }
    compact = json.dumps(prof, ensure_ascii=False, separators=(",", ":"))
    b64 = base64.b64encode(compact.encode("utf-8")).decode("ascii")
    deeplink = "happ://routing/onadd/" + b64
    assert json.loads(base64.b64decode(b64).decode("utf-8"))["Name"] == prof["Name"]

    with open(os.path.join(HERE, "happ-routing.json"), "w", encoding="utf-8") as f:
        json.dump(prof, f, ensure_ascii=False, indent=2)
    with open(os.path.join(HERE, "happ-routing.deeplink"), "w", encoding="utf-8") as f:
        f.write(deeplink + "\n")
    print(f"DirectSites={len(prof['DirectSites'])} ProxySites={len(PROXY_SITES)} deeplink_len={len(deeplink)}")


if __name__ == "__main__":
    main()
