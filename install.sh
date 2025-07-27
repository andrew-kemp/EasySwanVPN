#!/bin/bash

set -e

# 1. Create project folder structure
BASE_DIR="$HOME/easyswanvpn"
mkdir -p "$BASE_DIR"
mkdir -p "$BASE_DIR/app/templates"
mkdir -p "$BASE_DIR/static"

touch "$BASE_DIR/app/__init__.py"
touch "$BASE_DIR/app/routes.py"
touch "$BASE_DIR/app/certgen.py"
touch "$BASE_DIR/app/templates/index.html"
touch "$BASE_DIR/requirements.txt"
touch "$BASE_DIR/run.py"
touch "$BASE_DIR/README.md"

echo "[+] EasySwanVPN folder structure created at $BASE_DIR"


# 2. Install system packages (Python, strongSwan, EasyRSA, OpenSSL)
echo "[+] Installing required system packages..."
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip strongswan easy-rsa openssl

# 3. Set up Python virtual environment
cd "$BASE_DIR"
python3 -m venv venv
source venv/bin/activate

# 4. Create requirements.txt if missing
if ! grep -q Flask requirements.txt; then
  echo "Flask>=2.2" >> requirements.txt
fi

# 5. Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

echo "[+] Python environment ready and Flask installed."
echo "[+] strongSwan, EasyRSA, and OpenSSL are installed."
echo "[!] Setup completed successfully."
