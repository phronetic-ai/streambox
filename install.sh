#!/bin/bash
set -e
echo "🚀 Running Streambox setup script..."

# Set vars
REPO_URL="https://github.com/phronetic-ai/streambox.git"
REPO_NAME="streambox"
CODE_DIR="$HOME/code/$REPO_NAME"
UV_BIN="$HOME/.cargo/bin/uv"
SERVICE_NAME="streambox"
SERVICE_PATH="/etc/systemd/system/$SERVICE_NAME.service"

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
if [ ! -f "$UV_BIN" ]; then
  echo "🚀 Installing uv..."
  curl -Ls https://astral.sh/uv/install.sh | bash
  export PATH="$HOME/.cargo/bin:$PATH"
else
  echo "✅ uv already installed"
fi

# 3. Clone GitHub repo
mkdir -p ~/code
if [ ! -d "$CODE_DIR" ]; then
  echo "📁 Cloning repo..."
  git clone "$REPO_URL" "$CODE_DIR"
else
  echo "🔄 Pulling latest changes..."
  cd "$CODE_DIR"
  git pull
fi

cd "$CODE_DIR"

# 4. Install dependencies
echo "📦 Syncing dependencies..."
$UV_BIN sync

# 5. Run setup.py (if exists)
if [ -f "setup.py" ]; then
  echo "⚙️ Running setup.py..."
  $UV_BIN run python setup.py
fi

# 6. Create systemd service
if [ ! -f "$SERVICE_PATH" ]; then
  echo "🛠️ Creating systemd service..."

  cat <<EOF | sudo tee "$SERVICE_PATH" > /dev/null
[Unit]
Description=Theia Agent
After=network.target

[Service]
User=$USER
WorkingDirectory=$CODE_DIR
ExecStart=$UV_BIN run python main.py
Restart=always
RestartSec=3
Environment=PATH=$HOME/.cargo/bin:/usr/bin:/bin

[Install]
WantedBy=multi-user.target
EOF

  sudo systemctl daemon-reexec
  sudo systemctl daemon-reload
  sudo systemctl enable "$SERVICE_NAME"
  sudo systemctl start "$SERVICE_NAME"
else
  echo "✅ Systemd service already exists"
fi
