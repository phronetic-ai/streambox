#!/bin/bash

# Config
REPO_NAME="streambox"
REPO_DIR="$HOME/code/$REPO_NAME"
SERVICE_NAME="streambox"
LOG_FILE="$REPO_DIR/logs/streambox_monitor_updates.log"
MAX_LOG_SIZE_MB=20
mkdir -p "$REPO_DIR/logs" || exit 1

# Check if log file exists and rotate if needed
if [ -f "$LOG_FILE" ]; then
    # Get size in bytes and convert to MB
    log_size_bytes=$(stat -c%s "$LOG_FILE" 2>/dev/null || echo 0)
    log_size_mb=$((log_size_bytes / 1024 / 1024))

    if [ "$log_size_mb" -ge "$MAX_LOG_SIZE_MB" ]; then
        # Rotate logs, keeping only two backups
        if [ -f "${LOG_FILE}.2" ]; then
            rm "${LOG_FILE}.2"
        fi
        if [ -f "${LOG_FILE}.1" ]; then
            mv "${LOG_FILE}.1" "${LOG_FILE}.2"
        fi
        mv "$LOG_FILE" "${LOG_FILE}.1"
        touch "$LOG_FILE"
        echo "$(date): Log file rotated due to size exceeding ${MAX_LOG_SIZE_MB}MB" >> "$LOG_FILE"
    fi
else
    touch "$LOG_FILE"
fi

# Check if repo exists
if [ ! -d "$REPO_DIR" ]; then
    echo "Repository not found at $REPO_DIR" | tee -a "$LOG_FILE"
    exit 1
fi

cd "$REPO_DIR" || exit 1

# Fetch changes
git fetch origin

# Compare local HEAD with origin/main
LOCAL_HASH=$(git rev-parse HEAD)
REMOTE_HASH=$(git rev-parse origin/main)

if [ "$LOCAL_HASH" != "$REMOTE_HASH" ]; then
    echo "$(date): Detected change in origin. Pulling latest code..." | tee -a "$LOG_FILE"
    git reset --hard origin/main
    systemctl --user restart "$SERVICE_NAME"
else
    echo "$(date): No changes found." | tee -a "$LOG_FILE"
fi
