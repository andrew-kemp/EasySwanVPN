# EasySwanVPN

A simple web app to generate VPN certificates and configuration files for strongSwan deployments.

## Features

- Web front-end for certificate and config generation
- Designed for use on `/home/andyk/easyswanvpn/`
- Extendable for your network topology

## Usage

1. Install dependencies:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```
2. Run the app:
    ```bash
    python run.py
    ```
3. Visit `http://localhost:5000` in your browser.

## Next Steps

- Integrate EasyRSA/OpenSSL for real certificate generation
- Add config template generation
- Secure the web interface

---
