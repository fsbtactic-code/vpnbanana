# Выбор самого быстрого REALITY SNI из пула (по умолчанию раз в 30 минут)

Скрипт: [scripts/reality-failover.sh](scripts/reality-failover.sh)

## Что делает

1. Читает из БД 3x-ui первый **включённый** inbound: `vless`, порт **443**.
2. Берёт текущий хост из `realitySettings.target` или `dest` (до `:`).
3. Для **каждого** хоста из пула `CANDIDATES` замеряет время ответа: `curl --tlsv1.3 https://хост/` (как публичный TLS-dest для REALITY). Источник пула: если задан **`CANDIDATES_FILE`** — он; иначе, если есть непустой **`sni-rotation-pool.txt`** (см. [build-sni-rotation-pool.sh](scripts/build-sni-rotation-pool.sh)), берётся он; иначе **`sni-candidates.txt`**; иначе встроенный короткий список.
4. Выбирает хост с **минимальным** временем среди ответивших.
5. Если он **совпадает** с текущим в БД — только лог `KEEP`, **без** рестарта.
6. Если **другой** — обновляет `target`, `dest`, `serverNames`, в БД 3x-ui выставляет **`subUpdates`** (часы → заголовок `Profile-Update-Interval`) и **`subAnnounce`** (чтобы клиенты увидели смену подписки), затем перезапускает `x-ui`.

Интервал в режиме `watch`: **`WATCH_INTERVAL_SEC`** (по умолчанию **1800** = 30 минут).

## Важно про клиенты

После смены SNI старые ссылки `vless://...&sni=старый...` **перестанут совпадать** с сервером. Скрипт после **смены SNI** (`SWITCH`/`UPDATED`) обновляет в SQLite 3x-ui **`subUpdates`** (по умолчанию **1** час → заголовок **`Profile-Update-Interval`**, см. [subController.go](https://github.com/MHSanaei/3x-ui/blob/main/sub/subController.go)) и **`subAnnounce`**. С версии репо с **`BUMP_SUB_ON_KEEP=1`** (по умолчанию) то же делается и при **`KEEP`** (SNI уже лучший) — иначе заголовки не менялись и клиент с интервалом 1 ч не перезапрашивал подписку.

Тело подписки при **KEEP** часто **то же** (тот же `sni=` в `vless://`), меняются в основном **HTTP-заголовки** — клиент должен уметь реагировать на **`Announce`** / интервал или обновлять по кнопке.

- Переменные: **`SUB_UPDATES_HOURS`** (например `1`), **`BUMP_SUB_ANNOUNCE=0`** — не трогать текст объявления.
- Полностью «мгновенно» на стороне клиента зависит от приложения; при обратном прокси на порт подписки (**2096**) отключи кэш: `Cache-Control: no-store` для пути `/sub/`.

Нужна **subscription** из панели с автообновлением или ручное обновление конфига.

## Пул доменов в репозитории

- **[data/sni-candidates.txt](data/sni-candidates.txt)** — итоговый пул для сервера и для [scripts/check-sni-pool.sh](scripts/check-sni-pool.sh). Собирается скриптом [scripts/merge-sni-pools.sh](scripts/merge-sni-pools.sh): **локальный список** + домены из [hxehex/russia-mobile-internet-whitelist](https://github.com/hxehex/russia-mobile-internet-whitelist) (`whitelist.txt`, SNI для мобильного вайтлиста). Первые строки файла — служебные комментарии `#`; дальше по одному хосту в строке.
- **[data/sni-candidates-local.txt](data/sni-candidates-local.txt)** — правки «свои» только сюда; затем из корня репо: `./scripts/merge-sni-pools.sh` и коммит обновлённого `sni-candidates.txt`.

Переменная **`MOBILE_WHITELIST_URL`** в `merge-sni-pools.sh` задаёт другой raw-URL, если нужен форк или зеркало.

**Нагрузка:** тысячи хостов в `sni-candidates.txt` дают долгий каждый прогон failover. Рекомендуется один раз собрать **укороченный пул** (см. ниже).

## Отбор доменов на сервере → пул для ротации

Скрипт **[scripts/build-sni-rotation-pool.sh](scripts/build-sni-rotation-pool.sh)** с VPS:

1. Резолвит имя (**`getent ahosts`**).
2. Проверяет **HTTPS + TLS 1.3** с **проверкой сертификата** (как у `curl` без `-k`) — близко к требованиям к публичному dest у VLESS+REALITY.
3. Пишет **`/usr/local/share/reality-failover/sni-rotation-pool.txt`**: хосты **по возрастанию задержки**, не больше **`TOP_N`** (по умолчанию **120**).

`reality-failover.sh` **сначала** использует `sni-rotation-pool.txt`, если в нём есть строки-хосты; иначе — полный `sni-candidates.txt`.

Установка и однократная сборка (после того как уже лежит `sni-candidates.txt`):

```bash
sudo curl -fSL -o /usr/local/bin/build-sni-rotation-pool.sh \
  'https://raw.githubusercontent.com/fsbtactic-code/vpnbanana/main/scripts/build-sni-rotation-pool.sh'
sudo chmod +x /usr/local/bin/build-sni-rotation-pool.sh

# опционально: TOP_N=80 PARALLEL=40
sudo env TOP_N=120 PARALLEL=30 /usr/local/bin/build-sni-rotation-pool.sh
```

Проверка результата:

```bash
grep -v '^#' /usr/local/share/reality-failover/sni-rotation-pool.txt | head -20
wc -l /usr/local/share/reality-failover/sni-rotation-pool.txt
sudo /usr/local/bin/reality-failover.sh once
```

Для **только отчёта** без записи пула (сортировка OK по времени) подойдёт [check-sni-pool.sh](scripts/check-sni-pool.sh) с `PARALLEL=25`.

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

Свой список: **`CANDIDATES_FILE`**, либо положи **`sni-rotation-pool.txt`** / **`sni-candidates.txt`** в `/usr/local/share/reality-failover/`.

`Environment=CANDIDATES_FILE=/etc/reality-failover/my-pool.txt`

Замер пула к целям идёт **параллельно** (`PROBE_PARALLEL`, по умолчанию **30**). Полный лог всех хостов: `POOL_PROBE_FULL=1`. Последовательно как раньше: `PROBE_PARALLEL=1`.

Для подписки после смены SNI (в том же drop-in):

`Environment=SUB_UPDATES_HOURS=1`

`Environment=BUMP_SUB_ANNOUNCE=1`

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
