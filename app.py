import os
from flask import Flask, render_template, request, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24).hex())

USERS = {
    "admin": {
        "username": "admin",
        "password": generate_password_hash("admin123"),
        "role": "admin",
        "email": "admin@example.com",
        "phone": "13800138000",
        "balance": 99999
    },
    "alice": {
        "username": "alice",
        "password": generate_password_hash("alice2025"),
        "role": "user",
        "email": "alice@example.com",
        "phone": "13900139001",
        "balance": 100
    }
}

# 登录失败计数器（IP -> 失败次数）
LOGIN_FAILURES = {}


def is_login_blocked(ip):
    """检查 IP 是否已被临时封禁"""
    if ip in LOGIN_FAILURES and LOGIN_FAILURES[ip]["count"] >= 5:
        import time
        if time.time() - LOGIN_FAILURES[ip]["first_failure"] < 300:
            return True
        else:
            # 5 分钟后重置
            del LOGIN_FAILURES[ip]
    return False


def record_failure(ip):
    """记录一次登录失败"""
    import time
    if ip not in LOGIN_FAILURES:
        LOGIN_FAILURES[ip] = {"count": 0, "first_failure": time.time()}
    LOGIN_FAILURES[ip]["count"] += 1


@app.route("/")
def index():
    username = session.get("username")
    user_info = None
    if username and username in USERS:
        user_info = USERS[username]
    return render_template("index.html", user=user_info)


@app.route("/login", methods=["GET", "POST"])
def login():
    client_ip = request.remote_addr or "unknown"

    if request.method == "POST":
        # 检查 IP 是否被临时封禁
        if is_login_blocked(client_ip):
            return render_template("login.html", error="登录失败次数过多，请 5 分钟后再试")

        username = request.form.get("username")
        password = request.form.get("password")

        if username in USERS and check_password_hash(USERS[username]["password"], password):
            session["username"] = username
            # 登录成功，清除该 IP 的失败记录
            if client_ip in LOGIN_FAILURES:
                del LOGIN_FAILURES[client_ip]
            user_info = USERS[username]
            return render_template("index.html", user=user_info)

        record_failure(client_ip)
        return render_template("login.html", error="用户名或密码错误")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug_mode, host="0.0.0.0", port=5000)
