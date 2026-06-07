# VPS Control Bot Oneclick

VPS Control Bot Oneclick is a self-hosted Telegram control panel for small Ubuntu/Debian VPS servers. It can be installed with a single interactive `curl` command and gives you status, services, traffic, logs, subscription links, Cloudflare best-IP status, and safe cleanup reports from Telegram.

## One-Command Install

```bash
curl -fsSL https://raw.githubusercontent.com/shangguanwt/vps-control-bot-oneclick/main/install.sh | sudo bash
```

The installer asks for:

- Telegram Bot Token
- allowed Telegram user IDs
- VPS display name
- optional subscription base URL
- optional health-check URLs
- optional Cloudflare test host

Secrets are stored only on the VPS:

```bash
/etc/vps-control-bot.env
```

## Features

- `/start`, `/panel` - open the control panel
- `/status` - load, memory, disk, TCP/BBR
- `/services` - systemd services and Docker containers
- `/traffic` - 3X-UI traffic when the database exists
- `/nodes` - subscription node names
- `/sub` - subscription URLs
- `/check` - HTTP status checks
- `/cf_status` - Cloudflare best-IP status
- `/cf_optimize` - VPS-side Cloudflare IP test
- `/cleanup_status` - safe cleanup timer status
- `/cleanup` - run safe cleanup after confirmation
- `/backup` - archive key config files
- `/logs nginx`, `/logs xui` - recent logs

## Safe Cleanup

The installer enables `vps-safe-cleanup.timer`, which runs hourly by default. It cleans only recoverable data:

- systemd journal
- APT cache
- old files in `/tmp` and `/var/tmp`
- oversized Docker JSON logs
- page cache only when available memory is low or swap usage is high

It does not delete user data, databases, Xray configs, subscription files, or home directories.

## Update

```bash
curl -fsSL https://raw.githubusercontent.com/shangguanwt/vps-control-bot-oneclick/main/install.sh | sudo bash -s -- --update
```

Update refreshes files and restarts services. It keeps `/etc/vps-control-bot.env`.

## Uninstall

```bash
curl -fsSL https://raw.githubusercontent.com/shangguanwt/vps-control-bot-oneclick/main/install.sh | sudo bash -s -- --uninstall
```

Uninstall keeps `/etc/vps-control-bot.env` by default so secrets are not removed accidentally.

## Local Checks

```bash
python3 -m py_compile src/bot.py src/vps-safe-cleanup
bash -n install.sh
```

## Security Boundaries

- Do not commit real `BOT_TOKEN`, Telegram IDs, VPS IPs, private domains, subscription tokens, or panel paths.
- Keep `ALLOWED_TELEGRAM_IDS` restricted to trusted users.
- The bot does not provide arbitrary shell execution.
- The installer does not open firewall ports.
