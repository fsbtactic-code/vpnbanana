# Выбор самого быстрого REALITY SNI из пула (по умолчанию раз в 30 минут)

Скрипт: [scripts/reality-failover.sh](scripts/reality-failover.sh)

## Что делает

1. Читает из БД 3x-ui первый **включённый** inbound: `vless`, порт **443**.
2. Берёт текущий хост из `realitySettings.target` или `dest` (до `:`).
3. Для **каждого** хоста из пула `CANDIDATES` замеряет время ответа: `curl --tlsv1.3 https://хост/` (как публичный TLS-dest для REALITY). Источник пула: если задан **`CANDIDATES_FILE`** — он; иначе, если есть непустой **`SNICDNBEST.txt`** (см. [build-sni-rotation-pool.sh](scripts/build-sni-rotation-pool.sh)), берётся он; иначе **`sni-cdn.txt`** (из `data/SNICDN.txt`); иначе **`sni-candidates.txt`**; иначе встроенный короткий список.
4. Выбирает хост с **минимальным** временем среди ответивших.
5. Если он **совпадает** с текущим в БД — только лог `KEEP`, **без** рестарта.
6. Если **другой** — обновляет `target`, `dest`, `serverNames`, в БД 3x-ui выставляет **`subUpdates`** (часы → заголовок `Profile-Update-Interval`) и **`subAnnounce`** (чтобы клиенты увидели смену подписки), затем перезапускает `x-ui`.

Интервал в режиме `watch`: **`WATCH_INTERVAL_SEC`** (по умолчанию **3600** = 1 час).

## Важно про клиенты

После смены SNI старые ссылки `vless://...&sni=старый...` **перестанут совпадать** с сервером. Скрипт после **смены SNI** (`SWITCH`/`UPDATED`) обновляет в SQLite 3x-ui **`subUpdates`** (по умолчанию **1** час → заголовок **`Profile-Update-Interval`**, см. [subController.go](https://github.com/MHSanaei/3x-ui/blob/main/sub/subController.go)) и **`subAnnounce`**. С версии репо с **`BUMP_SUB_ON_KEEP=1`** (по умолчанию) то же делается и при **`KEEP`** (SNI уже лучший) — иначе заголовки не менялись и клиент с интервалом 1 ч не перезапрашивал подписку.

Тело подписки при **KEEP** часто **то же** (тот же `sni=` в `vless://`), меняются в основном **HTTP-заголовки** — клиент должен уметь реагировать на **`Announce`** / интервал или обновлять по кнопке.

- Переменные: **`SUB_UPDATES_HOURS`** (например `1`), **`BUMP_SUB_ANNOUNCE=0`** — не трогать текст объявления.
- Полностью «мгновенно» на стороне клиента зависит от приложения; при обратном прокси на порт подписки (**2096**) отключи кэш: `Cache-Control: no-store` для пути `/sub/`.

Нужна **subscription** из панели с автообновлением или ручное обновление конфига.

## Push на телефон («обнови подписку»)

Ссылка подписки по HTTP **сама не шлёт push** — клиент только периодически её опрашивает. Чтобы при **смене SNI** прилетало уведомление, на сервере в `reality-failover` можно включить:

### Вариант A — [ntfy.sh](https://ntfy.sh) (проще всего)

1. На телефоне: приложение **ntfy** (F-Droid / Google Play).
2. Задай секретный топик (длинная случайная строка), не светись публично.
3. В `systemctl edit reality-watcher`:

```ini
[Service]
Environment=NOTIFY_URL=https://ntfy.sh/ТВОЙ_СЕКРЕТНЫЙ_ТОПИК
Environment=NOTIFY_TITLE=VPN bananamaster
```

После **реальной смены SNI** (`SWITCH`) скрипт сделает `POST` с текстом в теле — придёт push. Текст: `SNI Обновлен! Ping: …ms SNI: … | Обновите подписку в своем клиенте`. При желании пуш и на каждый `KEEP` с обновлением заголовков: `Environment=NOTIFY_ON_KEEP=1` (шумнее).

### Вариант B — Telegram (админ + клиент)

**По умолчанию** скрипт читает настройки из панели 3x-ui (та же БД `XUI_DB`, таблица `settings`):

| Ключ в БД | Где в панели |
|-------------|----------------|
| `tgBotToken` | **Settings → Telegram Bot → Telegram Token** |
| `tgBotChatId` | **Admin Chat ID** — можно несколько через **запятую**; для failover: **первый** ID → админ, **второй** → клиент (если нужен второй получатель) |

Если в `systemd` заданы `TELEGRAM_BOT_TOKEN` / `TELEGRAM_ADMIN_CHAT_ID` / `TELEGRAM_CLIENT_CHAT_ID`, они **перекрывают** соответствующие значения из БД (удобно для тестов или отдельного бота).

Ручной override без панели:

```ini
[Service]
Environment=TELEGRAM_BOT_TOKEN=123456:ABC...
Environment=TELEGRAM_ADMIN_CHAT_ID=111111111
Environment=TELEGRAM_CLIENT_CHAT_ID=222222222
```

Оба получат одно и то же сообщение при **фактическом** обновлении SNI. Устаревший вариант с одним получателем: `TELEGRAM_CHAT_ID` (если админ/клиент не заданы).

Можно **одновременно** с `NOTIFY_URL` — уйдёт и в ntfy, и в Telegram.

### Порог смены SNI по задержке

По умолчанию **`SWITCH_MIN_IMPROVE_MS=50`**: если лидер пула не совпадает с текущим SNI, но выигрыш по времени `curl` меньше **50 мс**, переключение **не выполняется** (меньше шума для клиентов). Порог в миллисекундах: `Environment=SWITCH_MIN_IMPROVE_MS=80`

### Отключить пуш при смене

`Environment=NOTIFY_ON_SWITCH=0`

Обнови скрипт с GitHub и перезапусти watcher после правки unit.

## Пул доменов в репозитории

- **[data/SNICDN.txt](data/SNICDN.txt)** — CDN/edge‑ориентированный пул для ротации (рекомендуемый базовый источник для failover).
- **[data/sni-candidates.txt](data/sni-candidates.txt)** — широкий общий пул (fallback). Собирается скриптом [scripts/merge-sni-pools.sh](scripts/merge-sni-pools.sh): **локальный список** + домены из [hxehex/russia-mobile-internet-whitelist](https://github.com/hxehex/russia-mobile-internet-whitelist) (`whitelist.txt`, SNI для мобильного вайтлиста). Первые строки файла — служебные комментарии `#`; дальше по одному хосту в строке.
- **[data/sni-candidates-local.txt](data/sni-candidates-local.txt)** — правки «свои» только сюда; затем из корня репо: `./scripts/merge-sni-pools.sh` и коммит обновлённого `sni-candidates.txt`.

Переменная **`MOBILE_WHITELIST_URL`** в `merge-sni-pools.sh` задаёт другой raw-URL, если нужен форк или зеркало.

**Нагрузка:** тысячи хостов в `sni-candidates.txt` дают долгий каждый прогон failover. Рекомендуется один раз собрать **укороченный пул** (см. ниже).

## Отбор доменов на сервере → пул для ротации

Скрипт **[scripts/build-sni-rotation-pool.sh](scripts/build-sni-rotation-pool.sh)** с VPS:

1. Резолвит имя (**`getent ahosts`**).
2. Проверяет **HTTPS + TLS 1.3** с **проверкой сертификата** (как у `curl` без `-k`) — близко к требованиям к публичному dest у VLESS+REALITY.
3. Пишет **`/usr/local/share/reality-failover/SNICDNBEST.txt`**: хосты **по возрастанию задержки**, не больше **`TOP_N`** (по умолчанию **120**).

`reality-failover.sh` **сначала** использует `SNICDNBEST.txt`, если в нём есть строки-хосты; иначе — `sni-cdn.txt`; иначе — `sni-candidates.txt`.

Установка и однократная сборка (после того как уже лежит `sni-cdn.txt`):

```bash
sudo curl -fSL -o /usr/local/bin/build-sni-rotation-pool.sh \
  'https://raw.githubusercontent.com/fsbtactic-code/vpnbanana/main/scripts/build-sni-rotation-pool.sh'
sudo chmod +x /usr/local/bin/build-sni-rotation-pool.sh

# опционально: TOP_N=80 PARALLEL=40
sudo env TOP_N=120 PARALLEL=30 /usr/local/bin/build-sni-rotation-pool.sh
```

Проверка результата:

```bash
grep -v '^#' /usr/local/share/reality-failover/SNICDNBEST.txt | head -20
wc -l /usr/local/share/reality-failover/SNICDNBEST.txt
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
sudo curl -fSL -o /usr/local/share/reality-failover/sni-cdn.txt \
  'https://raw.githubusercontent.com/fsbtactic-code/vpnbanana/main/data/SNICDN.txt'
sudo curl -fSL -o /usr/local/share/reality-failover/sni-candidates.txt \
  'https://raw.githubusercontent.com/fsbtactic-code/vpnbanana/main/data/sni-candidates.txt'

# Проверка вручную
sudo /usr/local/bin/reality-failover.sh once
```

Свой список: **`CANDIDATES_FILE`**, либо положи **`sni-rotation-pool.txt`** / **`sni-cdn.txt`** / **`sni-candidates.txt`** в `/usr/local/share/reality-failover/`.

`Environment=CANDIDATES_FILE=/etc/reality-failover/my-pool.txt`

Замер пула к целям идёт **параллельно** (`PROBE_PARALLEL`, по умолчанию **12**). **Вторая волна** выбирает кандидатов так: все хосты из 1-й волны, у которых время ≤ **самый быстрый в 1-й волне + `VERIFY_MARGIN_SEC`** (по умолчанию **0.15** с), но не больше **`VERIFY_MAX_CANDIDATES`** (32); если кандидатов мало — **добор сверху** списка до **`VERIFY_TOP_N`** (8). По каждому кандидату — **`VERIFY_SAMPLES`** (3) последовательных замера, **медиана**; победитель — **минимальная медиана** (в логе строка `verify:` и топ‑5). Так отсекается «случайный» лидер при параллельном замере и выбирается устойчиво самый быстрый. Сертификат под SNI: `REALITY_SSL_VERIFY=1`. Полный лог 1-й волны: `POOL_PROBE_FULL=1`. `VERIFY_TOP_N=0` — отключить verify. Старый `curl`: `REALITY_SSL_VERIFY=0`.

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
