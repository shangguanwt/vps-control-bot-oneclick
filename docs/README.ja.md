# VPS Control Bot Oneclick

VPS Control Bot Oneclick は、小規模な Ubuntu/Debian VPS 向けのセルフホスト型 Telegram 管理パネルです。対話式の `curl` コマンドひとつでインストールでき、Telegram から VPS の状態、サービス、通信量、ログ、購読リンク、Cloudflare 優先 IP 状態、安全クリーンアップを確認できます。

## クイックインストール

```bash
curl -fsSL https://raw.githubusercontent.com/shangguanwt/vps-control-bot-oneclick/main/install.sh | sudo bash
```

インストーラーは次の値を確認します。

- Telegram Bot Token
- 許可する Telegram ユーザー ID
- VPS 表示名
- 任意の購読ベース URL
- 任意のヘルスチェック URL
- 任意の Cloudflare テスト用ホスト名

秘密情報は VPS 上の次のファイルにのみ保存されます。

```bash
/etc/vps-control-bot.env
```

## 主なコマンド

- `/start`, `/panel` - 管理パネルを開く
- `/status` - 負荷、メモリ、ディスク、TCP/BBR
- `/services` - systemd サービスと Docker コンテナ
- `/traffic` - 3X-UI の通信量
- `/sub` - 購読 URL
- `/check` - URL の疎通確認
- `/cf_status` - Cloudflare 優先 IP の状態
- `/cleanup_status` - 安全クリーンアップの状態
- `/cleanup` - 確認後に安全クリーンアップを実行

## 安全クリーンアップ

`vps-safe-cleanup.timer` が毎時実行され、復元可能なキャッシュやログだけを削除します。

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

## セキュリティ

実際の Bot Token、Telegram ID、VPS IP、プライベートドメイン、購読 token、管理パネルのパスを公開しないでください。この bot は任意の shell コマンド実行機能を提供しません。
