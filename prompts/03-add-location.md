# Промпт 3 (опционально): вторая локация и WARP

## A. Вторая локация (другая страна)

Нужен второй VPS и домен/поддомен с A-записью на него. Скопируй в агента с доступом к
обоим серверам.

---

Добавь вторую локацию к vpnbanana.

Второй сервер: `<root@IP2>`
Домен локации: `<de.example.com>` (A-запись на второй сервер)

Сделай:
1. На втором сервере запусти `PL_HOST=<домен2> bash /root/vpnbanana/server/add-location.sh`
   (склонируй репозиторий туда, если нужно).
2. Добавь публичный SSH-ключ ОСНОВНОГО сервера в `authorized_keys` второго (основной пушит
   конфиги по SSH). Проверь с основного: `ssh root@<домен2> 'echo ok'`.
3. Вставь напечатанный блок `PL_*` в `/root/vpnbanana/.env` основного сервера.
4. Перезапусти бота на основном: `systemctl restart vpnbanana-bot vpnbanana-backend`.
5. Проверь, что у новых подписок появились узлы второй локации.

## B. WARP-выход для гео-AI (Gemini/OpenAI/ElevenLabs/Grok/Claude)

Если AI-сервисы блокируют датацентр-IP сервера - выведи их через Cloudflare WARP.

---

На сервере vpnbanana запусти `bash /root/vpnbanana/server/warp-egress.sh`. Он поднимет
WireGuard-туннель WARP, направит AI-домены и весь диапазон Google через него, поставит
health-таймер. Проверь: `curl --interface warp https://www.cloudflare.com/cdn-cgi/trace`
должен показать `warp=on`.
