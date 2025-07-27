#!/bin/bash
set -e

BASE_DIR="$HOME/easyswanvpn"
REPO_URL="https://github.com/andrew-kemp/EasySwanVPN.git"

echo "[+] Checking for existing EasySwanVPN installation..."

if [ -d "$BASE_DIR/.git" ]; then
  echo "[+] EasySwanVPN already cloned at $BASE_DIR. Pulling latest changes..."
  cd "$BASE_DIR"
  git pull
else
  if [ -d "$BASE_DIR" ]; then
    echo "[!] Directory $BASE_DIR exists but is not a git repo. Removing it for a fresh clone."
    rm -rf "$BASE_DIR"
  fi
  echo "[+] Cloning EasySwanVPN repo to $BASE_DIR"
  git clone "$REPO_URL" "$BASE_DIR"
  cd "$BASE_DIR"
fi

echo "[+] Installing required system packages..."
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip strongswan easy-rsa openssl

echo "[+] Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Ensure Flask is in requirements.txt
if ! grep -q Flask requirements.txt; then
  echo "Flask>=2.2" >> requirements.txt
fi

echo "[+] Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "[+] Python environment ready and Flask installed."
echo "[+] strongSwan, EasyRSA, and OpenSSL are installed."

# --- Systemd user service block ---
echo "[+] Creating systemd user service for EasySwanVPN..."

SERVICE_DIR="$HOME/.config/systemd/user"
SERVICE_FILE="$SERVICE_DIR/easyswanvpn.service"

mkdir -p "$SERVICE_DIR"

cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=EasySwanVPN Flask web app
After=network.target

[Service]
User=$USER
WorkingDirectory=$HOME/easyswanvpn
Environment="PATH=$HOME/easyswanvpn/venv/bin"
ExecStart=$HOME/easyswanvpn/venv/bin/python $HOME/easyswanvpn/run.py
Restart=always

[Install]
WantedBy=default.target
EOF

echo "[+] Created user systemd service: $SERVICE_FILE"
echo "[*] To enable and start your service, run:"
echo "    systemctl --user daemon-reload"
echo "    systemctl --user enable easyswanvpn"
echo "    systemctl --user start easyswanvpn"
echo "[*] To check status or logs:"
echo "    systemctl --user status easyswanvpn"
echo "    journalctl --user -u easyswanvpn -f"

echo "[!] Setup completed successfully."
