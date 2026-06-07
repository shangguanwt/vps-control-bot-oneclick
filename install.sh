#!/usr/bin/env bash
set -euo pipefail

REPO="${REPO:-shangguanwt/vps-control-bot-oneclick}"
BRANCH="${BRANCH:-main}"
RAW_BASE="${RAW_BASE:-https://raw.githubusercontent.com/${REPO}/${BRANCH}}"
INSTALL_DIR="${INSTALL_DIR:-/opt/vps-control-bot}"
ENV_FILE="${ENV_FILE:-/etc/vps-control-bot.env}"
LOCAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || true)"

usage() {
  cat <<'EOF'
Usage:
  sudo bash install.sh
  sudo bash install.sh --update
  sudo bash install.sh --uninstall
  sudo bash install.sh --dry-run

Environment overrides:
  REPO=owner/repo BRANCH=main RAW_BASE=https://...
EOF
}

DRY_RUN=0
MODE="install"
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --update) MODE="update" ;;
    --uninstall) MODE="uninstall" ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $arg" >&2; usage; exit 2 ;;
  esac
done

need_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    echo "Please run as root: sudo bash install.sh" >&2
    exit 1
  fi
}

run() {
  echo "+ $*"
  if [[ "$DRY_RUN" -eq 0 ]]; then
    "$@"
  fi
}

fetch() {
  local path="$1"
  local dest="$2"
  if [[ -n "$LOCAL_DIR" && -f "$LOCAL_DIR/$path" ]]; then
    run install -D -m 0644 "$LOCAL_DIR/$path" "$dest"
    return
  fi
  run mkdir -p "$(dirname "$dest")"
  echo "+ curl -fsSL ${RAW_BASE}/${path} -o ${dest}"
  if [[ "$DRY_RUN" -eq 0 ]]; then
    curl -fsSL "${RAW_BASE}/${path}" -o "$dest"
  fi
}

prompt() {
  local var_name="$1"
  local label="$2"
  local default="${3:-}"
  local secret="${4:-0}"
  local value=""
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf -v "$var_name" '%s' "$default"
    return
  fi
  if [[ "$secret" -eq 1 ]]; then
    read -r -s -p "${label}${default:+ [${default}]}: " value
    echo
  else
    read -r -p "${label}${default:+ [${default}]}: " value
  fi
  value="${value:-$default}"
  printf -v "$var_name" '%s' "$value"
}

install_packages() {
  if command -v apt-get >/dev/null 2>&1; then
    run apt-get update
    run apt-get install -y python3 curl ca-certificates tar gzip coreutils findutils
  else
    echo "apt-get not found. Install python3 and curl manually, then rerun." >&2
    exit 1
  fi
}

write_env() {
  local tmp
  tmp="$(mktemp)"
  cat > "$tmp" <<EOF
BOT_TOKEN=${BOT_TOKEN}
ALLOWED_TELEGRAM_IDS=${ALLOWED_TELEGRAM_IDS}
VPS_DISPLAY_NAME=${VPS_DISPLAY_NAME}
SUB_TOKEN=${SUB_TOKEN}
SUB_BASE=${SUB_BASE}
CHECK_URLS=${CHECK_URLS}
CF_TEST_HOST=${CF_TEST_HOST}
XUI_DB=${XUI_DB}
SUB_GENERATOR=${SUB_GENERATOR}
MONITOR_INTERVAL=${MONITOR_INTERVAL}
DAILY_REPORT_HOUR=${DAILY_REPORT_HOUR}
MEM_WARN_PERCENT=${MEM_WARN_PERCENT}
DISK_WARN_PERCENT=${DISK_WARN_PERCENT}
LOAD_WARN_PER_CORE=${LOAD_WARN_PER_CORE}
EOF
  run install -D -m 0600 "$tmp" "$ENV_FILE"
  rm -f "$tmp"
}

install_files() {
  run mkdir -p "$INSTALL_DIR"
  fetch "src/bot.py" "$INSTALL_DIR/bot.py"
  fetch "src/vps-safe-cleanup" "/usr/local/sbin/vps-safe-cleanup"
  fetch "systemd/vps-control-bot.service" "/etc/systemd/system/vps-control-bot.service"
  fetch "systemd/vps-safe-cleanup.service" "/etc/systemd/system/vps-safe-cleanup.service"
  fetch "systemd/vps-safe-cleanup.timer" "/etc/systemd/system/vps-safe-cleanup.timer"
  run chmod 0755 "$INSTALL_DIR/bot.py" "/usr/local/sbin/vps-safe-cleanup"
}

configure_interactive() {
  local existing_token=""
  if [[ -f "$ENV_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$ENV_FILE" || true
    existing_token="${BOT_TOKEN:-}"
  fi
  prompt BOT_TOKEN "Telegram Bot Token" "${BOT_TOKEN:-$existing_token}" 1
  prompt ALLOWED_TELEGRAM_IDS "Allowed Telegram user IDs, comma separated" "${ALLOWED_TELEGRAM_IDS:-}"
  prompt VPS_DISPLAY_NAME "Display name" "${VPS_DISPLAY_NAME:-My VPS}"
  prompt SUB_TOKEN "Subscription token/path name" "${SUB_TOKEN:-change-me}"
  prompt SUB_BASE "Subscription base URL, leave empty to disable subscription page" "${SUB_BASE:-}"
  prompt CHECK_URLS "Extra health-check URLs, comma separated" "${CHECK_URLS:-}"
  prompt CF_TEST_HOST "Cloudflare test SNI host, leave empty to disable CF optimize" "${CF_TEST_HOST:-}"
  prompt XUI_DB "3X-UI database path" "${XUI_DB:-/etc/x-ui/x-ui.db}"
  prompt SUB_GENERATOR "Subscription generator path" "${SUB_GENERATOR:-/etc/proxy-subscription/generate.py}"
  prompt MONITOR_INTERVAL "Monitor interval seconds" "${MONITOR_INTERVAL:-600}"
  prompt DAILY_REPORT_HOUR "Daily report hour, server local time" "${DAILY_REPORT_HOUR:-9}"
  prompt MEM_WARN_PERCENT "Memory warning percent" "${MEM_WARN_PERCENT:-85}"
  prompt DISK_WARN_PERCENT "Disk warning percent" "${DISK_WARN_PERCENT:-85}"
  prompt LOAD_WARN_PER_CORE "Load warning per CPU core" "${LOAD_WARN_PER_CORE:-1.8}"
}

enable_services() {
  run python3 -m py_compile "$INSTALL_DIR/bot.py" "/usr/local/sbin/vps-safe-cleanup"
  run systemctl daemon-reload
  run systemctl enable --now vps-control-bot.service
  run systemctl enable --now vps-safe-cleanup.timer
  run systemctl restart vps-control-bot.service
}

uninstall_all() {
  run systemctl disable --now vps-control-bot.service vps-safe-cleanup.timer 2>/dev/null || true
  run rm -f /etc/systemd/system/vps-control-bot.service
  run rm -f /etc/systemd/system/vps-safe-cleanup.service
  run rm -f /etc/systemd/system/vps-safe-cleanup.timer
  run rm -f /usr/local/sbin/vps-safe-cleanup
  run rm -rf "$INSTALL_DIR"
  run systemctl daemon-reload
  echo "Kept $ENV_FILE by default. Remove it manually if you no longer need the secrets."
}

main() {
  need_root
  if [[ "$MODE" == "uninstall" ]]; then
    uninstall_all
    exit 0
  fi
  install_packages
  install_files
  if [[ "$MODE" == "install" ]]; then
    configure_interactive
    write_env
  elif [[ ! -f "$ENV_FILE" ]]; then
    echo "$ENV_FILE does not exist. Run interactive install first." >&2
    exit 1
  fi
  enable_services
  echo
  echo "Installed. Try /start in Telegram."
  echo "Status: systemctl status vps-control-bot --no-pager"
}

main
