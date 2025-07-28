from flask import Flask, render_template, request, session, redirect, url_for, send_file, flash
import os
import json
import pyotp
import qrcode
import io
import base64
import subprocess
import pam
import tempfile
import shutil

app = Flask(__name__)
app.secret_key = os.urandom(32)

USER_FILE = "users.json"
SYSTEM_USERNAME = "andyk"

CA_DIR = "cas"
os.makedirs(CA_DIR, exist_ok=True)

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

def list_cas():
    return [d for d in os.listdir(CA_DIR) if os.path.isdir(os.path.join(CA_DIR, d))]

def get_active_ca():
    ca = session.get("active_ca")
    if ca and ca in list_cas():
        return ca
    cas = list_cas()
    if cas:
        session["active_ca"] = cas[0]
        return cas[0]
    return None

@app.route("/", methods=["GET"])
def index():
    if not check_auth():
        return redirect(url_for("login"))
    cas = list_cas()
    active_ca = get_active_ca()
    return render_template("dashboard.html", cas=cas, active_ca=active_ca, username=SYSTEM_USERNAME)

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

@app.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/mfa_setup", methods=["GET", "POST"])
def mfa_setup():
    users = load_users()
    user = users.get(SYSTEM_USERNAME)
    error = ""
    if not user:
        return redirect(url_for("login"))
    secret = user["totp_secret"]
    provisioning_uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=f"{SYSTEM_USERNAME}@CAAdmin", issuer_name="CAAdmin"
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
    return render_template("mfa_setup.html", error=error, qr_b64=qr_b64, secret=secret)

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

@app.route("/select_ca", methods=["POST"])
def select_ca():
    ca_name = request.form.get("ca_name")
    if ca_name and ca_name in list_cas():
        session["active_ca"] = ca_name
    return redirect(url_for("index"))

@app.route("/import_ca", methods=["GET", "POST"])
def import_ca():
    if not check_auth():
        return redirect(url_for("login"))
    if request.method == "POST":
        ca_name = request.form.get("ca_name")
        ca_cert = request.files.get("ca_cert")
        ca_key = request.files.get("ca_key")
        if not ca_name or not ca_cert or not ca_key:
            flash("All fields are required!")
            return redirect(url_for("import_ca"))
        ca_path = os.path.join(CA_DIR, ca_name)
        if not os.path.exists(ca_path):
            os.makedirs(ca_path)
        ca_cert.save(os.path.join(ca_path, "ca.crt"))
        ca_key.save(os.path.join(ca_path, "ca.key"))
        session["active_ca"] = ca_name
        flash("CA imported successfully.")
        return redirect(url_for("index"))
    return render_template("import_ca.html")

@app.route("/generate_ca", methods=["GET", "POST"])
def generate_ca():
    if not check_auth():
        return redirect(url_for("login"))
    if request.method == "POST":
        ca_name = request.form.get("ca_name")
        subj = request.form.get("subject", "/CN=MyCA")
        days = request.form.get("days", "3650")
        if not ca_name:
            flash("CA name is required!")
            return redirect(url_for("generate_ca"))
        ca_path = os.path.join(CA_DIR, ca_name)
        if not os.path.exists(ca_path):
            os.makedirs(ca_path)
        ca_key = os.path.join(ca_path, "ca.key")
        ca_crt = os.path.join(ca_path, "ca.crt")
        subprocess.run(["openssl", "genrsa", "-out", ca_key, "4096"], check=True)
        subprocess.run([
            "openssl", "req", "-x509", "-new", "-nodes",
            "-key", ca_key, "-sha256", "-days", days,
            "-out", ca_crt, "-subj", subj
        ], check=True)
        session["active_ca"] = ca_name
        flash("CA generated successfully.")
        return redirect(url_for("index"))
    return render_template("generate_ca.html")

@app.route("/generate_cert", methods=["GET", "POST"])
def generate_cert():
    if not check_auth():
        return redirect(url_for("login"))
    active_ca = get_active_ca()
    error = ""
    if not active_ca:
        error = "No CA available. Please import or generate a CA first."
        return render_template("generate_cert.html", error=error, active_ca=active_ca)
    if request.method == "POST":
        cert_type = request.form.get("cert_type", "server")
        common_name = request.form.get("common_name", "myhost")
        ca_path = os.path.join(CA_DIR, active_ca)
        ca_key = os.path.join(ca_path, "ca.key")
        ca_crt = os.path.join(ca_path, "ca.crt")
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                key_path = os.path.join(tmpdir, f"{cert_type}.key")
                csr_path = os.path.join(tmpdir, f"{cert_type}.csr")
                crt_path = os.path.join(tmpdir, f"{cert_type}.crt")
                subprocess.run(["openssl", "genrsa", "-out", key_path, "2048"], check=True)
                subprocess.run([
                    "openssl", "req", "-new", "-key", key_path, "-out", csr_path,
                    "-subj", f"/CN={common_name}"
                ], check=True)
                subprocess.run([
                    "openssl", "x509", "-req", "-in", csr_path, "-CA", ca_crt, "-CAkey", ca_key, "-CAcreateserial",
                    "-out", crt_path, "-days", "365", "-sha256"
                ], check=True)
                zip_base = os.path.join(tmpdir, f"{cert_type}_bundle")
                shutil.make_archive(zip_base, 'zip', tmpdir)
                zip_path = zip_base + ".zip"
                return send_file(zip_path, as_attachment=True, download_name=f"{cert_type}_bundle.zip")
        except Exception as e:
            error = f"Error generating certificate: {e}"
    return render_template("generate_cert.html", error=error, active_ca=active_ca)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
