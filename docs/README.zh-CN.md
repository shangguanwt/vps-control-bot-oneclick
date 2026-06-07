# VPS Control Bot Oneclick

这是一个自托管 Telegram VPS 控制面板，适合小型 Ubuntu/Debian VPS。它可以用一条 `curl` 命令交互式安装，并通过 Telegram 查看状态、服务、流量、日志、订阅、Cloudflare 优选状态和安全清理结果。

## 一键安装

```bash
curl -fsSL https://raw.githubusercontent.com/shangguanwt/vps-control-bot-oneclick/main/install.sh | sudo bash
```

安装脚本会询问：

- Telegram Bot Token
- 允许使用机器人的 Telegram 用户 ID
- VPS 显示名称
- 可选订阅基础地址 `SUB_BASE`
- 可选健康检查 URL
- 可选 Cloudflare 测试域名 `CF_TEST_HOST`

敏感信息只写入 VPS 本地：

```bash
/etc/vps-control-bot.env
```

## 主要功能

- `/start`、`/panel`：打开控制面板
- `/status`：查看负载、内存、磁盘、TCP/BBR
- `/services`：查看 systemd 服务和 Docker 容器
- `/traffic`：读取 3X-UI 流量统计
- `/nodes`：查看订阅节点名称
- `/sub`：展示订阅地址
- `/check`：检查主要 URL 可用性
- `/cf_status`：查看 Cloudflare 优选 IP 状态
- `/cf_optimize`：从 VPS 视角手动测速 Cloudflare IP
- `/cleanup_status`：查看定时安全清理状态
- `/cleanup`：二次确认后立即执行安全清理
- `/backup`：备份关键配置
- `/logs nginx`、`/logs xui`：查看最近日志

## 安全清理

安装后会启用 `vps-safe-cleanup.timer`，默认每小时运行一次。它只清理可恢复内容：

- systemd journal
- APT 缓存
- `/tmp`、`/var/tmp` 中的旧文件
- 过大的 Docker JSON 日志
- 仅在可用内存低或 Swap 高时处理 page cache

它不会删除用户数据、数据库、Xray 配置、订阅文件或 home 目录。

## 更新

```bash
curl -fsSL https://raw.githubusercontent.com/shangguanwt/vps-control-bot-oneclick/main/install.sh | sudo bash -s -- --update
```

更新会刷新程序文件并重启服务，保留 `/etc/vps-control-bot.env`。

## 卸载

```bash
curl -fsSL https://raw.githubusercontent.com/shangguanwt/vps-control-bot-oneclick/main/install.sh | sudo bash -s -- --uninstall
```

卸载默认保留 `/etc/vps-control-bot.env`，避免误删密钥。

## 本地检查

```bash
python3 -m py_compile src/bot.py src/vps-safe-cleanup
bash -n install.sh
```

## 安全边界

- 不要提交真实 `BOT_TOKEN`、Telegram ID、VPS IP、私有域名、订阅 token 或面板路径。
- `ALLOWED_TELEGRAM_IDS` 只填写可信用户。
- 机器人不提供任意 shell 命令入口。
- 安装脚本不会开放防火墙端口。
