# Hide My Email iCloud Manager

一个本地 Web UI，用来管理 Apple iCloud 的 Hide My Email 别名。

这个版本支持两种方式：

- **账号登录模式**：直接输入 Apple ID / 密码，支持 **美国区** 与 **中国区**，并把 session / cookiejar 持久化到本地。
- **手动 Cookies 模式**：兼容旧版 `cookies.txt` 用法。

> 注意：这里实现的是“**本地持久化登录态**”，不是永不过期。Apple 仍可能在一段时间后要求重新登录或重新做 2FA。

## 功能

- 本地 Web UI 管理 Hide My Email
- 支持 **美国区 / 中国区** Apple ID 登录
- 本地持久化 session / cookiejar
- 支持 2FA 验证流程
- **支持保存多个账号并直接切换**
- **切换账号时优先复用本地 session，尽量避免重新登录 / 重新 2FA**
- **每个账号独立保存列表缓存、cookies 快照、导出文件**
- 浏览器内编辑和保存 `cookies.txt`
- 拉取、搜索、筛选别名
- 批量停用 / 删除选中别名
- 自动导出当前活动账号的最新列表到 `emails.txt`

## 安装

### 1. 克隆仓库

```bash
git clone https://github.com/spacex-3/Hide-My-Email-iCloud-Manager.git
cd Hide-My-Email-iCloud-Manager
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

## 启动 Web UI

```bash
python server.py
```

然后打开：

```text
http://127.0.0.1:8000
```

## 登录模式

页面里可以直接：

1. 选择区服：
   - `美国区`
   - `中国区`
2. 输入 Apple ID 和密码
3. 点击“账号登录”
4. 如果需要 2FA：
   - 点击“触发验证码”
   - 输入验证码
   - 点击“验证”

登录成功后：

- 本地 session 会保存到 `.pyicloud/`
- 当前 cookies 快照会保存到账号对应的本地快照文件
- 当前活动账号的 cookies 也会同步到顶层 `cookies.txt`
- 当前活动账号的列表也会同步到顶层 `emails.txt`
- 后续重新打开页面时会优先尝试复用本地 session

## 多账号持久化与切换

支持保存多个已经登录过的账号。

### 行为说明

- 每个账号都会按 **Apple ID + 区服** 单独保存本地资料
- 每个账号都有自己的：
  - session / cookiejar
  - cookies 快照
  - Hide My Email 列表缓存
- 前端左侧会显示“**已保存账号**”列表
- 点击某个已保存账号后，会：
  - 切换当前活动账号
  - 优先复用该账号已有 session
  - 如果本地存在该账号的列表缓存，也会同步显示该账号对应缓存

### 什么时候不需要重新登录 / 2FA

如果该账号本地 session 仍然有效：

- 切换账号时通常**不需要重新输入密码**
- 也通常**不需要重新做 2FA**

如果 Apple 让该账号 session 失效了：

- 账号仍然会保留在“已保存账号”列表里
- 该账号之前缓存的列表仍可显示
- 但要继续实时刷新时，需要重新登录一次

## 列表缓存与导出

当前实现里，**每个账号的列表缓存是独立的**。

### 账号级缓存文件

保存在：

```text
.pyicloud/lists/
```

通常包括：

- `*.json`：结构化缓存
- `*.txt`：文本导出缓存

### 当前活动账号的同步导出

为了兼容旧流程，当前活动账号还会同步到仓库根目录：

- `emails.txt`
- `cookies.txt`

所以：

- **账号级缓存** 用于多账号区分
- **根目录文件** 仅表示当前活动账号

## 手动 Cookies 模式

如果你仍然想手动维护 cookies：

```bash
cp cookies.txt.template cookies.txt
```

格式示例：

```python
cookies = {
    'X-APPLE-WEBAUTH-USER': '"v=1:s=0:d=YOUR_DSID"',
    'X-APPLE-WEBAUTH-TOKEN': '"v=2:t=YOUR_TOKEN"',
    'X-APPLE-DS-WEB-SESSION-TOKEN': '"YOUR_SESSION_TOKEN"',
    # ... add all other required cookies here
}
```

页面里也可以直接编辑并保存 `cookies.txt`。

## Web UI 行为

- 启动 `server.py` **不会自动删除** 别名
- 更新 `cookies.txt` **不会自动删除** 别名
- “刷新列表”只会拉取当前活动账号列表并更新缓存 / 导出文件
- 只有在你明确选择行并确认后，才会执行停用或删除

## 项目结构

```text
server.py              本地 HTTP 服务
hme_core.py            登录态、账号切换、列表缓存、Hide My Email 核心逻辑
web/index.html         前端结构
web/app.js             前端交互
web/styles.css         前端样式
cookies.txt.template   手动 Cookie 模板
```

## 隐私与本地文件

以下文件/目录默认不会提交到 Git：

- `cookies.txt`
- `emails.txt`
- `.pyicloud/`
- `venv/`
- `__pycache__/`
- `.DS_Store`

不要把真实 iCloud cookies、session 文件、账号快照或账号信息提交到远程仓库。

## 导出格式

`emails.txt` 示例：

```text
anonymousId: abc123... | email: xyz@icloud.com | active: True
anonymousId: def456... | email: abc@icloud.com | active: False
```

## 依赖

- Python 3.7+
- `requests`
- `rich`
- `pyicloud`

## 说明

- 中国区登录会走 `*.apple.com.cn / *.icloud.com.cn` 相关端点
- 持久化 session 主要用于减少重复登录和重复 2FA
- 多账号切换依赖本地保存的 session 是否仍然有效
- Apple 的风控、session 过期时间、2FA 重新验证周期仍由 Apple 决定

## License

MIT License. See `LICENSE` for details.
