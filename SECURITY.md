# Security Policy

This project is a self-hosted VPS operations helper. Treat the Telegram bot token and allowed Telegram IDs as production secrets.

## Supported Setup

- Ubuntu/Debian VPS
- Python 3
- systemd
- Telegram bot token stored in `/etc/vps-control-bot.env`

## Reporting Issues

Please open a GitHub issue without posting secrets. Redact:

- bot tokens
- Telegram user IDs
- VPS IP addresses
- domain names if private
- subscription tokens
- panel paths

## Design Boundaries

- No arbitrary shell command endpoint is exposed.
- Dangerous operations require Telegram button confirmation.
- The installer does not open firewall ports.
- The cleanup timer only removes recoverable cache/log/temp data.
