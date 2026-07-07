# 安全修复日志

## 修复时间：2026-07-07

---

### 修复项 1：密码明文存储
- **问题描述**：`USERS` 字典中密码以明文字符串存储（`"admin123"`、`"alice2025"`）
- **风险等级**：🔴 严重
- **修复方案**：使用 `werkzeug.security.generate_password_hash()` 对密码进行 bcrypt 风格哈希存储，原始明文不保存在任何变量中
- **涉及文件**：`app.py` 第 12、19 行
- **改动前**：
  ```python
  "password": "admin123"
  ```
- **改动后**：
  ```python
  "password": generate_password_hash("admin123")
  ```

---

### 修复项 2：密码明文展示在前端页面
- **问题描述**：登录后首页 `/` 的模板将 `{{ user.password }}` 渲染到 HTML，用户密码原文直接显示在浏览器上
- **风险等级**：🔴 严重
- **修复方案**：从 `index.html` 模板中删除密码字段的渲染行
- **涉及文件**：`templates/index.html`
- **改动前**：
  ```html
  <li><span class="info-label">密码：</span>{{ user.password }}</li>
  ```
- **改动后**：已移除该行，用户信息列表仅展示用户名、邮箱、手机、角色、余额

---

### 修复项 3：明文密码比对
- **问题描述**：使用 `==` 直接比对明文密码字符串
- **风险等级**：🔴 严重
- **修复方案**：改用 `werkzeug.security.check_password_hash()` 进行安全比对，比对过程不涉及明文密码
- **涉及文件**：`app.py` 第 53 行
- **改动前**：
  ```python
  USERS[username]["password"] == password
  ```
- **改动后**：
  ```python
  check_password_hash(USERS[username]["password"], password)
  ```

---

### 修复项 4：HTML 注释泄露默认密码
- **问题描述**：`login.html` 顶部 HTML 注释中包含 `<!-- 调试信息 - 默认管理员账号 用户名: admin 密码: admin123 -->`，任何人查看页面源码即可获取管理员密码
- **风险等级**：🔴 严重
- **修复方案**：删除整行 HTML 注释
- **涉及文件**：`templates/login.html` 第 1 行
- **改动前**：`<!-- 调试信息 - 默认管理员账号 用户名: admin 密码: admin123 -->`
- **改动后**：已删除

---

### 修复项 5：页面明文提示默认账号
- **问题描述**：登录页底部展示 `<p class="login-hint">默认账号：admin / admin123</p>`，对所有访客可见
- **风险等级**：🟡 中等
- **修复方案**：删除该提示段落。管理员账号不应该公开
- **涉及文件**：`templates/login.html` 第 21 行
- **改动前**：`<p class="login-hint">默认账号：admin / admin123</p>`
- **改动后**：已删除

---

### 修复项 6：Secret Key 硬编码且过弱
- **问题描述**：`secret_key = "dev-key-2025"` 为固定弱密钥，攻击者可伪造 session 登录任意账户
- **风险等级**：🔴 严重
- **修复方案**：优先从环境变量 `SECRET_KEY` 读取；未设置时使用 `os.urandom(24).hex()` 生成随机密钥
- **涉及文件**：`app.py` 第 6 行
- **改动前**：
  ```python
  app.secret_key = "dev-key-2025"
  ```
- **改动后**：
  ```python
  app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24).hex())
  ```
- **说明**：如需固定密钥以便 session 跨重启保持有效，可通过环境变量注入：
  ```bash
  export SECRET_KEY="your-strong-random-key"
  ```

---

### 修复项 7：无登录失败次数限制
- **问题描述**：登录接口无任何频率限制，攻击者可无限次暴力破解密码
- **风险等级**：🟡 中等
- **修复方案**：基于 IP 的登录失败计数器，连续失败 5 次后临时封禁该 IP 5 分钟。5 分钟后自动解封
- **涉及文件**：`app.py` 第 36-52 行（新增 `LOGIN_FAILURES` 字典、`is_login_blocked()`、`record_failure()` 函数）
- **新增代码**：
  ```python
  LOGIN_FAILURES = {}

  def is_login_blocked(ip):
      if ip in LOGIN_FAILURES and LOGIN_FAILURES[ip]["count"] >= 5:
          import time
          if time.time() - LOGIN_FAILURES[ip]["first_failure"] < 300:
              return True
          else:
              del LOGIN_FAILURES[ip]
      return False

  def record_failure(ip):
      import time
      if ip not in LOGIN_FAILURES:
          LOGIN_FAILURES[ip] = {"count": 0, "first_failure": time.time()}
      LOGIN_FAILURES[ip]["count"] += 1
  ```

---

### 修复项 8：Debug 模式开启
- **问题描述**：`debug=True` 在出错时会显示详细调用栈，可能暴露源代码路径和环境变量
- **风险等级**：🟡 中等
- **修复方案**：通过环境变量 `FLASK_DEBUG` 控制 debug 模式，默认关闭
- **涉及文件**：`app.py` 第 76-77 行
- **改动前**：
  ```python
  app.run(debug=True, host="0.0.0.0", port=5000)
  ```
- **改动后**：
  ```python
  debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
  app.run(debug=debug_mode, host="0.0.0.0", port=5000)
  ```

---

## 修复汇总

| 序号 | 问题 | 原风险等级 | 修复后状态 |
|:---:|------|:---------:|:---------:|
| 1 | 密码明文存储 | 🔴 严重 | ✅ 已哈希 |
| 2 | 密码展示在页面 | 🔴 严重 | ✅ 已移除 |
| 3 | 明文密码比对 | 🔴 严重 | ✅ 已哈希比对 |
| 4 | HTML 注释泄密 | 🔴 严重 | ✅ 已删除 |
| 5 | 页面提示默认账号 | 🟡 中等 | ✅ 已删除 |
| 6 | Secret Key 过弱 | 🔴 严重 | ✅ 环境变量 + 随机 |
| 7 | 无登录限流 | 🟡 中等 | ✅ IP 封禁机制 |
| 8 | Debug 模式 | 🟡 中等 | ✅ 环境变量控制 |
