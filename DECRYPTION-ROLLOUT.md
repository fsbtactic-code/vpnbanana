# Decryption Rollout (Server + Telegram)

This guide automates:
- enabling VLESS `decryption` on server side (3x-ui DB),
- forcing subscription refresh headers,
- sending rollout messages via Telegram (optionally with per-user sub URL + QR).

## 1) Update scripts from GitHub

```bash
sudo curl -fSL -o /usr/local/bin/rollout-vless-decryption.sh \
  'https://raw.githubusercontent.com/fsbtactic-code/vpnbanana/main/scripts/rollout-vless-decryption.sh'
sudo chmod +x /usr/local/bin/rollout-vless-decryption.sh

sudo curl -fSL -o /usr/local/bin/telegram-send-config-rollout.sh \
  'https://raw.githubusercontent.com/fsbtactic-code/vpnbanana/main/scripts/telegram-send-config-rollout.sh'
sudo chmod +x /usr/local/bin/telegram-send-config-rollout.sh
```

Optional (for QR images in Telegram):

```bash
sudo apt install -y qrencode
```

## 2) Dry run (recommended)

Set your target `DECRYPTION` string first:

```bash
export DECRYPTION='PUT_YOUR_DECRYPTION_STRING_HERE'
sudo env DECRYPTION="$DECRYPTION" INBOUND_PORT=443 DRY_RUN=1 /usr/local/bin/rollout-vless-decryption.sh
```

## 3) Apply rollout to VLESS inbounds

```bash
sudo env \
  DECRYPTION="$DECRYPTION" \
  INBOUND_PORT=443 \
  SUB_UPDATES_HOURS=1 \
  BUMP_SUB_ANNOUNCE=1 \
  RESTART_XUI=1 \
  /usr/local/bin/rollout-vless-decryption.sh
```

## 4) Send Telegram announcement (generic broadcast)

Reads token/chat IDs from 3x-ui settings (`tgBotToken`, `tgBotChatId`) by default:

```bash
sudo /usr/local/bin/telegram-send-config-rollout.sh
```

Or explicit env:

```bash
sudo env TELEGRAM_BOT_TOKEN='123:abc' CHAT_IDS='111111,222222' \
  /usr/local/bin/telegram-send-config-rollout.sh
```

## 5) Personalized links + QR per user

Create TSV file:

```text
# chat_id<TAB>name<TAB>subscription_url
111111111    Alice    https://your-panel/sub/abc123
222222222    Bob      https://your-panel/sub/def456
```

Run:

```bash
sudo env SUBS_FILE=/root/subscribers.tsv /usr/local/bin/telegram-send-config-rollout.sh
```

## 6) Verify

```bash
sudo journalctl -u x-ui -n 80 --no-pager
sudo sqlite3 /etc/x-ui/x-ui.db "SELECT id,protocol,port,enable,substr(settings,1,180) FROM inbounds WHERE protocol='vless';"
```

If some users fail after rollout, ask them to:
1) disable VPN,
2) refresh subscription,
3) enable VPN again.
