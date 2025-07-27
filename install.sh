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
echo "[!] Setup completed successfully."
