#!/bin/bash
set -e

BASE_DIR="/home/andyk/easyswanvpn"
REPO_URL="https://github.com/andrew-kemp/EasySwanVPN.git"
SERVICE_NAME="easyswanvpn"
SYSTEMD_SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}.service"
USER_NAME="andyk"
USER_HOME="/home/${USER_NAME}"

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

# --- Systemd system service block ---
echo "[+] Creating system-wide systemd service for EasySwanVPN..."

cat > /tmp/${SERVICE_NAME}.service <<EOF
[Unit]
Description=EasySwanVPN Flask web app
After=network.target

[Service]
Type=simple
User=${USER_NAME}
WorkingDirectory=${USER_HOME}/easyswanvpn
Environment="PATH=${USER_HOME}/easyswanvpn/venv/bin"
ExecStart=${USER_HOME}/easyswanvpn/venv/bin/python ${USER_HOME}/easyswanvpn/run.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo mv /tmp/${SERVICE_NAME}.service ${SYSTEMD_SERVICE_PATH}
sudo chown root:root ${SYSTEMD_SERVICE_PATH}
sudo chmod 644 ${SYSTEMD_SERVICE_PATH}

echo "[+] Reloading systemd manager configuration..."
sudo systemctl daemon-reload

echo "[+] Enabling EasySwanVPN service to start at boot..."
sudo systemctl enable ${SERVICE_NAME}

echo "[+] Starting EasySwanVPN service now..."
sudo systemctl restart ${SERVICE_NAME}

echo "[*] To check service status or logs, use:"
echo "    sudo systemctl status ${SERVICE_NAME}"
echo "    sudo journalctl -u ${SERVICE_NAME} -f"

echo "[!] Setup completed successfully."
