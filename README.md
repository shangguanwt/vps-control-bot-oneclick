# VPS Control Bot Oneclick

Self-hosted Telegram VPS control panel with one-command deployment.

## Languages

- [简体中文](docs/README.zh-CN.md)
- [English](docs/README.en.md)
- [日本語](docs/README.ja.md)

## Quick Install

```bash
curl -fsSL https://raw.githubusercontent.com/shangguanwt/vps-control-bot-oneclick/main/install.sh | sudo bash
```

The installer is interactive. It asks for your Telegram Bot Token, allowed Telegram user IDs, VPS display name, optional subscription URL, optional health-check URLs, and optional Cloudflare test host.

Secrets are stored only on the VPS:

```bash
/etc/vps-control-bot.env
```

## What It Provides

- Telegram control panel for VPS status, services, traffic, logs, backups, and speed tests
- Optional 3X-UI traffic and subscription display
- Optional Cloudflare best-IP status and VPS-side test
- Hourly safe cleanup timer for journal, cache, temp files, and oversized Docker logs
- Telegram allowlist and confirmation buttons for risky actions

## Update

```bash
curl -fsSL https://raw.githubusercontent.com/shangguanwt/vps-control-bot-oneclick/main/install.sh | sudo bash -s -- --update
```

## Uninstall

```bash
curl -fsSL https://raw.githubusercontent.com/shangguanwt/vps-control-bot-oneclick/main/install.sh | sudo bash -s -- --uninstall
```

## Security

Do not publish real Bot Tokens, Telegram IDs, VPS IPs, private domains, subscription tokens, or panel paths. The bot does not expose arbitrary shell execution.
