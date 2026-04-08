# Выбор самого быстрого REALITY SNI из пула (по умолчанию раз в 30 минут)

Скрипт: [scripts/reality-failover.sh](scripts/reality-failover.sh)

## Что делает

1. Читает из БД 3x-ui первый **включённый** inbound: `vless`, порт **443**.
2. Берёт текущий хост из `realitySettings.target` или `dest` (до `:`).
3. Для **каждого** хоста из пула `CANDIDATES` замеряет время ответа: `curl --tlsv1.3 https://хост/` (это практичный аналог «пинга» до HTTPS с твоего VPS). Пул по умолчанию читается из файла **`CANDIDATES_FILE`** (см. ниже); если файла нет — используется короткий встроенный список.
4. Выбирает хост с **минимальным** временем среди ответивших.
5. Если он **совпадает** с текущим в БД — только лог `KEEP`, **без** рестарта.
6. Если **другой** — обновляет `target`, `dest`, `serverNames` и перезапускает `x-ui`.

Интервал в режиме `watch`: **`WATCH_INTERVAL_SEC`** (по умолчанию **1800** = 30 минут).

## Важно про клиенты

После смены SNI старые ссылки `vless://...&sni=старый...` **перестанут совпадать** с сервером.

Нужно либо **subscription** из панели с автообновлением, либо после смены заново экспортировать узел и обновить конфиг вручную.

## Пул доменов в репозитории

- **[data/sni-candidates.txt](data/sni-candidates.txt)** — итоговый пул для сервера и для [scripts/check-sni-pool.sh](scripts/check-sni-pool.sh). Собирается скриптом [scripts/merge-sni-pools.sh](scripts/merge-sni-pools.sh): **локальный список** + домены из [hxehex/russia-mobile-internet-whitelist](https://github.com/hxehex/russia-mobile-internet-whitelist) (`whitelist.txt`, SNI для мобильного вайтлиста). Первые строки файла — служебные комментарии `#`; дальше по одному хосту в строке.
- **[data/sni-candidates-local.txt](data/sni-candidates-local.txt)** — правки «свои» только сюда; затем из корня репо: `./scripts/merge-sni-pools.sh` и коммит обновлённого `sni-candidates.txt`.

Переменная **`MOBILE_WHITELIST_URL`** в `merge-sni-pools.sh` задаёт другой raw-URL, если нужен форк или зеркало.

**Нагрузка:** в пуле сотни и тысячи хостов каждый прогон `reality-failover.sh` опрашивает их **последовательно** (до нескольких минут). Имеет смысл прогнать [check-sni-pool.sh](scripts/check-sni-pool.sh), оставить в рабочем файле на сервере только `OK`-хосты или сократить список вручную.

## Установка на сервере

```bash
sudo apt install -y jq curl sqlite3 util-linux

sudo curl -fSL -o /usr/local/bin/reality-failover.sh \
  'https://raw.githubusercontent.com/fsbtactic-code/vpnbanana/main/scripts/reality-failover.sh'
sudo chmod +x /usr/local/bin/reality-failover.sh

sudo mkdir -p /usr/local/share/reality-failover
sudo curl -fSL -o /usr/local/share/reality-failover/sni-candidates.txt \
  'https://raw.githubusercontent.com/fsbtactic-code/vpnbanana/main/data/sni-candidates.txt'

# Проверка вручную
sudo /usr/local/bin/reality-failover.sh once
```

Свой список: положи файл на сервер и задай переменную **`CANDIDATES_FILE`** (например в `systemctl edit reality-watcher`):

`Environment=CANDIDATES_FILE=/etc/reality-failover/my-pool.txt`

## Постоянный «слушатель» (systemd) — рекомендуется

Сервис в режиме `watch`: полный замер пула раз в **30 минут** (`WATCH_INTERVAL_SEC=1800`), затем смена SNI только если лидер пула изменился.

```bash
sudo curl -fsSL https://raw.githubusercontent.com/fsbtactic-code/vpnbanana/main/scripts/reality-watcher.service \
  -o /etc/systemd/system/reality-watcher.service

# Убедись, что скрипт уже в /usr/local/bin/reality-failover.sh (см. выше)

sudo systemctl daemon-reload
sudo systemctl enable --now reality-watcher
sudo systemctl status reality-watcher --no-pager
```

Интервал, например **1 час**:

```bash
sudo systemctl edit reality-watcher
# [Service]
# Environment=WATCH_INTERVAL_SEC=3600
sudo systemctl daemon-reload
sudo systemctl restart reality-watcher
```

Логи:

```bash
journalctl -u reality-watcher -f
```

**Не запускай одновременно** долгий cron с тем же скриптом без нужды (flock не даст двум менять БД сразу, но лишняя нагрузка). Либо cron, либо watcher.

Ручной один прогон:

```bash
sudo /usr/local/bin/reality-failover.sh once
```

## Cron раз в 10 минут (альтернатива watcher)

```bash
echo '*/30 * * * * root /usr/local/bin/reality-failover.sh once >> /var/log/reality-failover.log 2>&1' | sudo tee /etc/cron.d/reality-failover
sudo chmod 644 /etc/cron.d/reality-failover
```

Лог: `tail -f /var/log/reality-failover.log`

## Если скрипт пишет «no enabled vless inbound on 443»

Сначала в панели создай inbound **VLESS + REALITY** на порту **443**.

## 3x-ui: `target` вместо `dest`

В новых сборках 3x-ui в `stream_settings` используется **`realitySettings.target`**, а не `dest`. Скрипт `reality-failover.sh` поддерживает оба поля.

## Если UPDATE падает

Проверь имя колонки (редко отличается по версии 3x-ui):

```bash
sqlite3 /etc/x-ui/x-ui.db "PRAGMA table_info(inbounds);"
```

Должна быть колонка `stream_settings`. Если другая — поправь скрипт.

## Отключить

```bash
sudo systemctl disable --now reality-watcher 2>/dev/null || true
sudo rm -f /etc/cron.d/reality-failover
```
