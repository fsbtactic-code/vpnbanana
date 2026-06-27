# Промпт 2: подключить бота выдачи подписок

Запускай после промпта 1 (узел уже поднят). Скопируй в того же агента.

---

Подключи к узлу vpnbanana Telegram-бота выдачи подписок.

Токен бота: `<токен от @BotFather>`
Мой Telegram id: `<id от @userinfobot>`
Cloudflare-домен для узла XHTTP+CDN (опционально): `<cdn.example.com или "нет">`

Сделай:
1. Если задан CF-домен - впиши `CF_HOST=<домен>` в `/root/vpnbanana/.env`.
2. Запусти `BOT_TOKEN=<токен> ADMIN_ID=<id> bash /root/vpnbanana/bot/install.sh`.
3. Скрипт поднимет backend, бота и учёт трафика, переключит Hysteria на пер-юзер http-auth
   и проверит `/auth`. Дождись health-check OK.
4. Если health-check упал - покажи `journalctl -u vpnbanana-backend -n50`, почини, повтори.
5. Скажи мне открыть бота в Telegram и нажать `/start` (мой аккаунт = админ).

После этого у каждого выданного пользователя в подписке будет 5 узлов: Reality, XHTTP,
XHTTP+CDN (если задан CF), Hysteria, Hysteria turbo - плюс личный кабинет и Mini App.
