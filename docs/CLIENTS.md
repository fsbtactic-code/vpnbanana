# Клиенты

Подписка отдаётся как список узлов (base64) по ссылке `https://<домен>/s/<token>` (бот) или
`https://<домен>/sub/<token>` (личная при standalone). Импортируй URL в клиент как подписку.

## Рекомендуется: Happ

Поддерживает все узлы стека (Hysteria2, Reality, XHTTP) и авто-обход RU из заголовка подписки.

- iOS: "Happ Proxy Utility" в App Store.
- Android: Google Play (`com.happproxy`) или APK с GitHub `Happ-proxy/happ-android`.
- Desktop: `github.com/Happ-proxy/happ-desktop/releases` (Windows/macOS/Linux).

Импорт: добавь подписку по URL. Список обхода включится сам (подписка отдаёт заголовок
`routing` с профилем). Если используешь сырые ноды без подписки - выстави Remote DNS вручную.

## sing-box / Hiddify / Karing

Едят подписку и поддерживают `rule_set` для списка обхода. Добавь в маршрутизацию правило
`{ "rule_set": "ru-whitelist", "outbound": "direct" }` (URL правил - `/rules/ru-whitelist.json`)
перед `final: proxy`, если клиент не подхватил обход из подписки.

## Clash / Mihomo

Используй `rule-provider` с `behavior: domain` и `/rules/ru-whitelist-clash.yaml`, правило
`RULE-SET,ru-whitelist,DIRECT`.

## Какой узел выбирать

- Тупит/рвётся - переключись между Hysteria (UDP) и XHTTP/Reality (TCP): их ломает разный DPI.
- Совсем не идёт на прямом узле - пробуй XHTTP+CDN.
- Нужна скорость и DPI не мешает - Hysteria turbo.
