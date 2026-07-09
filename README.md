# 用户信息管理平台

一个基于 Python Flask 的简易用户信息管理平台，**故意引入安全漏洞后逐步修复**，作为 Web 安全教学示例。

---

## 🚀 快速搭建

### 环境要求

- Python 3.8+
- pip

### 安装与运行

```bash
# 1. 安装 Flask
pip install flask

# 2. 启动服务
python app.py

# 3. 访问
#    http://localhost:5000
```

服务默认监听 `0.0.0.0:5000`（所有网卡），默认关闭 debug 模式。

### 环境变量（可选）

```bash
export SECRET_KEY="your-strong-secret"   # session 密钥，默认自动生成
export FLASK_DEBUG="true"                # 开启 debug 模式，默认 false
```

### 默认用户

| 用户名 | 密码 | 角色 | 邮箱 | 余额 |
|-------|------|------|-----|:----:|
| admin | admin123 | admin | admin@example.com | 99999 |
| alice | alice2025 | user | alice@example.com | 100 |

---

## ⚠️ 原本存在的漏洞

> 以下漏洞系**故意引入**，用于演示常见 Web 安全风险。

### 第一轮：密码安全漏洞（8 项）

| # | 漏洞 | 严重程度 | 描述 |
|:-:|:----|:-------:|:----|
| 1 | **密码明文存储** | 🔴 严重 | 密码以明文硬编码在 `USERS` 字典中 |
| 2 | **密码明文展示** | 🔴 严重 | 首页模板渲染 `{{ user.password }}` |
| 3 | **明文密码比对** | 🔴 严重 | 使用 `==` 直接比较密码字符串 |
| 4 | **HTML 注释泄密** | 🔴 严重 | 登录页 HTML 注释明码写着 `admin / admin123` |
| 5 | **页面提示默认密码** | 🟡 中危 | 登录页底部公开显示默认账号密码 |
| 6 | **Secret Key 过弱** | 🔴 严重 | `secret_key = "dev-key-2025"` 可伪造 session |
| 7 | **无登录限流** | 🟡 中危 | 可无限暴力穷举密码 |
| 8 | **Debug 模式** | 🟡 中危 | 出错时暴露源码路径和调用栈 |

### 第二轮：SQL 注入漏洞（2 项）

| # | 漏洞 | 严重程度 | 描述 |
|:-:|:----|:-------:|:----|
| 9 | **搜索功能 SQL 注入** | 🔴 严重 | `keyword` 参数直接拼入 `LIKE` 子句，可注入任意 SQL |
| 10 | **注册功能 SQL 注入** | 🔴 严重 | 四个表单字段均直接拼入 `INSERT` 语句 |

#### SQL 注入攻击演示

```
# 搜索注入 — 查询全部用户（' OR '1'='1）
GET /search?keyword=' OR '1'='1
→ SELECT * FROM users WHERE username LIKE '%' OR '1'='1%'
→ 返回数据库中所有用户

# 搜索注入 — 读取数据库结构（UNION SELECT）
GET /search?keyword=' UNION SELECT name,sql,2,3 FROM sqlite_master--
→ 读取到完整的建表语句和系统表信息

# 注册注入 — 插入恶意数据
POST /register  username="hacker', 'hacked', ...); --"
→ 原 SQL: INSERT INTO users VALUES ('hacker', 'hacked', ...); --', ...)
```

### 第三轮：文件上传漏洞（1 项）

| # | 漏洞 | 严重程度 | 描述 |
|:-:|:----|:-------:|:----|
| 11 | **任意文件上传** | 🔴 严重 | 上传接口无文件类型检查，可上传 .html、.py、.bat 等危险文件 |

#### 攻击演示

```bash
# 上传 HTML → XSS 攻击（窃取 Cookie）
echo '<script>alert(document.cookie)</script>' > hack.html
curl -F "file=@hack.html;filename=hack.html" http://localhost:5000/upload
# 任何用户访问 /static/uploads/hack.html 就会触发 JS

# 上传 .py 脚本
curl -F "file=@shell.py;filename=shell.py" http://localhost:5000/upload

# 路径遍历（../../etc 写文件到上级目录）
curl -F "file=@evil.txt;filename=../../static/evil.txt" http://localhost:5000/upload
```

---

## 🔧 修复方法与结果

### 第一轮修复：密码安全

| # | 修复方法 | 修复后 |
|:-:|:--------|:------:|
| 1 | `generate_password_hash()` bcrypt 风格哈希 | ✅ 密码以哈希值存储 |
| 2 | 删除 `{{ user.password }}` | ✅ 首页不再显示密码 |
| 3 | `check_password_hash()` 安全比对 | ✅ 比对不涉及明文 |
| 4 | 删除 HTML 注释 | ✅ 源码不再泄露账号 |
| 5 | 删除登录页提示文字 | ✅ 默认账号不再公开 |
| 6 | 环境变量 + `os.urandom()` 随机密钥 | ✅ 密钥不可预测 |
| 7 | IP 计数器，5 次失败封禁 5 分钟 | ✅ 暴力破解被拦截 |
| 8 | `FLASK_DEBUG` 环境变量控制，默认关闭 | ✅ 不暴露调试信息 |

### 第二轮修复：SQL 注入

| # | 修复方法 | 修复后 |
|:-:|:--------|:------:|
| 9 | 搜索改用 `WHERE username LIKE ?` 参数化查询 | ✅ 用户输入仅作为数据，不解析为 SQL |
| 10 | 注册改用 `INSERT ... VALUES (?, ?, ?, ?)` 参数化查询 | ✅ SQL 注入 100% 被拦截 |

#### 代码级对比

```python
# ❌ 修复前（f-string 拼接，存在 SQL 注入）
sql = f"SELECT * FROM users WHERE username LIKE '%{keyword}%'"
c.execute(sql)

# ✅ 修复后（参数化查询，安全）
sql = "SELECT * FROM users WHERE username LIKE ?"
c.execute(sql, (f"%{keyword}%",))
```

### 第三轮修复：文件上传

| # | 修复方法 | 修复后 |
|:-:|:--------|:------:|
| 11 | 检查文件后缀 + `secure_filename()` 安全命名 | ✅ 仅允许图片上传，路径遍历被拦截 |

```python
# 修复：只允许图片 + 安全文件名
ALLOWED = {"png", "jpg", "jpeg", "gif", "webp"}
if ext not in ALLOWED:
    return render_template("upload.html", error="只允许上传图片")

from werkzeug.utils import secure_filename
safe_name = secure_filename(f.filename)
f.save(os.path.join(upload_dir, safe_name))
```

---

## 📁 项目结构

```
user-management/
├── app.py                    # Flask 主应用
├── .gitignore                # Git 忽略规则
├── CHANGELOG_SECURITY.md     # 安全修复日志
├── README.md                 # 本文件
├── data/
│   └── users.db              # SQLite 数据库
├── static/
│   ├── uploads/              # 上传文件目录
│   └── css/
│       └── style.css         # 导航栏、卡片、表单、表格样式
└── templates/
    ├── base.html             # 基础模板（导航栏 + 布局）
    ├── index.html            # 首页（用户信息 + 搜索）
    ├── login.html            # 登录页
    ├── register.html         # 注册页
    └── upload.html           # 头像上传页
```

---

## 📄 路由说明

| 路由 | 方法 | 说明 |
|:----|:----|:----|
| `/` | GET | 首页，已登录显示用户信息 + 搜索框 |
| `/login` | GET/POST | 登录页/提交登录 |
| `/register` | GET/POST | 注册页/提交注册 |
| `/search` | GET | 搜索用户（参数 `?keyword=xxx`） |
| `/logout` | GET | 登出并跳转首页 |
| `/upload` | GET/POST | 用户头像上传（已登录） |
| `/report` | GET | 下载安全漏洞审计报告 PDF |

---

## 🧪 测试

```bash
# 测试限流（连续 5 次错误密码）
for i in $(seq 1 5); do
  curl -X POST http://localhost:5000/login -d "username=admin&password=wrong$i"
done

# 测试 SQL 注入已被拦截
curl -s "http://localhost:5000/search?keyword=%27%20OR%20%271%27%3D%271"
# 返回"无搜索结果"，而不是全部用户
```
