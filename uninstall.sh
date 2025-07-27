#!/bin/bash

set -e

APP_DIR="$HOME/easyswanvpn"
VENV_DIR="$APP_DIR/venv"
SERVICE_NAME="easyswanvpn"
SYSTEMD_UNIT="/etc/systemd/system/${SERVICE_NAME}.service"
NGINX_CONF="/etc/nginx/sites-available/portal.easyswan.net"
NGINX_CONF_LINK="/etc/nginx/sites-enabled/portal.easyswan.net"
SSL_CERT="/etc/ssl/certs/portal.easyswan.net.crt"
SSL_KEY="/etc/ssl/private/portal.easyswan.net.key"

echo "[*] Stopping and disabling systemd service if it exists..."
sudo systemctl stop $SERVICE_NAME 2>/dev/null || true
sudo systemctl disable $SERVICE_NAME 2>/dev/null || true

echo "[*] Removing systemd service file if it exists..."
sudo rm -f "$SYSTEMD_UNIT"
sudo systemctl daemon-reload

echo "[*] Removing application directory and virtual environment..."
rm -rf "$APP_DIR"

echo "[*] Removing Nginx configuration if it exists..."
sudo rm -f "$NGINX_CONF"
sudo rm -f "$NGINX_CONF_LINK"
sudo nginx -t && sudo systemctl reload nginx || true

echo "[*] Removing SSL certificate and key if they exist..."
sudo rm -f "$SSL_CERT"
sudo rm -f "$SSL_KEY"

echo "[*] EasySwanVPN has been fully removed from this server."
