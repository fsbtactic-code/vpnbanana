# REALITY destination (SNI / dest) — scan from US (us-east4), Apr 2026

Checked with `curl --tlsv1.3` + HTTP/2. Use the **same string** in `dest` and in `serverNames` (usually apex domain, no `www`, if the site answers on apex).

## Top picks (TLS 1.3 + HTTP/2, lowest latency)

| Domain | Latency | Note |
|--------|---------|------|
| sovcombank.ru | ~179 ms | Fastest in scan |
| lamoda.ru | ~362 ms | Retail |
| ren.tv | ~399 ms | Media |
| habr.com | ~404 ms | Tech |
| vk.com | ~465 ms | Social |
| dns-shop.ru | ~465 ms | Retail |
| nalog.ru | ~471 ms | Tax / strong “RU official” SNI |
| aeroflot.ru | ~471 ms | Airline |
| rt.ru | ~472 ms | Telecom |
| yandex.ru | ~472 ms | Large traffic blend |

## “Whitelist-style” government / finance (still PERFECT on server)

- nalog.ru, mos.ru, sberbank.ru, tinkoff.ru, gazprombank.ru, cbr.ru (slower ~1.7s but OK)

## Domains that FAILED from the US in this scan

otkritie.ru, gazprom.ru, rostelecom.ru, rzd.ru, tatneft.ru, beeline.ru, kremlin.ru, government.ru, mvd.ru, minzdrav.gov.ru, rosreestr.gov.ru, zakupki.gov.ru

## 3x-ui inbound (recommended starter)

- **dest:** `nalog.ru:443` (or `sovcombank.ru:443` for speed)
- **serverNames:** same host as in dest (e.g. `nalog.ru`)
- **Port:** 443
- **Flow:** `xtls-rprx-vision`
- **Fingerprint:** `chrome`
- Add **several shortIds** in the panel.

After inbound works:

```bash
ss -ltnH '( sport = :443 )'
systemctl enable --now xray-watchdog
```
