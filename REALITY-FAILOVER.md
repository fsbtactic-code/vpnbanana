# Автосмена REALITY dest / SNI (каждые 10 минут)

Скрипт: [scripts/reality-failover.sh](scripts/reality-failover.sh)

## Что делает

1. Читает из БД 3x-ui первый **включённый** inbound: `vless`, порт **443**.
2. Берёт текущий хост из `realitySettings.dest` (до `:`).
3. Проверяет его `curl --tlsv1.3 https://хост/`.
4. Если **живой** — выходит, ничего не меняет.
5. Если **не отвечает** — перебирает список `CANDIDATES`, замеряет время ответа, выбирает **самый быстрый** рабочий.
6. Пишет в `stream_settings` новые `dest` и `serverNames`, перезапускает `x-ui`.

## Важно про клиенты

После смены SNI старые ссылки `vless://...&sni=старый...` **перестанут совпадать** с сервером.

Нужно либо **subscription** из панели с автообновлением, либо после смены заново экспортировать узел и обновить конфиг вручную.

## Установка на сервере

```bash
sudo apt install -y jq curl sqlite3 util-linux

sudo nano /usr/local/bin/reality-failover.sh
# вставь содержимое scripts/reality-failover.sh с GitHub или скопируй файл

sudo chmod +x /usr/local/bin/reality-failover.sh

# Проверка вручную
sudo /usr/local/bin/reality-failover.sh
```

## Cron раз в 10 минут

```bash
echo '*/10 * * * * root /usr/local/bin/reality-failover.sh >> /var/log/reality-failover.log 2>&1' | sudo tee /etc/cron.d/reality-failover
sudo chmod 644 /etc/cron.d/reality-failover
```

Лог: `tail -f /var/log/reality-failover.log`

## Если скрипт пишет «no enabled vless inbound on 443»

Сначала в панели создай inbound **VLESS + REALITY** на порту **443**.

## Если UPDATE падает

Проверь имя колонки (редко отличается по версии 3x-ui):

```bash
sqlite3 /etc/x-ui/x-ui.db "PRAGMA table_info(inbounds);"
```

Должна быть колонка `stream_settings`. Если другая — поправь скрипт.

## Отключить

```bash
sudo rm -f /etc/cron.d/reality-failover
```
