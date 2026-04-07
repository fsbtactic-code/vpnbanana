# Fixes after mixed Xray-install + 3x-ui

## 1. Stop the restart loop (watchdog)

If nothing listens on **443** yet, watchdog will keep restarting `x-ui`.

```bash
sudo systemctl disable --now xray-watchdog
```

Create **VLESS + REALITY** inbound on port **443** in the panel, then:

```bash
sudo ss -ltnH '( sport = :443 )'
sudo systemctl enable --now xray-watchdog
```

## 2. Disable standalone `xray.service` (conflicts with x-ui)

```bash
sudo systemctl disable --now xray
sudo systemctl status x-ui --no-pager
```

## 3. fail2ban

Start the daemon; remove a broken jail if the filter file is missing.

```bash
sudo systemctl enable --now fail2ban
sudo fail2ban-client status

# If x-ui jail errors, remove until you add a real filter:
sudo rm -f /etc/fail2ban/jail.d/x-ui.conf
sudo systemctl restart fail2ban
```

## 4. Weekly cron + Xray-install

The official install script may re-enable `xray.service`. After each weekly run, if you use only x-ui:

```bash
sudo systemctl disable --now xray
sudo systemctl restart x-ui
```

Or edit `/etc/cron.weekly/update-xray` to restart only `x-ui` and add `systemctl disable --now xray` after update.
