from flask import Flask, render_template, request, session, redirect, url_for, jsonify, send_file
import os
import json
import pyotp
import qrcode
import io
import base64
import subprocess
import pam
import requests
import tempfile
import shutil

app = Flask(__name__)
app.secret_key = os.urandom(32)

USER_FILE = "users.json"
SYSTEM_USERNAME = "andyk"  # Use your system username

def load_users():
    if not os.path.exists(USER_FILE):
        return {}
    with open(USER_FILE) as f:
        return json.load(f)

def save_users(users):
    with open(USER_FILE, "w") as f:
        json.dump(users, f)

def get_user():
    users = load_users()
    return users.get(SYSTEM_USERNAME)

def authenticate_linux(username, password):
    p = pam.pam()
    return p.authenticate(username, password)

def check_auth():
    return session.get("logged_in")

def get_public_ip():
    try:
        return requests.get('https://api.ipify.org', timeout=3).text
    except Exception:
        return "N/A"

def get_vpn_status():
    try:
        import psutil
        return "tun0" in psutil.net_if_addrs()
    except Exception:
        try:
            output = subprocess.check_output("ip addr show tun0", shell=True, text=True)
            return "state UP" in output or "tun0" in output
        except Exception:
            return False

def get_tunnel_ip():
    try:
        output = subprocess.check_output("ip -4 addr show tun0", shell=True, text=True)
        for line in output.splitlines():
            line = line.strip()
            if line.startswith("inet "):
                return line.split()[1].split("/")[0]
        return "N/A"
    except Exception:
        return "N/A"

def get_remote_gateway_ip():
    # This is the "via" address in default route (the router)
    try:
        output = subprocess.check_output("ip route show default", shell=True, text=True)
        for line in output.splitlines():
            parts = line.strip().split()
            if "default" in parts:
                return parts[2]
        return "N/A"
    except Exception:
        return "N/A"

def get_wan_ip():
    # WAN IP: IP of the interface used for default route, NOT tun0, NOT lo
    try:
        output = subprocess.check_output("ip route show default", shell=True, text=True)
        iface = None
        for line in output.splitlines():
            parts = line.strip().split()
            if "default" in parts and "dev" in parts:
                dev_index = parts.index("dev")
                iface = parts[dev_index + 1]
                break
        if iface and not iface.startswith("lo") and not iface.startswith("tun"):
            ip_output = subprocess.check_output(f"ip -4 addr show {iface}", shell=True, text=True)
            for line in ip_output.splitlines():
                line = line.strip()
                if line.startswith("inet "):
                    return line.split()[1].split("/")[0]
        return "N/A"
    except Exception:
        return "N/A"

def get_lan_ip(interface_name="enxc8a362ba3ec9"):
    # LAN IP: always from the specified LAN interface
    try:
        output = subprocess.check_output(f"ip -4 addr show {interface_name}", shell=True, text=True)
        for line in output.splitlines():
            line = line.strip()
            if line.startswith("inet "):
                return line.split()[1].split("/")[0]
        return "N/A"
    except Exception:
        return "N/A"

@app.route("/", methods=["GET", "POST"])
def index():
    if not check_auth():
        return redirect(url_for("login"))
    return render_template("main.html", username=SYSTEM_USERNAME)

@app.route("/main")
def main():
    if not check_auth():
        return redirect(url_for("login"))
    return render_template("main.html", username=SYSTEM_USERNAME)

@app.route("/protected")
def protected():
    if not check_auth():
        return redirect(url_for("login"))
    return render_template("protected.html", username=SYSTEM_USERNAME)

@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""
    user = get_user()

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username != SYSTEM_USERNAME:
            error = "Invalid username or password"
        elif not authenticate_linux(username, password):
            error = "Invalid username or password"
        else:
            users = load_users()
            if not user:
                totp_secret = pyotp.random_base32()
                users[SYSTEM_USERNAME] = {"totp_secret": totp_secret, "mfa_enabled": False}
                save_users(users)
                session["username"] = username
                return redirect(url_for("mfa_setup"))
            elif not user.get("mfa_enabled"):
                session["username"] = username
                return redirect(url_for("mfa_setup"))
            else:
                session["username"] = username
                return redirect(url_for("mfa"))

    return render_template("login.html", error=error)

@app.route("/mfa_setup", methods=["GET", "POST"])
def mfa_setup():
    users = load_users()
    user = users.get(SYSTEM_USERNAME)
    error = ""
    if not user:
        return redirect(url_for("login"))

    secret = user["totp_secret"]
    provisioning_uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=f"{SYSTEM_USERNAME}@easyswanvpn", issuer_name="EasySwanVPN"
    )

    img = qrcode.make(provisioning_uri)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    qr_b64 = base64.b64encode(buf.read()).decode('ascii')

    if request.method == "POST":
        otp = request.form.get("mfa_code")
        totp = pyotp.TOTP(secret)
        if totp.verify(otp):
            user["mfa_enabled"] = True
            save_users(users)
            session["logged_in"] = True
            return redirect(url_for("index"))
        else:
            error = "Invalid OTP code. Please try again."

    return render_template(
        "mfa_setup.html",
        error=error,
        qr_b64=qr_b64,
        secret=secret
    )

@app.route("/mfa", methods=["GET", "POST"])
def mfa():
    users = load_users()
    user = users.get(SYSTEM_USERNAME)
    error = ""
    if not user or not user.get("mfa_enabled"):
        return redirect(url_for("login"))

    if request.method == "POST":
        otp = request.form.get("mfa_code")
        totp = pyotp.TOTP(user["totp_secret"])
        if totp.verify(otp):
            session["logged_in"] = True
            return redirect(url_for("index"))
        else:
            error = "Invalid OTP code. Please try again."

    return render_template("mfa.html", error=error)

@app.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/generate", methods=["GET", "POST"])
def generate():
    if not check_auth():
        return redirect(url_for("login"))

    error = ""
    if request.method == "POST":
        common_name = request.form.get("common_name", "client")
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                key_path = os.path.join(tmpdir, "client.key")
                crt_path = os.path.join(tmpdir, "client.crt")
                config_path = os.path.join(tmpdir, "client.conf")

                # Generate private key
                subprocess.run(["openssl", "genrsa", "-out", key_path, "2048"], check=True)
                # Generate self-signed certificate
                subprocess.run([
                    "openssl", "req", "-new", "-x509", "-key", key_path, "-out", crt_path,
                    "-days", "365", "-subj", f"/CN={common_name}"
                ], check=True)
                # Write a simple config as example
                with open(config_path, "w") as f:
                    f.write(f"client\ncert = client.crt\nkey = client.key\n")

                # Zip files for download
                zip_base = os.path.join(tmpdir, "client_bundle")
                shutil.make_archive(zip_base, 'zip', tmpdir)
                zip_path = zip_base + ".zip"

                return send_file(zip_path, as_attachment=True, download_name="client_bundle.zip")
        except Exception as e:
            error = f"Error generating certificate: {e}"
    return render_template("generate.html", error=error)

@app.route("/api/networks")
def api_networks():
    if not check_auth():
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
    try:
        output = subprocess.check_output(
            ["nmcli", "-t", "-f", "SSID,SIGNAL", "device", "wifi", "list"],
            text=True
        )
        networks = []
        for line in output.strip().split("\n"):
            if line:
                parts = line.split(":")
                if len(parts) >= 2:
                    ssid, signal = parts[0], parts[1]
                    networks.append({"ssid": ssid, "signal": signal})
        return jsonify(networks)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/connect", methods=["POST"])
def api_connect():
    if not check_auth():
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
    data = request.get_json(force=True)
    ssid = data.get("ssid")
    psk = data.get("psk", "")
    if not ssid:
        return jsonify({"status": "error", "message": "SSID required"}), 400
    try:
        cmd = ["nmcli", "device", "wifi", "connect", ssid]
        if psk:
            cmd += ["password", psk]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            return jsonify({"status": "success"})
        else:
            return jsonify({"status": "error", "message": result.stderr.strip() or result.stdout.strip()}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/restart_service", methods=["POST"])
def restart_service():
    if not check_auth():
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
    try:
        subprocess.Popen(["sudo", "systemctl", "restart", "openvpn-client@TravelNetVPN"])
        return jsonify({"status": "success", "message": "Service restarting..."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/shutdown", methods=["POST"])
def shutdown():
    if not check_auth():
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
    try:
        subprocess.Popen(["sudo", "shutdown", "-h", "now"])
        return jsonify({"status": "success", "message": "Server shutting down..."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/reboot", methods=["POST"])
def reboot():
    if not check_auth():
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
    try:
        subprocess.Popen(["sudo", "reboot"])
        return jsonify({"status": "success", "message": "Server rebooting..."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/status")
def api_status():
    if not check_auth():
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    public_ip = get_public_ip()
    wan_ip = get_wan_ip()
    lan_ip = get_lan_ip("enxc8a362ba3ec9")  # LAN IP as requested
    tunnel_ip = get_tunnel_ip()
    remote_gateway_ip = get_remote_gateway_ip()
    vpn_connected = get_vpn_status()

    return jsonify({
        "status": "success",
        "vpn_connected": vpn_connected,
        "public_ip": public_ip,
        "wan_ip": wan_ip,
        "lan_ip": lan_ip,
        "tunnel_ip": tunnel_ip,
        "remote_gateway_ip": remote_gateway_ip
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
