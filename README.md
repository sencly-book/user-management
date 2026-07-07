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

| # | 漏洞 | 严重程度 | 描述 |
|:-:|:----|:-------:|:----|
| 1 | **密码明文存储** | 🔴 严重 | 密码以明文硬编码在 `USERS` 字典中，代码泄露即密码泄露 |
| 2 | **密码明文展示** | 🔴 严重 | 首页模板直接渲染 `{{ user.password }}`，用户密码显示在浏览器上 |
| 3 | **明文密码比对** | 🔴 严重 | 使用 `==` 直接比较密码字符串，数据库泄露可被直接利用 |
| 4 | **HTML 注释泄密** | 🔴 严重 | `login.html` 顶部 HTML 注释明码写着`admin / admin123`，查看源代码即得 |
| 5 | **页面提示默认密码** | 🟡 中危 | 登录页底部显示`默认账号：admin / admin123`，对所有访客公开 |
| 6 | **Secret Key 过弱** | 🔴 严重 | `secret_key = "dev-key-2025"` 为固定弱密钥，可伪造任意用户 session |
| 7 | **无登录限流** | 🟡 中危 | 登录接口无频率限制，可无限暴力穷举密码 |
| 8 | **Debug 模式** | 🟡 中危 | `debug=True` 出错时暴露源码路径和调用栈 |

---

## 🔧 修复方法与结果

| # | 修复方法 | 修复后 |
|:-:|:--------|:------:|
| 1 | 使用 `werkzeug.security.generate_password_hash()` 进行 bcrypt 风格哈希 | ✅ 密码以哈希值存储，原文不保留 |
| 2 | 从 `index.html` 模板中删除 `{{ user.password }}` | ✅ 首页不再显示密码字段 |
| 3 | 改用 `check_password_hash(哈希值, 输入)` 安全比对 | ✅ 比对过程不涉及明文密码 |
| 4 | 删除 `login.html` 中的调试注释 | ✅ 查看源码不再泄露账号 |
| 5 | 删除登录页底部提示文字 | ✅ 默认账号不再对外公开 |
| 6 | 改为 `os.environ.get("SECRET_KEY", os.urandom(24).hex())` | ✅ 密钥不可预测，优先从环境变量读取 |
| 7 | 基于 IP 的失败计数器，5 次失败后封禁 5 分钟 | ✅ 暴力破解被有效拦截 |
| 8 | 通过 `FLASK_DEBUG` 环境变量控制，默认关闭 | ✅ 生产环境不暴露调试信息 |

### 改动文件一览

| 文件 | 变更 |
|:----|:----|
| `app.py` | 密码哈希存储/比对、Secret Key 环境变量、IP 限流、Debug 环境变量控制 |
| `templates/login.html` | 删除 HTML 注释和默认账号提示 |
| `templates/index.html` | 删除密码字段展示 |
| `CHANGELOG_SECURITY.md` | 完整的安全修复日志 |

---

## 📁 项目结构

```
user-management/
├── app.py                    # Flask 主应用
├── .gitignore                # Git 忽略规则
├── CHANGELOG_SECURITY.md     # 安全修复日志
├── README.md                 # 本文件
├── static/
│   └── css/
│       └── style.css         # 导航栏、卡片、表单样式
└── templates/
    ├── base.html             # 基础模板（导航栏 + 布局）
    ├── index.html            # 首页（用户信息展示）
    └── login.html            # 登录页
```

---

## 📄 路由说明

| 路由 | 方法 | 说明 |
|:----|:----|:----|
| `/` | GET | 首页，已登录显示用户信息，未登录提示跳转 |
| `/login` | GET/POST | 登录页/提交登录 |
| `/logout` | GET | 登出并跳转首页 |

---

## 🧪 测试限流功能

```bash
# 连续 5 次输入错误密码，第 5 次会被封禁
for i in $(seq 1 5); do
  curl -X POST http://localhost:5000/login -d "username=admin&password=wrong$i"
done
# 第 5 次返回："登录失败次数过多，请 5 分钟后再试"
```
