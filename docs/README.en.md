# VPS Control Bot Oneclick

![VPS Control Bot Oneclick](images/hero.svg)

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](../LICENSE)
[![Install](https://img.shields.io/badge/install-curl%20%7C%20bash-0f766e.svg)](../install.sh)
[![Python](https://img.shields.io/badge/python-3.x-blue.svg)](../src/bot.py)
[![Systemd](https://img.shields.io/badge/runtime-systemd-334155.svg)](../systemd/)

VPS Control Bot Oneclick is a self-hosted Telegram control panel for small Ubuntu/Debian VPS servers. It provides status cards, service checks, 3X-UI traffic summaries, subscription links, Cloudflare best-IP status, logs, backups, speed tests, and a safe cleanup timer.

The README layout is inspired by the deployment-first style of [hotyue/IP-Sentinel](https://github.com/hotyue/IP-Sentinel) and its [installation and upgrade guide](https://blog.iot-architect.com/engineering-practice/ip-sentinel-installation-and-upgrade-guide/). This project is independent and focuses on Telegram-based VPS control.

## Preview

![Telegram panel preview](images/panel-preview.svg)

## Features

| Area | Capability |
| --- | --- |
| Control panel | `/start`, `/panel` |
| System status | `/status` for load, memory, disk, swap, TCP/BBR |
| Services | `/services` for systemd and Docker |
| 3X-UI | `/traffic`, `/nodes` when the database exists |
| Subscriptions | `/sub` when `SUB_BASE` is configured |
| Health checks | `/check` for configured URLs |
| Cloudflare | `/cf_status`, `/cf_optimize` |
| Cleanup | `/cleanup_status`, `/cleanup` with confirmation |
| Logs and backup | `/logs nginx`, `/logs xui`, `/backup` |

## Architecture

![Architecture](images/architecture.svg)

Secrets are stored only on the VPS:

```bash
/etc/vps-control-bot.env
```

The GitHub repository contains code, templates, and docs. It must not contain your Bot Token, Telegram ID, VPS IP, private domain, or subscription token.

## Requirements

- Debian / Ubuntu VPS
- root access
- access to GitHub Raw
- Python 3
- systemd
- curl

The installer uses `apt-get` to install required packages.

## Install

![Install flow](images/install-flow.svg)

```bash
curl -fsSL https://raw.githubusercontent.com/shangguanwt/vps-control-bot-oneclick/main/install.sh | sudo bash
```

The installer asks for:

| Field | Description |
| --- | --- |
| `BOT_TOKEN` | Telegram Bot Token |
| `ALLOWED_TELEGRAM_IDS` | comma-separated Telegram user IDs |
| `VPS_DISPLAY_NAME` | display name in Telegram |
| `SUB_BASE` | optional subscription base URL |
| `CHECK_URLS` | optional health-check URLs |
| `CF_TEST_HOST` | optional Cloudflare test SNI host |
| `XUI_DB` | default `/etc/x-ui/x-ui.db` |
| `SUB_GENERATOR` | default `/etc/proxy-subscription/generate.py` |

After installation, send this to your bot:

```text
/start
```

## Verify

```bash
systemctl is-active vps-control-bot
systemctl is-active vps-safe-cleanup.timer
systemctl status vps-control-bot --no-pager
```

Telegram checks:

- `/start` shows the panel
- `/status` shows resources
- `/services` shows service states
- `/cleanup_status` shows cleanup policy
- unauthorized Telegram IDs cannot operate the bot

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

Update refreshes program files, reloads systemd, restarts the bot, and keeps `/etc/vps-control-bot.env`.

## Uninstall

```bash
curl -fsSL https://raw.githubusercontent.com/shangguanwt/vps-control-bot-oneclick/main/install.sh | sudo bash -s -- --uninstall
```

Uninstall removes services, timers, and the install directory. It keeps `/etc/vps-control-bot.env` by default to avoid accidentally deleting secrets.

## Troubleshooting

Bot does not reply:

```bash
systemctl status vps-control-bot --no-pager
journalctl -u vps-control-bot -n 80 --no-pager
```

Check `BOT_TOKEN`, `ALLOWED_TELEGRAM_IDS`, and network access to `api.telegram.org`.

No 3X-UI traffic:

```bash
ls -l /etc/x-ui/x-ui.db
```

If your database path is different, update `XUI_DB` in `/etc/vps-control-bot.env`.

Cleanup timer does not run:

```bash
systemctl list-timers --all vps-safe-cleanup.timer --no-pager
journalctl -u vps-safe-cleanup.service -n 50 --no-pager
```

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
- Restart and cleanup actions require Telegram confirmation.
