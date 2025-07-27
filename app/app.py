from flask import Flask, render_template_string, request, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_pam import PAM

app = Flask(__name__)
app.secret_key = 'change_this_secret_key'

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

pam = PAM()

class User(UserMixin):
    def __init__(self, username):
        self.id = username

@login_manager.user_loader
def load_user(username):
    return User(username)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if pam.authenticate(username, password):
            login_user(User(username))
            return redirect(url_for('index'))
        else:
            return render_template_string(LOGIN_FORM, error="Invalid credentials")
    return render_template_string(LOGIN_FORM)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return f"<h1>Welcome, {current_user.id}!</h1><br><a href='/logout'>Logout</a>"

LOGIN_FORM = '''
<!DOCTYPE html>
<html>
<head><title>Login</title></head>
<body>
    <h2>Login</h2>
    {% if error %}<p style="color: red;">{{ error }}</p>{% endif %}
    <form method="post">
        <input type="text" name="username" placeholder="Username" required autofocus /><br>
        <input type="password" name="password" placeholder="Password" required /><br>
        <input type="submit" value="Login" />
    </form>
</body>
</html>
'''

if __name__ == "__main__":
    context = ("/etc/ssl/certs/portal.easyswan.net.crt", "/etc/ssl/private/portal.easyswan.net.key")
    app.run(host="0.0.0.0", port=443, ssl_context=context)
