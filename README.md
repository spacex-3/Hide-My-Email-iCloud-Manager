# Hide My Email iCloud Manager

一个本地 Web UI，用来管理 Apple iCloud 的 Hide My Email 别名。

这个版本支持两种方式：

- **账号登录模式**：直接输入 Apple ID / 密码，支持 **美国区** 与 **中国区**，并把 session / cookiejar 持久化到本地，尽量减少反复登录。
- **手动 Cookies 模式**：兼容旧版 `cookies.txt` 用法。

> 注意：这里实现的是“**本地持久化登录态**”，不是永不过期。Apple 仍可能在一段时间后要求重新登录或重新做 2FA。

## 功能

- 本地 Web UI 管理 Hide My Email
- 支持 **美国区 / 中国区** Apple ID 登录
- 本地持久化 session / cookiejar
- 支持 2FA 验证流程
- 浏览器内编辑和保存 `cookies.txt`
- 拉取、搜索、筛选别名
- 批量停用 / 删除选中别名
- 自动导出最新列表到 `emails.txt`

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
   - 点击“触发验证码 / 设备提示”
   - 输入验证码
   - 点击“验证 2FA”

登录成功后：

- 本地 session 会保存到 `.pyicloud/`
- 当前 cookies 快照会导出到 `cookies.txt`
- 后续重新打开页面时会优先尝试复用本地 session

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
- “刷新列表”只会拉取列表并更新 `emails.txt`
- 只有在你明确选择行并确认后，才会执行停用或删除

## 项目结构

```text
server.py              本地 HTTP 服务
hme_core.py            登录态、Cookie、Hide My Email 核心逻辑
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

不要把真实 iCloud cookies、session 文件或账号信息提交到远程仓库。

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
- Apple 的风控、session 过期时间、2FA 重新验证周期仍由 Apple 决定

## License

MIT License. See `LICENSE` for details.
