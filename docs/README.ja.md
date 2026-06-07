# VPS Control Bot Oneclick

![VPS Control Bot Oneclick](images/hero.svg)

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](../LICENSE)
[![Install](https://img.shields.io/badge/install-curl%20%7C%20bash-0f766e.svg)](../install.sh)
[![Python](https://img.shields.io/badge/python-3.x-blue.svg)](../src/bot.py)
[![Systemd](https://img.shields.io/badge/runtime-systemd-334155.svg)](../systemd/)

VPS Control Bot Oneclick は、小規模な Ubuntu/Debian VPS 向けのセルフホスト型 Telegram 管理パネルです。状態確認、サービス監視、3X-UI 通信量、購読リンク、Cloudflare 優先 IP 状態、ログ、バックアップ、安全クリーンアップを Telegram から操作できます。

この README の構成は、[hotyue/IP-Sentinel](https://github.com/hotyue/IP-Sentinel) とその [インストール・アップグレードガイド](https://blog.iot-architect.com/engineering-practice/ip-sentinel-installation-and-upgrade-guide/) の「導入手順を先に明確にする」スタイルを参考にしています。本プロジェクトのコードは独立したものです。

## プレビュー

![Telegram panel preview](images/panel-preview.svg)

## 主な機能

| 項目 | 内容 |
| --- | --- |
| 管理パネル | `/start`, `/panel` |
| システム状態 | `/status` で負荷、メモリ、ディスク、Swap、TCP/BBR |
| サービス | `/services` で systemd と Docker |
| 3X-UI | `/traffic`, `/nodes` |
| 購読 | `/sub` |
| ヘルスチェック | `/check` |
| Cloudflare | `/cf_status`, `/cf_optimize` |
| クリーンアップ | `/cleanup_status`, `/cleanup` |
| ログとバックアップ | `/logs nginx`, `/logs xui`, `/backup` |

## アーキテクチャ

![Architecture](images/architecture.svg)

秘密情報は VPS 上のみに保存されます。

```bash
/etc/vps-control-bot.env
```

GitHub には Bot Token、Telegram ID、VPS IP、プライベートドメイン、購読 token を保存しないでください。

## 要件

- Debian / Ubuntu VPS
- root 権限
- GitHub Raw へアクセス可能
- Python 3
- systemd
- curl

## インストール

![Install flow](images/install-flow.svg)

```bash
curl -fsSL https://raw.githubusercontent.com/shangguanwt/vps-control-bot-oneclick/main/install.sh | sudo bash
```

インストーラーは次の値を確認します。

| 設定 | 説明 |
| --- | --- |
| `BOT_TOKEN` | Telegram Bot Token |
| `ALLOWED_TELEGRAM_IDS` | 許可する Telegram ユーザー ID |
| `VPS_DISPLAY_NAME` | Telegram 上の表示名 |
| `SUB_BASE` | 任意の購読ベース URL |
| `CHECK_URLS` | 任意のヘルスチェック URL |
| `CF_TEST_HOST` | 任意の Cloudflare テストホスト |
| `XUI_DB` | 既定値 `/etc/x-ui/x-ui.db` |
| `SUB_GENERATOR` | 既定値 `/etc/proxy-subscription/generate.py` |

インストール後、Telegram で bot に送信します。

```text
/start
```

## 確認

```bash
systemctl is-active vps-control-bot
systemctl is-active vps-safe-cleanup.timer
systemctl status vps-control-bot --no-pager
```

## 安全クリーンアップ

`vps-safe-cleanup.timer` が毎時実行され、復元可能なデータのみを削除します。

- systemd journal
- APT キャッシュ
- `/tmp` と `/var/tmp` の古いファイル
- 大きすぎる Docker JSON ログ
- メモリ不足または Swap 使用率が高い場合のみ page cache

ユーザーデータ、データベース、Xray 設定、購読ファイル、home ディレクトリは削除しません。

## 更新

```bash
curl -fsSL https://raw.githubusercontent.com/shangguanwt/vps-control-bot-oneclick/main/install.sh | sudo bash -s -- --update
```

## アンインストール

```bash
curl -fsSL https://raw.githubusercontent.com/shangguanwt/vps-control-bot-oneclick/main/install.sh | sudo bash -s -- --uninstall
```

## トラブルシューティング

bot が返信しない場合:

```bash
systemctl status vps-control-bot --no-pager
journalctl -u vps-control-bot -n 80 --no-pager
```

クリーンアップ timer を確認する場合:

```bash
systemctl list-timers --all vps-safe-cleanup.timer --no-pager
journalctl -u vps-safe-cleanup.service -n 50 --no-pager
```

## セキュリティ

実際の Bot Token、Telegram ID、VPS IP、プライベートドメイン、購読 token、管理パネルのパスを公開しないでください。この bot は任意の shell コマンド実行機能を提供しません。
