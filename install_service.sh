#!/usr/bin/env bash
#!/usr/bin/env bash
# Install systemd unit and timer for website-watcher (requires root)
set -euo pipefail
BASEDIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_SRC="$BASEDIR/systemd/website-watcher.service"
TIMER_SRC="$BASEDIR/systemd/website-watcher.timer"
ENV_FILE="/etc/default/website-watcher"
DATA_DIR="/var/lib/website-watcher"

if [ "$EUID" -ne 0 ]; then
  echo "This script must be run as root to install systemd units. Use sudo." >&2
  exit 1
fi

# create data dir and a dedicated user if it does not exist
if ! id -u website-watcher >/dev/null 2>&1; then
  useradd --system --home "$DATA_DIR" --shell /usr/sbin/nologin website-watcher || true
fi
mkdir -p "$DATA_DIR"
chown website-watcher:website-watcher "$DATA_DIR"

# write a simple env file for the service (can be edited by admin)
cat > "$ENV_FILE" <<EOF
# Environment for website-watcher service
WPS_DB_PATH=${WPS_DB_PATH:-$DATA_DIR/watcher.db}
ARCHIVEBOX_INDEX_JSON=${ARCHIVEBOX_INDEX_JSON:-}
PYTHONUNBUFFERED=1
EOF

cp "$SERVICE_SRC" /etc/systemd/system/website-watcher.service
cp "$TIMER_SRC" /etc/systemd/system/website-watcher.timer
systemctl daemon-reload
systemctl enable --now website-watcher.timer
echo "Installed and enabled website-watcher.timer"
echo "Data dir: $DATA_DIR; env: $ENV_FILE"
