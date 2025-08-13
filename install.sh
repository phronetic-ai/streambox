#!/bin/bash
set -e
echo "🚀 Running Streambox setup script..."

# enable headless services
loginctl enable-linger "$USER"

# Set vars
REPO_URL="https://github.com/phronetic-ai/streambox.git"
REPO_NAME="streambox"
CODE_DIR="$HOME/code/$REPO_NAME"
SERVICE_NAME="streambox"
SERVICE_PATH="$HOME/.config/systemd/user/${SERVICE_NAME}.service"

echo "📦 Updating packages..."
sudo apt update -y

# 1. Install Python, git
if ! command -v python3 >/dev/null; then
  echo "🐍 Installing Python..."
  sudo apt install -y python3 python3-pip python3-venv
fi

if ! command -v git >/dev/null; then
  echo "📥 Installing Git..."
  sudo apt install -y git
fi

# 2. Install uv
if ! command -v uv >/dev/null; then
  echo "🚀 Installing uv..."
  curl -Ls https://astral.sh/uv/install.sh | bash
else
  echo "✅ uv already installed"
fi

# 3. Clone GitHub repo
mkdir -p ~/code
if [ ! -d "$CODE_DIR" ]; then
  echo "📁 Cloning repo..."
  echo "Running git clone $REPO_URL $CODE_DIR"
  git clone "$REPO_URL" "$CODE_DIR"
else
  echo "🔄 Pulling latest changes..."
  cd "$CODE_DIR"
  git fetch origin main
  git reset --hard origin/main
fi

cd "$CODE_DIR"

# 4. Install dependencies
echo "📦 Syncing dependencies..."
uv sync

# 5. Run setup.py (if exists)
if [ -f "setup.py" ]; then
  echo "⚙️ Running setup.py..."
  uv run python setup.py
fi

# 6. Install ffmpeg
if ! command -v ffmpeg >/dev/null; then
  echo "🎥 Installing FFmpeg..."
  sudo apt install -y ffmpeg
fi

# 7. Install speedtest-cli if not already present
if ! command -v speedtest &> /dev/null; then
    echo "Installing speedtest-cli..."
    bash "$CODE_DIR/scripts/install_speedtest.sh"
fi

# 8. Create systemd service
if [ ! -f "$SERVICE_PATH" ]; then
  echo "🛠️ Creating systemd service..."
  mkdir -p "$HOME/.config/systemd/user"
  touch "$SERVICE_PATH"
  echo "Created service file at $SERVICE_PATH"
fi

cat <<EOF | tee "$SERVICE_PATH" > /dev/null
[Unit]
Description=Theia Agent
After=network.target

[Service]
WorkingDirectory=$CODE_DIR
ExecStart=$HOME/.local/bin/uv run python main.py
Restart=always
RestartSec=3
Environment=PATH=$HOME/.local/bin:/usr/bin:/bin

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reexec
systemctl --user daemon-reload
systemctl --user enable "$SERVICE_NAME"
systemctl --user start "$SERVICE_NAME"

# 7. Install update monitor
echo "🔄 Setting up automatic updates..."
if [ -f "$CODE_DIR/scripts/install_updates_monitor.sh" ]; then
  chmod +x "$CODE_DIR/scripts/install_updates_monitor.sh"
  "$CODE_DIR/scripts/install_updates_monitor.sh" "$CODE_DIR"
  echo "🔄 Update monitor installed"
else
  echo "⚠️ Update monitor script not found. Skipping."
fi
