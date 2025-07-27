#!/bin/bash
set -e

# ===== User Variables and Paths =====
USER_HOME="$HOME"
BASE_DIR="${USER_HOME}/easyswanvpn"
REPO_URL="https://github.com/andrew-kemp/EasySwanVPN.git"
SERVICE_NAME="easyswanvpn"
SYSTEMD_SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}.service"
SSL_CERT="/etc/ssl/certs/portal.easyswan.net.crt"
SSL_KEY="/etc/ssl/private/portal.easyswan.net.key"
NGINX_CONF="/etc/nginx/sites-available/portal.easyswan.net"
NGINX_CONF_LINK="/etc/nginx/sites-enabled/portal.easyswan.net"

PYTHON_VERSION="python3"  # Use system Python (e.g., Python 3.12+ on Ubuntu 24.04)

# ===== Clone or Update Repo =====
echo "[+] Checking for EasySwanVPN repository..."

if [ -d "$BASE_DIR/.git" ]; then
  echo "[+] EasySwanVPN already cloned at $BASE_DIR. Pulling latest changes..."
  cd "$BASE_DIR"
  git pull
else
  if [ -d "$BASE_DIR" ]; then
    echo "[!] Directory $BASE_DIR exists but is not a git repo. Removing for fresh clone."
    rm -rf "$BASE_DIR"
  fi
  echo "[+] Cloning EasySwanVPN repo to $BASE_DIR"
  git clone "$REPO_URL" "$BASE_DIR"
  cd "$BASE_DIR"
fi

# ===== Install System Dependencies =====
echo "[+] Installing required system packages..."
sudo apt-get update
sudo apt-get install -y $PYTHON_VERSION $PYTHON_VERSION-venv python3-pip strongswan easy-rsa openssl libpam0g-dev nginx

# ===== Python Virtual Environment and Dependencies =====
echo "[+] Setting up Python virtual environment..."
cd "$BASE_DIR"
$PYTHON_VERSION -m venv venv
source venv/bin/activate

# ===== Write requirements.txt for this project =====
cat > requirements.txt <<EOF
Flask
flask-login
pam
pyotp
qrcode
requests
psutil
EOF

echo "[+] Installing Python dependencies from requirements.txt..."
pip install --upgrade pip
pip install -r requirements.txt

echo "[+] Python environment ready and dependencies installed."

# ===== SSL Certificate for Nginx =====
echo "[+] Creating self-signed SSL certificate for portal.easyswan.net if needed..."
sudo mkdir -p /etc/ssl/private /etc/ssl/certs
if [ ! -f "$SSL_KEY" ] || [ ! -f "$SSL_CERT" ]; then
  sudo openssl req -x509 -nodes -days 365 -newkey rsa:4096 \
    -keyout "$SSL_KEY" \
    -out "$SSL_CERT" \
    -subj "/CN=portal.easyswan.net"
  sudo chmod 600 "$SSL_KEY"
  sudo chmod 644 "$SSL_CERT"
  echo "[+] Certificate and key created."
else
  echo "[~] Certificate and key already exist, skipping creation."
fi

# ===== Nginx Config =====
echo "[+] Creating Nginx config for portal.easyswan.net..."
sudo tee "$NGINX_CONF" > /dev/null <<EOF
server {
    listen 443 ssl;
    server_name portal.easyswan.net;

    ssl_certificate     $SSL_CERT;
    ssl_certificate_key $SSL_KEY;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }
}
EOF

sudo ln -sf "$NGINX_CONF" "$NGINX_CONF_LINK"
sudo nginx -t && sudo systemctl reload nginx

# ===== Systemd Service =====
echo "[+] Creating user-agnostic systemd service for EasySwanVPN..."

cat > /tmp/${SERVICE_NAME}.service <<EOF
[Unit]
Description=EasySwanVPN Flask web app
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$BASE_DIR
Environment="PATH=$BASE_DIR/venv/bin"
ExecStart=$BASE_DIR/venv/bin/python $BASE_DIR/app.py
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
