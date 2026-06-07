#!/usr/bin/env python3
import datetime as dt
import html
import json
import os
import re
import sqlite3
import subprocess
import sys
import tarfile
import threading
import time
import urllib.request
from pathlib import Path

APP_DIR = Path('/opt/vps-control-bot')
ENV_FILE = Path('/etc/vps-control-bot.env')
LOG_FILE = Path('/var/log/vps-control-bot.log')
SUB_TOKEN = os.environ.get('SUB_TOKEN', 'change-me')
SUB_BASE = os.environ.get('SUB_BASE', '')
ALLOWED_USERS = {x.strip() for x in os.environ.get('ALLOWED_TELEGRAM_IDS', '').split(',') if x.strip()}
XUI_DB = Path(os.environ.get('XUI_DB', '/etc/x-ui/x-ui.db'))
SUB_GENERATOR = Path(os.environ.get('SUB_GENERATOR', '/etc/proxy-subscription/generate.py'))
POLL_TIMEOUT = int(os.environ.get('POLL_TIMEOUT', '30'))
MONITOR_INTERVAL = int(os.environ.get('MONITOR_INTERVAL', '600'))
DAILY_REPORT_HOUR = int(os.environ.get('DAILY_REPORT_HOUR', '9'))
CF_OPTIMIZE_HOUR = int(os.environ.get('CF_OPTIMIZE_HOUR', '4'))
CF_OPTIMIZE_MINUTE = int(os.environ.get('CF_OPTIMIZE_MINUTE', '30'))
MEM_WARN_PERCENT = float(os.environ.get('MEM_WARN_PERCENT', '85'))
DISK_WARN_PERCENT = float(os.environ.get('DISK_WARN_PERCENT', '85'))
LOAD_WARN_PER_CORE = float(os.environ.get('LOAD_WARN_PER_CORE', '1.8'))
ALERT_STATE_FILE = APP_DIR / 'alert-state.json'
CF_BEST_FILE = Path('/etc/proxy-subscription/cf-best-ip.json')
CF_TEST_HOST = os.environ.get('CF_TEST_HOST', '')
CF_TEST_URL = os.environ.get('CF_TEST_URL', f'https://{CF_TEST_HOST}/')
CF_CANDIDATE_LIMIT = int(os.environ.get('CF_CANDIDATE_LIMIT', '24'))
CLEANUP_SCRIPT = Path(os.environ.get('CLEANUP_SCRIPT', '/usr/local/sbin/vps-safe-cleanup'))
CLEANUP_TIMER = os.environ.get('CLEANUP_TIMER', 'vps-safe-cleanup.timer')

ALIASES = json.loads(os.environ.get('NODE_ALIASES_JSON', '{}') or '{}')

SERVICES = ['nginx', 'x-ui', 'docker', 'subconverter', 'ip-sentinel-master', 'vps-control-bot']
CHECK_URLS = [x.strip() for x in os.environ.get('CHECK_URLS', '').split(',') if x.strip()]
if SUB_BASE:
    CHECK_URLS.append(f'{SUB_BASE}-meta.json')

TEXT = {
    'control_title': '\u76ee\u6807\u9501\u5b9a',
    'target': os.environ.get('VPS_DISPLAY_NAME', 'My VPS'),
    'ip_coord': 'IP \u5750\u6807',
    'last': '\u6700\u540e\u901a\u8baf',
    'prompt': '\u8bf7\u4e0b\u8fbe\u7cbe\u786e\u63a7\u5236\u6307\u4ee4\uff1a',
    'core': '\u6838\u5fc3\u670d\u52a1',
    'docker': 'Docker \u5bb9\u5668',
    'traffic': '3X-UI \u7528\u6237\u6d41\u91cf',
    'nodes': '\u5f53\u524d\u8ba2\u9605\u8282\u70b9',
    'sub_all': '\u56fa\u5b9a\u5168\u91cf\u8ba2\u9605',
    'check': '\u53ef\u7528\u6027\u68c0\u67e5',
    'regen_ok': '\u8ba2\u9605\u5df2\u5237\u65b0',
    'regen_fail': '\u5237\u65b0\u8ba2\u9605\u5931\u8d25',
    'not_found_gen': '\u8ba2\u9605\u751f\u6210\u5668\u4e0d\u5b58\u5728',
    'backup_ok': '\u5907\u4efd\u5b8c\u6210',
    'size': '\u5927\u5c0f',
    'usage_logs': '\u7528\u6cd5\uff1a/logs nginx \u6216 /logs xui',
    'recent_logs': '\u6700\u8fd1\u65e5\u5fd7',
    'no_logs': '\u65e0\u65e5\u5fd7',
    'speed_fail': '\u6d4b\u901f\u5931\u8d25',
    'speed_result': 'VPS \u51fa\u53e3\u6d4b\u901f',
    'parse_fail': '\u6d4b\u901f\u7ed3\u679c\u89e3\u6790\u5931\u8d25',
    'confirm': '\u786e\u8ba4\u91cd\u542f',
    'cancel': '\u53d6\u6d88',
    'cancelled': '\u5df2\u53d6\u6d88\u3002',
    'unauth': '\u672a\u6388\u6743\u3002',
    'unknown': '\u672a\u77e5\u547d\u4ee4\u3002\u53d1\u9001 /start \u6253\u5f00\u63a7\u5236\u9762\u677f\u3002',
    'security': '\u5b89\u5168\u9650\u5236\uff1a\u53ea\u54cd\u5e94 allowlist \u7528\u6237\uff0c\u4e0d\u63d0\u4f9b\u4efb\u610f shell \u547d\u4ee4\u3002',
}


def load_env_file(path=ENV_FILE):
    if not path.exists():
        return
    for raw in path.read_text(encoding='utf-8', errors='ignore').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def log(message):
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        stamp = dt.datetime.now(dt.UTC).isoformat().replace('+00:00', 'Z')
        with LOG_FILE.open('a', encoding='utf-8') as f:
            f.write(f'{stamp} {message}\n')
    except Exception:
        pass


def token():
    value = os.environ.get('BOT_TOKEN', '').strip()
    if not value:
        raise RuntimeError('BOT_TOKEN is empty. Edit /etc/vps-control-bot.env first.')
    return value


def api(method, payload=None, timeout=45):
    url = f'https://api.telegram.org/bot{token()}/{method}'
    if payload is None:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8'))
    data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8'))


def send(chat_id, text, reply_markup=None):
    chunks = [text[i:i + 3600] for i in range(0, len(text), 3600)] or ['']
    for i, chunk in enumerate(chunks):
        payload = {'chat_id': chat_id, 'text': chunk, 'parse_mode': 'HTML', 'disable_web_page_preview': True}
        if reply_markup and i == 0:
            payload['reply_markup'] = reply_markup
        api('sendMessage', payload, timeout=20)


def answer_callback(callback_id, text='\u6536\u5230'):
    if callback_id:
        try:
            api('answerCallbackQuery', {'callback_query_id': callback_id, 'text': text, 'show_alert': False}, timeout=10)
        except Exception as exc:
            log(f'answerCallbackQuery failed: {exc}')


def run(cmd, timeout=20):
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=timeout)
    return proc.returncode, proc.stdout.strip()


def human_bytes(value):
    try:
        n = float(value)
    except Exception:
        return str(value)
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if n < 1024 or unit == 'TB':
            return f'{n:.1f}{unit}' if unit != 'B' else f'{int(n)}B'
        n /= 1024


def esc(value):
    return html.escape(str(value), quote=False)


def line(label, value):
    return f'<b>{esc(label)}</b>  {esc(value)}'


def row(icon, label, value):
    return f'{esc(icon)} <b>{esc(label)}</b>  {esc(value)}'


def code_value(value):
    return f'<code>{esc(value)}</code>'


def pre_block(value):
    return f'<pre>{esc(value)}</pre>'


def bar(percent, width=10):
    try:
        pct = max(0, min(100, float(percent)))
    except Exception:
        pct = 0
    filled = round(pct / 100 * width)
    return ('█' * filled) + ('░' * (width - filled)) + f' {pct:.0f}%'


def divider():
    return '━━━━━━━━━━━━━━'


def badge(state):
    raw = (state or '').strip().lower()
    if raw in {'active', 'running', 'up', 'healthy', 'ok', 'enabled', 'on'} or raw.startswith('up '):
        return 'OK'
    if raw in {'inactive', 'exited', 'disabled', 'off'}:
        return 'WARN'
    if raw in {'failed', 'dead', 'error', 'unhealthy'}:
        return 'FAIL'
    return 'INFO'


def page_keyboard(refresh_key=None, extra_rows=None):
    rows = []
    if extra_rows:
        rows.extend(extra_rows)
    nav = []
    if refresh_key:
        nav.append({'text': '刷新本页', 'callback_data': f'refresh:{refresh_key}'})
    nav.append({'text': '返回面板', 'callback_data': 'panel:home'})
    rows.append(nav)
    return {'inline_keyboard': rows}


def sub_keyboard():
    if not SUB_BASE:
        return page_keyboard('sub', [
            [{'text': '刷新订阅文件', 'callback_data': 'cmd:regen_sub'}],
        ])
    return page_keyboard('sub', [
        [{'text': '打开 YAML 全量订阅', 'url': f'{SUB_BASE}-all.yaml'}],
        [{'text': '打开 B64 全量订阅', 'url': f'{SUB_BASE}-all.b64'}],
        [{'text': '刷新订阅文件', 'callback_data': 'cmd:regen_sub'}],
    ])


def cf_keyboard():
    return {'inline_keyboard': [
        [{'text': '查看本机优选结果', 'callback_data': 'cmd:cf_status'}, {'text': 'VPS 视角优选', 'callback_data': 'cmd:cf_optimize'}],
        [{'text': '刷新订阅', 'callback_data': 'cmd:regen_sub'}, {'text': '返回面板', 'callback_data': 'panel:home'}],
    ]}


def nodes_keyboard():
    return {'inline_keyboard': [
        [{'text': '节点流量', 'callback_data': 'cmd:traffic'}, {'text': '节点列表', 'callback_data': 'cmd:nodes'}],
        [{'text': '订阅地址', 'callback_data': 'cmd:sub'}, {'text': 'CF 优选 IP', 'callback_data': 'menu:cf'}],
        [{'text': '刷新订阅', 'callback_data': 'cmd:regen_sub'}],
        [{'text': '返回面板', 'callback_data': 'panel:home'}],
    ]}


def logs_keyboard():
    return {'inline_keyboard': [
        [{'text': 'Nginx 日志', 'callback_data': 'cmd:logs_nginx'}, {'text': '3X-UI 日志', 'callback_data': 'cmd:logs_xui'}],
        [{'text': 'Docker 日志', 'callback_data': 'cmd:logs_docker'}, {'text': 'Subconverter 日志', 'callback_data': 'cmd:logs_sub'}],
        [{'text': '返回面板', 'callback_data': 'panel:home'}],
    ]}


def maintenance_keyboard():
    return {'inline_keyboard': [
        [{'text': '清理状态', 'callback_data': 'cmd:cleanup_status'}, {'text': '立即安全清理', 'callback_data': 'confirm:cleanup'}],
        [{'text': '备份配置', 'callback_data': 'cmd:backup'}, {'text': '出口测速', 'callback_data': 'cmd:speedtest'}],
        [{'text': '重载 Nginx', 'callback_data': 'confirm:nginx'}, {'text': '重启 3X-UI', 'callback_data': 'confirm:xui'}],
        [{'text': '重启 Subconverter', 'callback_data': 'confirm:sub'}],
        [{'text': '返回面板', 'callback_data': 'panel:home'}],
    ]}


def cleanup_keyboard():
    return {'inline_keyboard': [
        [{'text': '刷新清理状态', 'callback_data': 'refresh:cleanup_status'}, {'text': '立即安全清理', 'callback_data': 'confirm:cleanup'}],
        [{'text': '返回维护', 'callback_data': 'menu:maintenance'}, {'text': '返回面板', 'callback_data': 'panel:home'}],
    ]}


def reports_keyboard():
    return {'inline_keyboard': [
        [{'text': '立即巡检报告', 'callback_data': 'cmd:report'}, {'text': '域名检查', 'callback_data': 'cmd:check'}],
        [{'text': '状态概览', 'callback_data': 'cmd:status'}, {'text': '服务巡检', 'callback_data': 'cmd:services'}],
        [{'text': '返回面板', 'callback_data': 'panel:home'}],
    ]}


def get_public_ip():
    _, ip = run(['bash', '-lc', "curl -4 -s --max-time 5 https://api.ipify.org || hostname -I | awk '{print $1}'"], 8)
    return ip or 'unknown'


def service_states():
    states = {}
    for service in SERVICES:
        _, state = run(['systemctl', 'is-active', service], 8)
        states[service] = state.strip() or 'unknown'
    return states


def docker_states():
    _, docker = run(['bash', '-lc', "docker ps --format '{{.Names}} | {{.Status}}' 2>/dev/null"], 12)
    rows = []
    for item in docker.splitlines():
        name, _, state = item.partition(' | ')
        if name:
            rows.append((name, state or 'unknown'))
    return rows


def system_metrics():
    _, uptime = run(['bash', '-lc', 'uptime -p; uptime | sed "s/^ //"'], 10)
    _, loadavg = run(['cat', '/proc/loadavg'], 5)
    _, cores = run(['bash', '-lc', 'nproc 2>/dev/null || echo 1'], 5)
    _, mem = run(['bash', '-lc', "free -b | awk '/Mem:/ {printf \"%s %s %s\", $3, $2, $7}'"], 5)
    _, swap = run(['bash', '-lc', "free -h | awk '/Swap:/ {print $3\" / \"$2}'"], 5)
    _, disk = run(['bash', '-lc', "df -B1 / | awk 'NR==2{printf \"%s %s %s\", $3, $2, $4}'"], 5)
    _, bbr = run(['bash', '-lc', 'sysctl -n net.ipv4.tcp_congestion_control 2>/dev/null; sysctl -n net.core.default_qdisc 2>/dev/null'], 5)
    mem_parts = mem.split()
    disk_parts = disk.split()
    used_mem = total_mem = available_mem = 0
    used_disk = total_disk = free_disk = 0
    if len(mem_parts) == 3 and mem_parts[1].isdigit():
        used_mem, total_mem, available_mem = map(int, mem_parts)
    if len(disk_parts) == 3 and disk_parts[1].isdigit():
        used_disk, total_disk, free_disk = map(int, disk_parts)
    load_parts = loadavg.split()
    try:
        load1 = float(load_parts[0])
    except Exception:
        load1 = 0.0
    try:
        cpu_cores = max(1, int(cores.strip()))
    except Exception:
        cpu_cores = 1
    uptime_lines = [x.strip() for x in uptime.splitlines() if x.strip()]
    bbr_lines = [x for x in bbr.splitlines() if x.strip()]
    return {
        'uptime': uptime_lines[0] if uptime_lines else 'unknown',
        'loadavg': loadavg,
        'load1': load1,
        'cores': cpu_cores,
        'mem_used': used_mem,
        'mem_total': total_mem,
        'mem_available': available_mem,
        'mem_pct': (used_mem / total_mem * 100) if total_mem else 0,
        'swap': swap or 'unknown',
        'disk_used': used_disk,
        'disk_total': total_disk,
        'disk_free': free_disk,
        'disk_pct': (used_disk / total_disk * 100) if total_disk else 0,
        'tcp': ' / '.join(bbr_lines) if bbr_lines else 'unknown',
    }


def traffic_rows():
    if not XUI_DB.exists():
        return None
    con = sqlite3.connect(str(XUI_DB))
    try:
        rows = con.execute('select email,up,down,total,enable from client_traffics order by (up+down) desc').fetchall()
    finally:
        con.close()
    result = []
    for email, up, down, total, enable in rows:
        name = ALIASES.get(email, email)
        kind = '家宽' if '家宽' in name or 'socks' in email.lower() else 'VPS'
        result.append({
            'email': email,
            'name': name,
            'kind': kind,
            'up': up or 0,
            'down': down or 0,
            'used': (up or 0) + (down or 0),
            'total': total or 0,
            'enable': bool(enable),
        })
    return result


def cf_candidate_ips(limit=CF_CANDIDATE_LIMIT):
    import ipaddress
    urls = [
        'https://www.cloudflare.com/ips-v4/',
        'https://api.cloudflare.com/client/v4/ips',
    ]
    nets = []
    for url in urls:
        try:
            with urllib.request.urlopen(url, timeout=15) as resp:
                body = resp.read().decode('utf-8', 'replace')
            if 'result' in body and url.endswith('/ips'):
                data = json.loads(body)
                nets = [ipaddress.ip_network(x) for x in data.get('result', {}).get('ipv4_cidrs', [])]
            else:
                nets = [ipaddress.ip_network(x.strip()) for x in body.splitlines() if x.strip()]
            if nets:
                break
        except Exception as exc:
            log(f'fetch cf ips failed from {url}: {exc}')
    if not nets:
        nets = [ipaddress.ip_network(x) for x in ['104.16.0.0/13', '104.24.0.0/14', '172.64.0.0/13', '188.114.96.0/20']]
    candidates = []
    for net in nets:
        size = int(net.num_addresses)
        if size <= 2:
            continue
        for ratio in (0.18, 0.35, 0.52, 0.69, 0.86):
            idx = max(1, min(size - 2, int(size * ratio)))
            candidates.append(str(net.network_address + idx))
            if len(candidates) >= limit:
                return candidates
    return candidates[:limit]


def test_cf_ip(ip):
    if not CF_TEST_HOST:
        return {'ip': ip, 'ok': False, 'score': 999.0, 'raw': 'CF_TEST_HOST is not configured'}
    cmd = [
        'curl', '-k', '-L', '--connect-timeout', '4', '--max-time', '10',
        '--connect-to', f'{CF_TEST_HOST}:443:{ip}:443',
        '-o', '/dev/null', '-sS', '-w', 'code=%{http_code} connect=%{time_connect} appconnect=%{time_appconnect} total=%{time_total}',
        CF_TEST_URL,
    ]
    code, out = run(cmd, 15)
    ok = code == 0 and ('code=2' in out or 'code=3' in out or 'code=404' in out)
    score = 999.0
    m = re.search(r'total=([0-9.]+)', out)
    if m:
        try:
            score = float(m.group(1))
        except Exception:
            pass
    return {'ip': ip, 'ok': ok, 'score': score, 'raw': out or 'failed'}


def cf_optimize(apply=True):
    if not CF_TEST_HOST:
        return {
            'enabled': False,
            'host': '',
            'url': '',
            'generated_at': int(time.time()),
            'ip': '',
            'best': None,
            'top': [],
            'tested': 0,
            'reason': 'CF_TEST_HOST is not configured',
        }
    candidates = cf_candidate_ips()
    results = [test_cf_ip(ip) for ip in candidates]
    good = sorted([x for x in results if x['ok']], key=lambda x: x['score'])
    best = good[0] if good else None
    payload = {
        'enabled': bool(best),
        'host': CF_TEST_HOST,
        'url': CF_TEST_URL,
        'generated_at': int(time.time()),
        'ip': best['ip'] if best else '',
        'best': best,
        'top': good[:8],
        'tested': len(results),
    }
    if apply and best:
        CF_BEST_FILE.parent.mkdir(parents=True, exist_ok=True)
        CF_BEST_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        if SUB_GENERATOR.exists():
            run([str(SUB_GENERATOR)], 40)
    return payload


def load_cf_status():
    try:
        return json.loads(CF_BEST_FILE.read_text(encoding='utf-8'))
    except Exception:
        return None


def cf_status_text(data=None, title='Cloudflare 优选 IP'):
    data = data or load_cf_status()
    if not data:
        return f'⚡ <b>{esc(title)}</b>\n{divider()}\n当前还没有优选结果。可以点击“立即优选 IP”。'
    best = data.get('best') or {}
    ts = data.get('generated_at') or 0
    when = dt.datetime.fromtimestamp(ts, dt.UTC).strftime('%Y-%m-%d %H:%M:%S UTC') if ts else 'unknown'
    tested_at = data.get('tested_at') or ts
    tested_when = dt.datetime.fromtimestamp(tested_at, dt.UTC).strftime('%Y-%m-%d %H:%M:%S UTC') if tested_at else 'unknown'
    score = data.get('score')
    if score is None:
        score = best.get('score')
    try:
        score_text = f'{float(score):.3f}s'
    except Exception:
        score_text = 'unknown'
    source = data.get('source') or 'unknown'
    source_label = 'Windows 本机直连' if 'windows-local' in source else 'VPS 视角'
    switched = data.get('switched')
    if switched is True:
        switch_text = '已切换'
    elif switched is False:
        switch_text = '保留当前 IP'
    else:
        switch_text = '未记录'
    reason = data.get('reason') or '-'
    last_failure = data.get('last_failure') or data.get('failure') or ''
    lines = [
        f'⚡ <b>{esc(title)}</b>',
        divider(),
        f'{row("🌐", "域名", data.get("host") or CF_TEST_HOST)}',
        f'{row("🏆", "当前 IP", data.get("ip") or "未启用")}',
        f'{row("🧭", "来源", source_label)}',
        f'{row("⏱️", "本机耗时", score_text)}',
        f'{row("🔁", "切换策略", switch_text)}',
        f'{row("📌", "原因", reason)}',
        f'{row("🕒", "更新时间", when)}',
        f'{row("🧪", "本机测速时间", tested_when)}',
        f'{row("📊", "测试数量", data.get("tested", 0) if data.get("tested") is not None else "unknown")}',
        '',
        '📋 <b>Top 候选</b>',
    ]
    if last_failure:
        lines.insert(-1, f'{row("⚠️", "最近失败", last_failure)}')
    top = data.get('top') or []
    if top:
        for item in top[:5]:
            try:
                item_score = f'{float(item.get("score")):.3f}s'
            except Exception:
                item_score = 'unknown'
            lines.append(f'✅ {esc(item.get("ip", ""))}  {esc(item_score)}  {esc(item.get("raw", ""))}')
    else:
        lines.append('暂无可用候选。')
    lines.append('\n说明：订阅里的连接地址使用优选 IP，SNI/Host 仍保持原域名。Reality 直连节点不改。')
    return '\n'.join(lines)


def check_results():
    rows = []
    for url in CHECK_URLS:
        cmd = ['curl', '-k', '-L', '--connect-timeout', '8', '--max-time', '18', '-o', '/dev/null', '-sS', '-w', 'code=%{http_code} total=%{time_total}', url]
        _, out = run(cmd, 25)
        ok = 'code=2' in out or 'code=3' in out
        rows.append({'url': url, 'ok': ok, 'raw': out if out else 'failed'})
    return rows


def panel_keyboard():
    return {'inline_keyboard': [
        [{'text': '状态', 'callback_data': 'cmd:status'}, {'text': '服务', 'callback_data': 'cmd:services'}],
        [{'text': '节点与订阅', 'callback_data': 'menu:nodes'}, {'text': '巡检报告', 'callback_data': 'menu:reports'}],
        [{'text': '日志', 'callback_data': 'menu:logs'}, {'text': '维护', 'callback_data': 'menu:maintenance'}],
    ]}


def panel_text():
    ip = get_public_ip()
    now = dt.datetime.now(dt.UTC).strftime('%Y-%m-%d %H:%M:%S UTC')
    states = service_states()
    active = sum(1 for state in states.values() if state == 'active')
    return (
        '🛰️ <b>VPS 控制台</b>\n'
        f'{divider()}\n'
        f'{row("🎯", TEXT["control_title"], TEXT["target"])}\n'
        f'{row("🌐", TEXT["ip_coord"], ip)}\n'
        f'{row("🧩", "核心服务", f"{active}/{len(SERVICES)} active")}\n'
        f'{row("🕒", TEXT["last"], now)}\n\n'
        f'👇 {esc(TEXT["prompt"])}'
    )


def help_text():
    return (
        '🤖 <b>VPS Control Bot</b>\n'
        f'{divider()}\n\n'
        f'{code_value("/status")} VPS 负载、内存、磁盘、BBR\n'
        f'{code_value("/services")} 核心服务和 Docker 容器\n'
        f'{code_value("/traffic")} 3X-UI 用户流量\n'
        f'{code_value("/nodes")} 当前订阅节点名\n'
        f'{code_value("/sub")} 固定订阅地址\n'
        f'{code_value("/cf_status")} Cloudflare 优选 IP 状态\n'
        f'{code_value("/cf_optimize")} 立即执行 CF 优选并刷新订阅\n'
        f'{code_value("/check")} 检查主要域名和订阅\n'
        f'{code_value("/report")} 即时巡检报告\n'
        f'{code_value("/regen_sub")} 立即刷新订阅文件\n'
        f'{code_value("/cleanup_status")} 定时清理状态\n'
        f'{code_value("/backup")} 备份关键配置\n'
        f'{code_value("/logs nginx")} 最近 Nginx 日志\n'
        f'{code_value("/logs xui")} 最近 3X-UI 日志\n'
        f'{code_value("/speedtest")} VPS 出口测速\n\n'
        '🛡️ <b>危险操作会二次确认</b>\n'
        f'{code_value("/cleanup")} / {code_value("/restart_nginx")} / {code_value("/restart_xui")} / {code_value("/restart_sub")}\n\n'
        + esc(TEXT['security'])
    )


def status_text():
    metrics = system_metrics()
    states = service_states()
    active = sum(1 for state in states.values() if state == 'active')
    mem_line = f'{bar(metrics["mem_pct"])}  {human_bytes(metrics["mem_used"])} / {human_bytes(metrics["mem_total"])}  可用 {human_bytes(metrics["mem_available"])}'
    disk_line = f'{bar(metrics["disk_pct"])}  {human_bytes(metrics["disk_used"])} / {human_bytes(metrics["disk_total"])}  可用 {human_bytes(metrics["disk_free"])}'
    return (
        '📊 <b>VPS 状态概览</b>\n'
        f'{divider()}\n'
        f'{row("🎯", "主机", TEXT["target"])}\n'
        f'{row("🌐", "公网 IP", get_public_ip())}\n'
        f'{row("🧩", "核心服务", f"{active}/{len(SERVICES)} active")}\n\n'
        '🖥️ <b>系统</b>\n'
        f'{row("⏱️", "运行时间", metrics["uptime"])}\n'
        f'{row("📈", "负载", f"{metrics["loadavg"]} / {metrics["cores"]} cores")}\n'
        '\n'
        '💾 <b>资源</b>\n'
        f'{row("🧠", "内存", mem_line)}\n'
        f'{row("🔁", "Swap", metrics["swap"])}\n'
        f'{row("💽", "磁盘 /", disk_line)}\n\n'
        '🚀 <b>网络栈</b>\n'
        f'{row("📡", "TCP", metrics["tcp"])}'
    )


def services_text():
    lines = ['🧭 <b>服务巡检</b>', divider(), '', '🧩 <b>核心服务</b>']
    for service, state in service_states().items():
        icon = '✅' if badge(state) == 'OK' else '⚠️' if badge(state) == 'WARN' else '❌'
        lines.append(f'{icon} {code_value(badge(state))} <b>{esc(service)}</b>  {esc(state)}')
    docker = docker_states()
    if docker:
        lines.append('')
        lines.append(f'🐳 <b>{esc(TEXT["docker"])}</b>')
        for name, state in docker:
            icon = '✅' if badge(state) == 'OK' else '⚠️' if badge(state) == 'WARN' else '❌'
            lines.append(f'{icon} {code_value(badge(state))} <b>{esc(name)}</b>  {esc(state)}')
    return '\n'.join(lines)


def traffic_text():
    rows = traffic_rows()
    if rows is None:
        return f'📶 <b>节点流量</b>\n{divider()}\n没有找到 3X-UI 数据库：{code_value(XUI_DB)}'
    if not rows:
        return f'📶 <b>节点流量</b>\n{divider()}\n3X-UI 暂无流量记录。'
    enabled = sum(1 for item in rows if item['enable'])
    total_used = sum(item['used'] for item in rows)
    lines = [
        f'📶 <b>{esc(TEXT["traffic"])}</b>',
        divider(),
        f'{row("📦", "累计总量", human_bytes(total_used))}',
        f'{row("🟢", "启用节点", f"{enabled}/{len(rows)}")}',
        '',
        '🏆 <b>流量排行</b>',
    ]
    for item in rows[:8]:
        state = 'ON' if item['enable'] else 'OFF'
        limit = '不限' if not item['total'] else human_bytes(item['total'])
        kind = item['kind']
        lines.append(
            f'\n{"🏠" if kind == "家宽" else "🛰️"} <b>{esc(item["name"])}</b>  {code_value(kind)} {code_value(state)}\n'
            f'⬆️ 上行 {esc(human_bytes(item["up"]))}   ⬇️ 下行 {esc(human_bytes(item["down"]))}\n'
            f'📦 累计 {esc(human_bytes(item["used"]))}   🎚️ 限额 {esc(limit)}'
        )
    return '\n'.join(lines)


def nodes_text():
    meta = Path(f'/var/www/html/proxy-subscription/{SUB_TOKEN}-meta.json')
    names = []
    if meta.exists():
        try:
            names = json.loads(meta.read_text(encoding='utf-8')).get('names') or []
        except Exception:
            names = []
    if not names:
        names = list(ALIASES.values())
    rows = []
    for name in names:
        kind = '家宽' if '家宽' in name else 'VPS'
        icon = '🏠' if kind == '家宽' else '🛰️'
        rows.append(f'{icon} {code_value(kind)} {esc(name)}')
    return f'🧬 <b>{esc(TEXT["nodes"])}</b>\n{divider()}\n' + '\n'.join(rows)


def sub_text():
    if not SUB_BASE:
        return (
            f'🔗 <b>{esc(TEXT["sub_all"])}</b>\n'
            f'{divider()}\n'
            '尚未配置订阅地址。请在 /etc/vps-control-bot.env 中设置 SUB_BASE。'
        )
    return (
        f'🔗 <b>{esc(TEXT["sub_all"])}</b>\n'
        f'{divider()}\n'
        f'{row("🧭", "Mihomo / Clash Verge / FlClash", f"{SUB_BASE}-all.yaml")}\n'
        f'{row("📦", "v2rayN / NekoBox / Nekoray", f"{SUB_BASE}-all.b64")}\n\n'
        '🗂️ <b>分组订阅</b>\n'
        f'{row("⚡", "高速订阅", f"{SUB_BASE}-fast.yaml")}\n'
        f'{row("⚡", "高速 B64", f"{SUB_BASE}-fast.b64")}\n'
        f'{row("🏠", "家宽订阅", f"{SUB_BASE}-socks.yaml")}\n'
        f'{row("🏠", "家宽 B64", f"{SUB_BASE}-socks.b64")}\n\n'
        '👇 下方按钮可以直接打开全量订阅地址。'
    )


def check_text():
    lines = [f'🩺 <b>{esc(TEXT["check"])}</b>', divider()]
    for item in check_results():
        ok = 'OK' if item['ok'] else 'FAIL'
        icon = '✅' if ok == 'OK' else '❌'
        lines.append(f'\n{icon} {code_value(ok)} {esc(item["url"])}\n⏱️ {esc(item["raw"])}')
    return '\n'.join(lines)


def regen_sub_text():
    if not SUB_GENERATOR.exists():
        return f'⚠️ <b>{esc(TEXT["not_found_gen"])}</b>\n{code_value(SUB_GENERATOR)}'
    code, out = run([str(SUB_GENERATOR)], 30)
    if code != 0:
        return f'❌ <b>{esc(TEXT["regen_fail"])}</b>\n' + pre_block(out[-1200:])
    return f'✅ <b>{esc(TEXT["regen_ok"])}</b>\n' + pre_block(out[-1200:] or 'done')


def parse_cleanup_json(args, timeout=40):
    if not CLEANUP_SCRIPT.exists():
        return None, f'cleanup script not found: {CLEANUP_SCRIPT}'
    code, out = run([str(CLEANUP_SCRIPT)] + args + ['--json'], timeout)
    if code != 0:
        return None, out or f'exit code {code}'
    try:
        return json.loads(out), ''
    except Exception as exc:
        return None, f'parse cleanup json failed: {exc}\n{out[-1000:]}'


def cleanup_time(ts):
    try:
        return dt.datetime.fromtimestamp(int(ts), dt.UTC).strftime('%Y-%m-%d %H:%M:%S UTC')
    except Exception:
        return 'unknown'


def cleanup_status_text():
    data, err = parse_cleanup_json(['--status'], 35)
    if not data:
        return f'🧹 <b>清理状态</b>\n{divider()}\n❌ {esc(err)}'
    current = data.get('current', {})
    mem = current.get('memory', {})
    disk = current.get('disk', {})
    policy = data.get('policy', {})
    last = data.get('last') or {}
    _, timer_state = run(['systemctl', 'is-active', CLEANUP_TIMER], 8)
    _, next_run = run(['bash', '-lc', f"systemctl list-timers --all {CLEANUP_TIMER} --no-pager --no-legend | awk '{{print $1\" \"$2\" \"$3\" \"$4\" \"$5\" \"$6}}'"], 10)
    lines = [
        '🧹 <b>VPS 安全清理状态</b>',
        divider(),
        f'{row("🧠", "当前内存", f"{mem.get("mem_available_mb", "?")}MB 可用 / 已用 {mem.get("mem_used_percent", "?")}%")}',
        f'{row("🔁", "Swap", f"{mem.get("swap_used_mb", "?")}MB / {mem.get("swap_used_percent", "?")}%")}',
        f'{row("💽", "磁盘 /", f"{disk.get("used_percent", "?")} 已用，可用 {human_bytes(disk.get("available", 0))}")}',
        f'{row("📜", "Journal", current.get("journal", "unknown"))}',
        '',
        '⏱️ <b>定时策略</b>',
        f'{row("🟢", "Timer", f"{CLEANUP_TIMER} = {timer_state or "unknown"}")}',
        f'{row("🗓️", "下次运行", next_run or "unknown")}',
        f'{row("📏", "日志保留", f"{policy.get("journal_max_size")} / {policy.get("journal_max_age")}")}',
        f'{row("🧪", "触发阈值", f"可用内存低于 {policy.get("min_available_mb")}MB 或 Swap 高于 {policy.get("max_swap_percent")}%")}',
    ]
    if last:
        after_mem = (last.get('after') or {}).get('memory', {})
        actions = last.get('actions') or []
        ok_actions = sum(1 for item in actions if item.get('ok'))
        lines.extend([
            '',
            '📌 <b>最近一次清理</b>',
            f'{row("🕒", "时间", cleanup_time(last.get("ran_at")))}',
            f'{row("✅", "结果", "OK" if last.get("ok") else "WARN")}',
            f'{row("🧠", "清理后内存", f"{after_mem.get("mem_available_mb", "?")}MB 可用")}',
            f'{row("🧩", "动作", f"{ok_actions}/{len(actions)} ok")}',
        ])
    else:
        lines.extend(['', '📌 <b>最近一次清理</b>', '还没有记录。'])
    return '\n'.join(lines)


def cleanup_text(force=True):
    data, err = parse_cleanup_json(['--force'] if force else [], 140)
    if not data:
        return f'🧹 <b>安全清理失败</b>\n{divider()}\n❌ {esc(err)}'
    before_mem = (data.get('before') or {}).get('memory', {})
    after_mem = (data.get('after') or {}).get('memory', {})
    before_disk = (data.get('before') or {}).get('disk', {})
    after_disk = (data.get('after') or {}).get('disk', {})
    actions = data.get('actions') or []
    lines = [
        '🧹 <b>安全清理已执行</b>' if data.get('ok') else '⚠️ <b>安全清理完成但有警告</b>',
        divider(),
        f'{row("🕒", "时间", cleanup_time(data.get("ran_at")))}',
        f'{row("🧠", "内存", f"{before_mem.get("mem_available_mb", "?")}MB -> {after_mem.get("mem_available_mb", "?")}MB 可用")}',
        f'{row("🔁", "Swap", f"{before_mem.get("swap_used_mb", "?")}MB -> {after_mem.get("swap_used_mb", "?")}MB 已用")}',
        f'{row("💽", "磁盘", f"{before_disk.get("used_percent", "?")} -> {after_disk.get("used_percent", "?")} 已用")}',
        f'{row("📜", "Journal", (data.get("after") or {}).get("journal", "unknown"))}',
        '',
        '📋 <b>动作摘要</b>',
    ]
    for item in actions[:8]:
        icon = '⏭️' if item.get('skipped') else '✅' if item.get('ok') else '❌'
        lines.append(f'{icon} {esc(item.get("name", "action"))}')
    return '\n'.join(lines)


def backup_text():
    backup_dir = Path('/root/vps-control-bot-backups')
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now(dt.UTC).strftime('%Y%m%d-%H%M%S')
    out = backup_dir / f'vps-config-{ts}.tgz'
    paths = ['/etc/x-ui/x-ui.db', '/etc/nginx/nginx.conf', '/etc/nginx/conf.d/subconverter.conf', '/etc/proxy-subscription/generate.py', '/etc/cron.d/proxy-subscription', '/etc/vps-control-bot.env', '/opt/vps-control-bot/bot.py']
    with tarfile.open(out, 'w:gz') as tar:
        for path in paths:
            if os.path.exists(path):
                tar.add(path, arcname=path.lstrip('/'))
    return (
        f'📦 <b>{esc(TEXT["backup_ok"])}</b>\n'
        f'{divider()}\n'
        f'{row("📁", "路径", out)}\n'
        f'{row("📏", TEXT["size"], human_bytes(out.stat().st_size))}'
    )


def logs_text(which):
    units = {'nginx': 'nginx', 'xui': 'x-ui', 'x-ui': 'x-ui', 'docker': 'docker', 'sub': 'subconverter'}
    unit = units.get((which or '').lower())
    if not unit:
        return f'📜 <b>日志查看</b>\n{divider()}\n{esc(TEXT["usage_logs"])}'
    _, out = run(['journalctl', '-u', unit, '--since', '2 hours ago', '--no-pager', '-n', '40'], 15)
    return f'📜 <b>{esc(unit)} {esc(TEXT["recent_logs"])}</b>\n{divider()}\n' + pre_block(out[-3200:] if out else TEXT['no_logs'])


def speedtest_text():
    code, out = run(['bash', '-lc', 'timeout 100 speedtest --accept-license --accept-gdpr --format=json 2>/tmp/vps-control-speedtest.err'], 110)
    if code != 0 or not out:
        err_file = Path('/tmp/vps-control-speedtest.err')
        err = err_file.read_text(errors='ignore') if err_file.exists() else ''
        return f'❌ <b>{esc(TEXT["speed_fail"])}</b>\n' + pre_block(err[-1000:] or out[-1000:])
    try:
        data = json.loads(out)
        down = data.get('download', {}).get('bandwidth', 0) * 8 / 1_000_000
        up = data.get('upload', {}).get('bandwidth', 0) * 8 / 1_000_000
        ping = data.get('ping', {}).get('latency')
        server = data.get('server', {})
        return (
            f'🚀 <b>{esc(TEXT["speed_result"])}</b>\n'
            f'{divider()}\n'
            f'{row("⬇️", "Download", f"{down:.1f} Mbps")}\n'
            f'{row("⬆️", "Upload", f"{up:.1f} Mbps")}\n'
            f'{row("📍", "Ping", f"{ping} ms")}\n'
            f'{row("🧭", "Server", f"{server.get("name", "?")} / {server.get("location", "?")}")}'
        )
    except Exception:
        return f'⚠️ <b>{esc(TEXT["parse_fail"])}</b>\n' + pre_block(out[-1500:])


def report_text(title='每日巡检报告'):
    metrics = system_metrics()
    states = service_states()
    docker = docker_states()
    traffic = traffic_rows() or []
    checks = check_results()
    failed_services = [name for name, state in states.items() if state != 'active']
    failed_checks = [item for item in checks if not item['ok']]
    active = len(states) - len(failed_services)
    total_used = sum(item['used'] for item in traffic)
    top = traffic[:3]
    lines = [
        f'🧾 <b>{esc(title)}</b>',
        divider(),
        f'{row("🕒", "时间", dt.datetime.now(dt.UTC).strftime("%Y-%m-%d %H:%M:%S UTC"))}',
        f'{row("🎯", "主机", TEXT["target"])}',
        '',
        '📊 <b>系统摘要</b>',
        f'{row("⏱️", "运行时间", metrics["uptime"])}',
        f'{row("📈", "负载", f"{metrics["load1"]:.2f} / {metrics["cores"]} cores")}',
        f'{row("🧠", "内存", f"{bar(metrics["mem_pct"])}  {human_bytes(metrics["mem_used"])} / {human_bytes(metrics["mem_total"])}")}',
        f'{row("💽", "磁盘", f"{bar(metrics["disk_pct"])}  {human_bytes(metrics["disk_used"])} / {human_bytes(metrics["disk_total"])}")}',
        '',
        '🧩 <b>服务摘要</b>',
        f'{row("✅", "核心服务", f"{active}/{len(states)} active")}',
        f'{row("🐳", "Docker 容器", f"{len(docker)} running")}',
        f'{row("🩺", "地址检查", f"{len(checks) - len(failed_checks)}/{len(checks)} ok")}',
        '',
        '📶 <b>流量摘要</b>',
        f'{row("📦", "累计总量", human_bytes(total_used))}',
    ]
    if top:
        lines.append('🏆 <b>Top 节点</b>')
        for item in top:
            icon = '🏠' if item['kind'] == '家宽' else '🛰️'
            lines.append(f'{icon} {esc(item["name"])}  {esc(human_bytes(item["used"]))}')
    if failed_services or failed_checks:
        lines.extend(['', '⚠️ <b>需要关注</b>'])
        for name in failed_services:
            lines.append(f'❌ 服务异常：{esc(name)} = {esc(states[name])}')
        for item in failed_checks:
            lines.append(f'❌ 地址异常：{esc(item["url"])}  {esc(item["raw"])}')
    else:
        lines.extend(['', '✅ <b>结论</b>  当前巡检未发现明显异常。'])
    return '\n'.join(lines)


def load_alert_state():
    try:
        return json.loads(ALERT_STATE_FILE.read_text(encoding='utf-8')) if ALERT_STATE_FILE.exists() else {}
    except Exception:
        return {}


def save_alert_state(state):
    try:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        ALERT_STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception as exc:
        log(f'save alert state failed: {exc}')


def current_alerts():
    alerts = {}
    metrics = system_metrics()
    if metrics['mem_pct'] >= MEM_WARN_PERCENT:
        alerts['mem'] = f'内存占用 {metrics["mem_pct"]:.0f}%：{human_bytes(metrics["mem_used"])} / {human_bytes(metrics["mem_total"])}'
    if metrics['disk_pct'] >= DISK_WARN_PERCENT:
        alerts['disk'] = f'磁盘占用 {metrics["disk_pct"]:.0f}%：{human_bytes(metrics["disk_used"])} / {human_bytes(metrics["disk_total"])}'
    if metrics['load1'] >= metrics['cores'] * LOAD_WARN_PER_CORE:
        alerts['load'] = f'1 分钟负载 {metrics["load1"]:.2f}，CPU cores {metrics["cores"]}'
    for name, state in service_states().items():
        if state != 'active':
            alerts[f'service:{name}'] = f'服务异常 {name}: {state}'
    for name, state in docker_states():
        if badge(state) != 'OK':
            alerts[f'docker:{name}'] = f'Docker 容器异常 {name}: {state}'
    for item in check_results():
        if not item['ok']:
            alerts[f'url:{item["url"]}'] = f'地址不可用 {item["url"]}: {item["raw"]}'
    return alerts


def alert_message(kind, key, text):
    title = '⚠️ <b>VPS 异常告警</b>' if kind == 'new' else '✅ <b>VPS 异常恢复</b>'
    return f'{title}\n{divider()}\n{row("🔎", "项目", key)}\n{row("📌", "详情", text)}\n{row("🕒", "时间", dt.datetime.now(dt.UTC).strftime("%Y-%m-%d %H:%M:%S UTC"))}'


def broadcast(text, reply_markup=None):
    for chat_id in sorted(ALLOWED_USERS):
        try:
            send(chat_id, text, reply_markup)
        except Exception as exc:
            log(f'broadcast to {chat_id} failed: {exc}')


def monitor_loop():
    state = load_alert_state()
    last_daily = state.get('last_daily', '')
    last_cf_optimize = state.get('last_cf_optimize', '')
    while True:
        try:
            alerts = current_alerts()
            previous = state.get('active_alerts', {})
            for key, text in alerts.items():
                if key not in previous:
                    broadcast(alert_message('new', key, text), page_keyboard('status'))
            for key, text in previous.items():
                if key not in alerts:
                    broadcast(alert_message('recovered', key, text), page_keyboard('status'))
            now = dt.datetime.now()
            today = now.strftime('%Y-%m-%d')
            if now.hour == DAILY_REPORT_HOUR and last_daily != today:
                broadcast(report_text('每日巡检报告'), reports_keyboard())
                last_daily = today
            if (now.hour > CF_OPTIMIZE_HOUR or (now.hour == CF_OPTIMIZE_HOUR and now.minute >= CF_OPTIMIZE_MINUTE)) and last_cf_optimize != today:
                result = cf_optimize(apply=True)
                broadcast(cf_status_text(result, '每日 Cloudflare 优选 IP'), cf_keyboard())
                last_cf_optimize = today
            state = {'active_alerts': alerts, 'last_daily': last_daily, 'last_cf_optimize': last_cf_optimize}
            save_alert_state(state)
        except Exception as exc:
            log(f'monitor loop error: {exc}')
        time.sleep(MONITOR_INTERVAL)


def confirm_keyboard(target):
    labels = {'nginx': 'Nginx', 'xui': '3X-UI', 'sub': 'Subconverter', 'cleanup': '安全清理'}
    return {'inline_keyboard': [
        [{'text': f"{TEXT['confirm']} {labels[target]}", 'callback_data': f'restart:{target}'}, {'text': TEXT['cancel'], 'callback_data': 'cancel'}],
        [{'text': '返回面板', 'callback_data': 'panel:home'}],
    ]}


def do_restart(target):
    mapping = {'nginx': 'nginx', 'xui': 'x-ui', 'sub': 'subconverter'}
    service = mapping[target]
    if target == 'nginx':
        code, out = run(['nginx', '-t'], 15)
        if code != 0:
            return '<b>Nginx 配置检查失败，已取消 reload</b>\n' + pre_block(out[-1200:])
        code, out = run(['systemctl', 'reload', 'nginx'], 20)
        return '<b>Nginx 已 reload</b>' if code == 0 else '<b>Nginx reload 失败</b>\n' + pre_block(out[-1200:])
    code, out = run(['systemctl', 'restart', service], 25)
    if code != 0:
        return f'<b>{esc(service)} 重启失败</b>\n' + pre_block(out[-1200:])
    _, state = run(['systemctl', 'is-active', service], 8)
    return f'<b>{esc(service)} 已重启</b>\n{line("当前状态", state)}'


def is_allowed(chat_id):
    return str(chat_id) in ALLOWED_USERS


def command_response(command, args=None):
    args = args or []
    if command in {'/start', '/vps', '/panel'}:
        return panel_text(), panel_keyboard()
    if command == '/help':
        return help_text(), panel_keyboard()
    if command == '/status':
        return status_text(), page_keyboard('status', [[{'text': '服务巡检', 'callback_data': 'cmd:services'}, {'text': '节点流量', 'callback_data': 'cmd:traffic'}]])
    if command == '/services':
        return services_text(), page_keyboard('services', [[{'text': '重载 Nginx', 'callback_data': 'confirm:nginx'}, {'text': '重启 3X-UI', 'callback_data': 'confirm:xui'}]])
    if command == '/traffic':
        return traffic_text(), page_keyboard('traffic')
    if command == '/nodes':
        return nodes_text(), page_keyboard('nodes')
    if command == '/sub':
        return sub_text(), sub_keyboard()
    if command == '/cf_status':
        return cf_status_text(), cf_keyboard()
    if command == '/cf_optimize':
        return cf_status_text(cf_optimize(apply=True), 'Cloudflare 优选 IP 已执行'), cf_keyboard()
    if command == '/check':
        return check_text(), page_keyboard('check')
    if command == '/report':
        return report_text('即时巡检报告'), reports_keyboard()
    if command == '/regen_sub':
        return regen_sub_text(), page_keyboard('sub')
    if command == '/cleanup_status':
        return cleanup_status_text(), cleanup_keyboard()
    if command == '/cleanup':
        return '<b>确认要立即执行安全清理吗？</b>\n将清理 journal、APT 缓存、旧临时文件、过大的 Docker JSON 日志，并按阈值处理 page cache。', confirm_keyboard('cleanup')
    if command == '/backup':
        return backup_text(), page_keyboard(None)
    if command == '/logs':
        key = (args[0] if args else '').lower()
        refresh = 'logs_nginx' if key == 'nginx' else 'logs_xui' if key in {'xui', 'x-ui'} else None
        return logs_text(args[0] if args else ''), page_keyboard(refresh)
    if command == '/logs_nginx':
        return logs_text('nginx'), page_keyboard('logs_nginx')
    if command == '/logs_xui':
        return logs_text('xui'), page_keyboard('logs_xui')
    if command == '/logs_docker':
        return logs_text('docker'), page_keyboard('logs_docker')
    if command == '/logs_sub':
        return logs_text('sub'), page_keyboard('logs_sub')
    if command == '/speedtest':
        return speedtest_text(), page_keyboard('speedtest')
    if command == '/restart_nginx':
        return '<b>确认要 reload Nginx 吗？</b>', confirm_keyboard('nginx')
    if command == '/restart_xui':
        return '<b>确认要重启 3X-UI 吗？</b>', confirm_keyboard('xui')
    if command == '/restart_sub':
        return '<b>确认要重启 Subconverter 吗？</b>', confirm_keyboard('sub')
    return TEXT['unknown'], panel_keyboard()


def handle_message(chat_id, text):
    stripped = (text or '').strip()
    command = stripped.split()[0].split('@', 1)[0].lower() if stripped else ''
    args = stripped.split()[1:]
    return command_response(command, args)


def process_update(update):
    if 'callback_query' in update:
        cq = update['callback_query']
        chat_id = cq.get('message', {}).get('chat', {}).get('id')
        callback_id = cq.get('id')
        data = cq.get('data', '')
        if not is_allowed(chat_id):
            answer_callback(callback_id, '\u672a\u6388\u6743')
            return
        answer_callback(callback_id)
        if data == 'cancel':
            send(chat_id, f'<b>{esc(TEXT["cancelled"])}</b>', page_keyboard(None))
        elif data == 'panel:home':
            send(chat_id, panel_text(), panel_keyboard())
        elif data.startswith('menu:'):
            key = data.split(':', 1)[1]
            menus = {
                'nodes': ('🧬 <b>节点与订阅</b>\n' + divider(), nodes_keyboard()),
                'cf': ('⚡ <b>Cloudflare 优选 IP</b>\n' + divider(), cf_keyboard()),
                'logs': ('📜 <b>日志中心</b>\n' + divider(), logs_keyboard()),
                'maintenance': ('🛠️ <b>维护中心</b>\n' + divider(), maintenance_keyboard()),
                'reports': ('🧾 <b>巡检中心</b>\n' + divider(), reports_keyboard()),
            }
            text, markup = menus.get(key, (panel_text(), panel_keyboard()))
            send(chat_id, text, markup)
        elif data.startswith('restart:'):
            target = data.split(':', 1)[1]
            if target in {'nginx', 'xui', 'sub'}:
                send(chat_id, do_restart(target), page_keyboard(None))
            elif target == 'cleanup':
                send(chat_id, cleanup_text(force=True), cleanup_keyboard())
        elif data.startswith('confirm:'):
            target = data.split(':', 1)[1]
            if target in {'nginx', 'xui', 'sub', 'cleanup'}:
                send(chat_id, '<b>确认执行？</b>', confirm_keyboard(target))
        elif data.startswith('refresh:'):
            key = data.split(':', 1)[1]
            mapping = {'status': '/status', 'services': '/services', 'traffic': '/traffic', 'nodes': '/nodes', 'sub': '/sub', 'cf_status': '/cf_status', 'check': '/check', 'report': '/report', 'logs_nginx': '/logs_nginx', 'logs_xui': '/logs_xui', 'logs_docker': '/logs_docker', 'logs_sub': '/logs_sub', 'speedtest': '/speedtest', 'cleanup_status': '/cleanup_status'}
            command = mapping.get(key, '/panel')
            reply, markup = command_response(command, [])
            send(chat_id, reply, markup)
        elif data.startswith('cmd:'):
            key = data.split(':', 1)[1]
            mapping = {'status': '/status', 'services': '/services', 'traffic': '/traffic', 'nodes': '/nodes', 'sub': '/sub', 'cf_status': '/cf_status', 'cf_optimize': '/cf_optimize', 'check': '/check', 'report': '/report', 'regen_sub': '/regen_sub', 'cleanup_status': '/cleanup_status', 'logs_nginx': '/logs_nginx', 'logs_xui': '/logs_xui', 'logs_docker': '/logs_docker', 'logs_sub': '/logs_sub', 'backup': '/backup', 'speedtest': '/speedtest'}
            command = mapping.get(key, '/panel')
            reply, markup = command_response(command, [])
            send(chat_id, reply, markup)
        return
    msg = update.get('message') or {}
    chat_id = msg.get('chat', {}).get('id')
    text = msg.get('text', '')
    if not text:
        return
    if not is_allowed(chat_id):
        if text.startswith('/'):
            send(chat_id, TEXT['unauth'])
        return
    reply, markup = handle_message(chat_id, text)
    send(chat_id, reply, markup)


def poll_loop():
    APP_DIR.mkdir(parents=True, exist_ok=True)
    offset_file = APP_DIR / 'offset'
    offset = 0
    if offset_file.exists():
        raw = offset_file.read_text(encoding='utf-8').strip()
        if raw.isdigit():
            offset = int(raw)
    api('deleteWebhook', {'drop_pending_updates': False}, timeout=15)
    log('bot started')
    while True:
        try:
            result = api('getUpdates', {'offset': offset, 'timeout': POLL_TIMEOUT, 'allowed_updates': ['message', 'callback_query']}, timeout=POLL_TIMEOUT + 15)
            for update in result.get('result', []):
                offset = max(offset, int(update['update_id']) + 1)
                offset_file.write_text(str(offset), encoding='utf-8')
                process_update(update)
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            log(f'poll error: {exc}')
            time.sleep(5)


def offline_test():
    for name, text in [('panel', panel_text()), ('help', help_text()), ('status', status_text()), ('services', services_text()), ('nodes', nodes_text()), ('sub', sub_text())]:
        print(f'--- {name} ---')
        print(text[:1600])


def main():
    load_env_file()
    if len(sys.argv) > 1 and sys.argv[1] == '--offline-test':
        offline_test()
        return
    threading.Thread(target=monitor_loop, daemon=True).start()
    poll_loop()


if __name__ == '__main__':
    main()
