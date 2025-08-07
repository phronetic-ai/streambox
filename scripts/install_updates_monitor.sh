#!/bin/bash

# Check if CODE_DIR argument is provided
if [ -z "$1" ]; then
    echo "Error: CODE_DIR argument is required"
    echo "Usage: $0 <code_directory>"
    exit 1
fi

CODE_DIR=$1
TIMER_PATH="$HOME/.config/systemd/user/streambox_updates_monitor.timer"
SERVICE_PATH="$HOME/.config/systemd/user/streambox_updates_monitor.service"

# Create service file
cat <<EOF > "$SERVICE_PATH"
[Unit]
Description=Updates Monitor for $CODE_DIR

[Service]
Type=oneshot
ExecStart=$CODE_DIR/scripts/updates_monitor.sh
EOF

# Create timer file
cat <<EOF > "$TIMER_PATH"
[Unit]
Description=Run git updater every 1 minute

[Timer]
OnBootSec=1min
OnUnitActiveSec=1min
Unit=streambox_updates_monitor.service

[Install]
WantedBy=timers.target
EOF

# Enable and start the timer
systemctl --user daemon-reload
systemctl --user enable --now "$TIMER_PATH"
