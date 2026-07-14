import os
import sqlite3
import secrets
from urllib.parse import quote
from flask import Flask, render_template, request, redirect, session, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24).hex())
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB


def generate_csrf_token():
    """生成 CSRF Token 并存入 session"""
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)
    return session["csrf_token"]


def validate_csrf_token():
    """验证 CSRF Token"""
    token = request.form.get("csrf_token")
    stored = session.get("csrf_token")
    return token and stored and token == stored

# ========== 数据库初始化 ==========

def init_db():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect("data/users.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT,
            phone TEXT
        )
    """)
    # 插入默认用户（使用 INSERT OR IGNORE 防止重复）
    c.execute("INSERT OR IGNORE INTO users (username, password, email, phone) VALUES ('admin', 'admin123', 'admin@example.com', '13800138000')")
    c.execute("INSERT OR IGNORE INTO users (username, password, email, phone) VALUES ('alice', 'alice2025', 'alice@example.com', '13900139001')")
    conn.commit()
    conn.close()
    print("[DB] 数据库初始化完成")

    # 确保数据库表有 balance 字段（兼容旧数据库）
    try:
        conn2 = sqlite3.connect("data/users.db")
        conn2.execute("ALTER TABLE users ADD COLUMN balance REAL DEFAULT 0")
        conn2.commit()
        conn2.close()
    except Exception:
        pass  # 字段已存在，忽略

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
        user_info = dict(USERS[username])  # 复制一份，避免修改原字典
        # 从数据库获取实时余额（充值后同步）
        try:
            conn = sqlite3.connect("data/users.db")
            c = conn.cursor()
            c.execute("SELECT balance, id FROM users WHERE username = ?", (username,))
            row = c.fetchone()
            conn.close()
            if row:
                user_info["balance"] = row[0]
                user_info["id"] = row[1]
        except Exception:
            pass  # 数据库出错时使用内存中的默认值
    return render_template("index.html", user=user_info, search_results=None, keyword="", page_content=None)


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
            user_info = dict(USERS[username])
            # 从数据库获取实时余额和 ID
            try:
                conn2 = sqlite3.connect("data/users.db")
                c2 = conn2.cursor()
                c2.execute("SELECT balance, id FROM users WHERE username = ?", (username,))
                row = c2.fetchone()
                conn2.close()
                if row:
                    user_info["balance"] = row[0]
                    user_info["id"] = row[1]
            except Exception:
                pass
            return render_template("index.html", user=user_info, page_content=None)

        record_failure(client_ip)
        return render_template("login.html", error="用户名或密码错误")

    msg = request.args.get("msg", "")
    return render_template("login.html", msg=msg)


@app.route("/report")
def download_report():
    return send_from_directory(".", "第5轮_文件包含漏洞审计报告.pdf", as_attachment=True)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        email = request.form.get("email")
        phone = request.form.get("phone")

        # 使用参数化查询防止 SQL 注入
        sql = "INSERT INTO users (username, password, email, phone) VALUES (?, ?, ?, ?)"
        print(f"[SQL] {sql} | 参数: username={username}, password={password}, email={email}, phone={phone}", flush=True)
        conn = sqlite3.connect("data/users.db")
        c = conn.cursor()
        try:
            c.execute(sql, (username, password, email, phone))
            conn.commit()
            return redirect("/login?msg=注册成功，请登录")
        except Exception as e:
            conn.rollback()
            return render_template("register.html", error="注册失败，用户名可能已被占用")
        finally:
            conn.close()

    return render_template("register.html")


@app.route("/search", methods=["GET"])
def search():
    keyword = request.args.get("keyword", "")

    # 使用参数化查询防止 SQL 注入
    sql = "SELECT id, username, email, phone FROM users WHERE username LIKE ? OR email LIKE ?"
    params = (f"%{keyword}%", f"%{keyword}%")
    print(f"[SQL] {sql} | 参数: keyword={keyword}", flush=True)

    results = []
    if keyword:
        conn = sqlite3.connect("data/users.db")
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        try:
            c.execute(sql, params)
            rows = c.fetchall()
            for row in rows:
                results.append(dict(row))
            print(f"[SQL] 命中 {len(results)} 条记录", flush=True)
        except Exception as e:
            print(f"[SQL] 查询出错: {e}")
        finally:
            conn.close()

    username = session.get("username")
    user_info = None
    if username and username in USERS:
        user_info = dict(USERS[username])
        try:
            conn2 = sqlite3.connect("data/users.db")
            c2 = conn2.cursor()
            c2.execute("SELECT balance, id FROM users WHERE username = ?", (username,))
            row = c2.fetchone()
            conn2.close()
            if row:
                user_info["balance"] = row[0]
                user_info["id"] = row[1]
        except Exception:
            pass
    return render_template("index.html", user=user_info, search_results=results, keyword=keyword, page_content=None)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/upload", methods=["GET", "POST"])
def upload():
    if "username" not in session:
        return redirect("/login")

    if request.method == "POST":
        f = request.files.get("file")
        if f is None or f.filename == "":
            return render_template("upload.html", error="请选择要上传的文件")

        # ===== 修复：只允许图片文件 =====
        # 1. 检查文件后缀名
        ALLOWED = {"png", "jpg", "jpeg", "gif", "webp"}
        ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
        if ext not in ALLOWED:
            return render_template("upload.html", error=f"只允许上传图片文件，当前类型: .{ext}")

        # 2. 使用安全文件名（移除路径和特殊字符）
        from werkzeug.utils import secure_filename
        safe_name = secure_filename(f.filename)

        # 保存文件
        upload_dir = os.path.join(app.root_path, "static", "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        save_path = os.path.join(upload_dir, safe_name)
        f.save(save_path)

        file_url = f"/static/uploads/{safe_name}"
        return render_template("upload.html", file_url=file_url, filename=safe_name)

    return render_template("upload.html")


@app.route("/profile", methods=["GET"])
def profile():
    # 只允许查看自己的个人中心，从 session 获取当前用户
    username = session.get("username")
    if not username:
        return redirect("/login")

    conn = sqlite3.connect("data/users.db")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT id, username, email, phone, balance FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    conn.close()

    if row is None:
        return render_template("profile.html", error="用户不存在", user=None)

    # 获取充值结果提示信息（从 recharge 重定向带过来的）
    msg = request.args.get("msg", "")
    return render_template("profile.html", user=dict(row), error=None, msg=msg, csrf_token=generate_csrf_token())


@app.route("/recharge", methods=["POST"])
def recharge():
    # 修复1：必须登录才能充值
    if "username" not in session:
        return redirect("/login")

    # CSRF Token 校验
    if not validate_csrf_token():
        return redirect("/profile?msg=" + quote("充值失败，CSRF Token 无效"))

    user_id = request.form.get("user_id")
    amount = request.form.get("amount", "0")

    try:
        amount_num = float(amount)
    except ValueError:
        return redirect("/profile?msg=" + quote("充值失败，金额格式不正确"))

    # 修复2：单次充值金额限制在 ±10000
    if abs(amount_num) > 10000:
        return redirect("/profile?msg=" + quote("充值失败，单次金额不能超过10000"))

    conn = sqlite3.connect("data/users.db")
    c = conn.cursor()
    # 修复3：余额不低于 0
    c.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
    row = c.fetchone()
    if row is None:
        conn.close()
        return redirect("/profile?msg=" + quote("充值失败，用户不存在"))

    current_balance = row[0]
    new_balance = current_balance + amount_num
    if new_balance < 0:
        conn.close()
        return redirect("/profile?msg=" + quote("充值失败，余额不能为负数"))

    c.execute("UPDATE users SET balance = ? WHERE id = ?", (new_balance, user_id))
    conn.commit()
    conn.close()

    return redirect("/profile?msg=" + quote(f"充值成功，当前余额: {new_balance}"))


@app.route("/change-password", methods=["POST"])
def change_password():
    if "username" not in session:
        return redirect("/login")

    # CSRF Token 校验
    if not validate_csrf_token():
        return redirect("/profile?msg=" + quote("密码修改失败，CSRF Token 无效"))

    username = request.form.get("username")
    new_password = request.form.get("new_password")

    if not username or not new_password:
        return redirect("/profile?msg=" + quote("密码修改失败，参数不完整"))

    # 更新内存中的密码哈希
    if username in USERS:
        USERS[username]["password"] = generate_password_hash(new_password)

    # 同时更新 SQLite 数据库中的密码
    conn = sqlite3.connect("data/users.db")
    c = conn.cursor()
    c.execute("UPDATE users SET password = ? WHERE username = ?", (new_password, username))
    conn.commit()
    conn.close()

    return redirect("/profile?msg=" + quote(f"密码修改成功，用户 {username} 的新密码已生效"))


@app.route("/page", methods=["GET"])
def page():
    name = request.args.get("name", "")

    # 修复路径遍历漏洞：规范化路径并检查是否在 pages 目录内
    pages_dir = os.path.join(os.path.dirname(__file__), "pages")
    requested_path = os.path.abspath(os.path.join(pages_dir, name))

    page_content = None
    if not requested_path.startswith(os.path.abspath(pages_dir) + os.sep):
        page_content = "页面不存在"
    elif os.path.isfile(requested_path):
        with open(requested_path, "r", encoding="utf-8") as f:
            page_content = f.read()
    else:
        # 尝试加上 .html 后缀
        requested_path_html = requested_path + ".html"
        if os.path.isfile(requested_path_html):
            with open(requested_path_html, "r", encoding="utf-8") as f:
                page_content = f.read()
        else:
            page_content = "页面不存在"

    username = session.get("username")
    user_info = None
    if username and username in USERS:
        user_info = USERS[username]
    return render_template("index.html", user=user_info, search_results=None, keyword="", page_content=page_content)


if __name__ == "__main__":
    init_db()
    # 确保上传目录存在
    os.makedirs(os.path.join(os.path.dirname(__file__), "static", "uploads"), exist_ok=True)
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"

    # 如果端口被占用，先杀死旧进程再启动
    import subprocess, signal
    try:
        result = subprocess.run(
            ["lsof", "-ti", ":5000"],
            capture_output=True, text=True, timeout=5
        )
        if result.stdout.strip():
            old_pid = result.stdout.strip()
            os.kill(int(old_pid), signal.SIGKILL)
            print(f"[启动] 已杀死旧进程 PID={old_pid}，释放端口 5000")
    except Exception:
        pass  # 没有旧进程或无法杀死，直接启动

    app.run(debug=debug_mode, host="0.0.0.0", port=5000)
