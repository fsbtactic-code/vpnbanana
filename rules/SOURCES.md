# Список обхода (RU split-tunnel whitelist) - источники

`whitelist-src.txt` - сырой список доменов РФ-сервисов, которые должны идти **напрямую**
(мимо VPN). Зачем: банки, госуслуги, маркетплейсы (Wildberries/Ozon), такси, медиа часто
ругаются на чужое гео или режут датацентр-IP. Если они идут direct - видят домашний IP
пользователя и работают штатно, при этом весь остальной трафик защищён VPN.

Это просто данные маршрутизации, не секрет. Публикуется открыто, можно форкать и дополнять.

## Сборка

```bash
python3 build_wl.py
```

Перегенерирует три формата из `whitelist-src.txt`:

| Файл | Формат | Для чего |
|------|--------|----------|
| `ru-whitelist.json` | sing-box `rule_set` (version 2, format source) | sing-box / Hiddify / Karing |
| `ru-whitelist-clash.yaml` | Clash/Mihomo rule-provider (behavior: domain) | Clash.Meta / Mihomo |
| `ru-whitelist.txt` | plain, по хосту на строку | прочие клиенты, ручная правка |

## Как подключить на клиенте

- **sing-box / Hiddify:** добавить `rule_set` с `type: remote`, `format: source`,
  `url: https://<твой-домен>/rules/ru-whitelist.json`, и правило
  `{ "rule_set": "ru-whitelist", "outbound": "direct" }` ПЕРЕД `final: proxy`.
- **Clash/Mihomo:** `rule-providers` -> `behavior: domain`, `url: .../ru-whitelist-clash.yaml`,
  правило `RULE-SET,ru-whitelist,DIRECT`.
- Сервер раздаёт эти файлы по `/rules/*` (nginx-location в шаблоне vhost, с CORS).

## Происхождение и родственные проекты

Список собран и дополнен на базе публичных списков RU-сегмента:

- **hxehex/russia-mobile-internet-whitelist** - белый список хостов мобильного интернета РФ
  (CDN, API, антифрод банков и маркетплейсов), основа этого списка.
- **hydraponique/roscomvpn-routing** - профили маршрутизации Happ (формат
  `DirectSites`/`ProxySites`), канон Happ-роутинга и geoip/geosite.
- **kort0881/russia-whitelist** - whitelist-домены РФ на случай региональных шатдаунов.

Дополняется точечно по мере того, как какой-нибудь RU-сервис начинает течь через VPN-выход
и ругаться на гео. Добавил хост в `whitelist-src.txt` -> `python3 build_wl.py` -> залил.
