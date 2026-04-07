# vpnbanana

VLESS + REALITY on Google Cloud (3x-ui).  
Private ops: put real panel URL / IPs in a local note — **do not commit secrets**.

## Stack

- Protocol: VLESS + TCP + REALITY + `xtls-rprx-vision`
- Panel: 3x-ui v2.8+
- Example: GCP `e2-standard-2`, `us-east4-b`
- OS: Debian 12 (bookworm)
- BBR + buffers: see `install.sh`
- Panel TLS: Let’s Encrypt (acme.sh) + paths in SQLite if needed

## REALITY SNI (from VPS scan)

See [REALITY-DEST.md](REALITY-DEST.md). Short version:

- **Speed:** `sovcombank.ru:443`
- **“Official RU” SNI:** `nalog.ru:443`

## Quick Deploy (fresh server)

```bash
sudo bash install.sh
```

## Files

| File | Description |
|------|-------------|
| `install.sh` | Full server setup script |
| `xray-config.template.json` | Xray template (no secrets) |
| `check-domains.sh` | Scan domains for TLS1.3 + H2 from the server |
| `REALITY-DEST.md` | Parsed scan + inbound hints |
| `SERVER-FIXES.md` | Watchdog / xray.service / fail2ban |
| `REALITY-FAILOVER.md` | Cron: авто-смена SNI/dest при падении |
| `scripts/reality-failover.sh` | Скрипт проверки + выбор быстрейшего хоста |
| `../reality-checker/` | Windows PowerShell checker (optional) |

## Ports

| Service | Port |
|---------|------|
| VPN (inbound) | 443 |
| Panel | 24443 (example) |
| Subscription (x-ui) | 2096 (default) |

## Useful Commands

```bash
# Check status
vpn-status

# Manage panel
sudo x-ui

# View logs
journalctl -u x-ui -f

# Restart
sudo systemctl restart x-ui

# SSH to server
gcloud compute ssh neurocloud --zone us-east4-b
```

## Security Notes

- Use a long random panel path; restrict panel port in GCP firewall if you can.
- Enable **watchdog only after** inbound on 443 exists (see `SERVER-FIXES.md`).
- **Never commit** UUID, private keys, shortIDs, or panel passwords.
