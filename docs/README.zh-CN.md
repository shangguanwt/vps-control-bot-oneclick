# VPS Control Bot Oneclick

![VPS Control Bot Oneclick](images/hero.svg)

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](../LICENSE)
[![一键安装](https://img.shields.io/badge/install-curl%20%7C%20bash-0f766e.svg)](../install.sh)
[![Python](https://img.shields.io/badge/python-3.x-blue.svg)](../src/bot.py)
[![Systemd](https://img.shields.io/badge/runtime-systemd-334155.svg)](../systemd/)

一个自托管 Telegram VPS 控制面板。它把常见 VPS 运维动作做成 Telegram 控制台：状态、服务、流量、订阅、日志、备份、Cloudflare 优选状态、安全清理，都可以通过按钮和命令完成。

这个项目的 README 结构参考了 [hotyue/IP-Sentinel](https://github.com/hotyue/IP-Sentinel) 的“部署优先、架构清晰、升级明确”写法，也参考了它的 [节点安装与平滑升级教程](https://blog.iot-architect.com/engineering-practice/ip-sentinel-installation-and-upgrade-guide/)。本项目代码是独立实现，目标是“给普通 VPS 用户一个可一键部署的 Telegram 控制面板”。

## 适用场景

- 你有一台 Ubuntu/Debian VPS，希望手机上随时看状态。
- 你使用 3X-UI / Xray，希望能查看节点流量、订阅地址和服务状态。
- 你希望定时清理 journal、临时文件、APT 缓存和 Docker 日志，防止小内存 VPS 被撑满。
- 你希望所有危险操作都有二次确认，不开放任意 shell。
- 你希望别人也能通过一条 `curl` 命令复刻这套控制面板。

## 效果预览

![Telegram 面板预览](images/panel-preview.svg)

## 核心功能

| 模块 | 功能 |
| --- | --- |
| VPS 控制台 | `/start`、`/panel` 打开 Telegram 控制面板 |
| 系统状态 | `/status` 查看负载、内存、磁盘、Swap、TCP/BBR |
| 服务巡检 | `/services` 查看 systemd 服务和 Docker 容器 |
| 3X-UI 集成 | `/traffic`、`/nodes` 展示流量和节点名 |
| 订阅展示 | `/sub` 展示 Clash/Mihomo、v2rayN 等订阅地址 |
| 健康检查 | `/check` 检查订阅、面板、域名等 URL |
| Cloudflare 优选 | `/cf_status` 查看优选 IP，`/cf_optimize` 执行 VPS 视角测速 |
| 安全清理 | `/cleanup_status` 查看定时器，`/cleanup` 二次确认后手动清理 |
| 日志与备份 | `/logs nginx`、`/logs xui`、`/backup` |

## 架构图

![架构图](images/architecture.svg)

项目只把敏感配置写在 VPS 本地：

```bash
/etc/vps-control-bot.env
```

GitHub 仓库只保存代码、模板和文档，不保存你的 Bot Token、Telegram ID、VPS IP、域名或订阅 token。

## 项目结构

```text
vps-control-bot-oneclick
├── install.sh                         # 交互式一键安装、更新、卸载入口
├── src/
│   ├── bot.py                         # Telegram VPS 控制机器人
│   └── vps-safe-cleanup               # 安全清理脚本
├── systemd/
│   ├── vps-control-bot.service
│   ├── vps-safe-cleanup.service
│   └── vps-safe-cleanup.timer
├── examples/
│   └── vps-control-bot.env.example
├── docs/
│   ├── README.zh-CN.md
│   ├── README.en.md
│   ├── README.ja.md
│   └── images/
├── SECURITY.md
└── LICENSE
```

## 部署前准备

### 1. 系统要求

- Debian / Ubuntu VPS
- root 权限
- 能访问 GitHub Raw
- Python 3
- systemd
- curl

安装脚本会通过 `apt-get` 安装必要依赖。

### 2. 创建 Telegram Bot

在 Telegram 中打开 BotFather：

1. 发送 `/newbot`
2. 输入机器人名称和 username
3. 复制 BotFather 返回的 Bot Token

### 3. 获取 Telegram 用户 ID

可以通过 `@userinfobot` 获取你的个人 Telegram ID。安装时填写到 `ALLOWED_TELEGRAM_IDS`，机器人只响应这个 allowlist 内的用户。

## 一键安装

![部署流程](images/install-flow.svg)

在 VPS 上执行：

```bash
curl -fsSL https://raw.githubusercontent.com/shangguanwt/vps-control-bot-oneclick/main/install.sh | sudo bash
```

安装脚本会交互式询问：

| 配置项 | 说明 |
| --- | --- |
| `BOT_TOKEN` | Telegram Bot Token，必填 |
| `ALLOWED_TELEGRAM_IDS` | 允许操作机器人的 Telegram 用户 ID，必填 |
| `VPS_DISPLAY_NAME` | Telegram 面板里显示的 VPS 名称 |
| `SUB_BASE` | 可选，订阅基础地址 |
| `CHECK_URLS` | 可选，逗号分隔的健康检查 URL |
| `CF_TEST_HOST` | 可选，用于 Cloudflare 优选测速的 SNI 域名 |
| `XUI_DB` | 默认 `/etc/x-ui/x-ui.db` |
| `SUB_GENERATOR` | 默认 `/etc/proxy-subscription/generate.py` |

安装完成后，到 Telegram 里给你的机器人发送：

```text
/start
```

## 安装后验证

```bash
systemctl is-active vps-control-bot
systemctl is-active vps-safe-cleanup.timer
systemctl status vps-control-bot --no-pager
```

Telegram 手动验收：

- `/start` 能看到控制面板
- `/status` 能看到系统资源
- `/services` 能看到服务状态
- `/cleanup_status` 能看到定时清理策略
- 未授权 Telegram ID 无法操作

## 安全清理说明

安装后会启用 `vps-safe-cleanup.timer`，默认每小时运行一次。它只清理可恢复内容：

- systemd journal
- APT 缓存
- `/tmp`、`/var/tmp` 中的旧文件
- 过大的 Docker JSON 日志
- 仅在可用内存低或 Swap 高时处理 page cache

它不会删除用户数据、数据库、Xray 配置、订阅文件或 home 目录。

## 平滑更新

重新执行安装脚本并加 `--update`：

```bash
curl -fsSL https://raw.githubusercontent.com/shangguanwt/vps-control-bot-oneclick/main/install.sh | sudo bash -s -- --update
```

更新会：

- 下载最新 `bot.py`
- 下载最新 `vps-safe-cleanup`
- 刷新 systemd 模板
- 重启 `vps-control-bot`
- 保留 `/etc/vps-control-bot.env`

## 卸载

```bash
curl -fsSL https://raw.githubusercontent.com/shangguanwt/vps-control-bot-oneclick/main/install.sh | sudo bash -s -- --uninstall
```

卸载会移除服务、定时器和安装目录，但默认保留：

```bash
/etc/vps-control-bot.env
```

这样可以避免误删 Bot Token。如果确定不需要，可以手动删除。

## 排障

### 机器人没有回复

```bash
systemctl status vps-control-bot --no-pager
journalctl -u vps-control-bot -n 80 --no-pager
```

检查：

- `BOT_TOKEN` 是否正确
- `ALLOWED_TELEGRAM_IDS` 是否包含你的 Telegram ID
- VPS 是否能访问 `api.telegram.org`

### `/traffic` 没有数据

确认 3X-UI 数据库路径：

```bash
ls -l /etc/x-ui/x-ui.db
```

如果你的路径不同，在 `/etc/vps-control-bot.env` 里修改 `XUI_DB`。

### `/sub` 没有订阅地址

配置 `SUB_BASE`：

```bash
nano /etc/vps-control-bot.env
systemctl restart vps-control-bot
```

### 清理定时器不运行

```bash
systemctl list-timers --all vps-safe-cleanup.timer --no-pager
journalctl -u vps-safe-cleanup.service -n 50 --no-pager
```

## 本地开发检查

```bash
python3 -m py_compile src/bot.py src/vps-safe-cleanup
bash -n install.sh
```

## 安全边界

- 不要提交真实 `BOT_TOKEN`、Telegram ID、VPS IP、私有域名、订阅 token 或面板路径。
- `ALLOWED_TELEGRAM_IDS` 只填写可信用户。
- 机器人不提供任意 shell 命令入口。
- 安装脚本不会开放防火墙端口。
- 重启和清理类动作需要 Telegram 二次确认。

## 参考

- [hotyue/IP-Sentinel](https://github.com/hotyue/IP-Sentinel)
- [IP-Sentinel 节点安装与平滑升级全攻略](https://blog.iot-architect.com/engineering-practice/ip-sentinel-installation-and-upgrade-guide/)
