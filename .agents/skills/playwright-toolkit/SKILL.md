---
name: playwright-toolkit
description: Playwright 本机工具箱：npmmirror 镜像装 Chromium、cookie 注入开登录态页面、SPA 接口抓取（response 监听一击必中）、表单/文件上传自动化。当任务需要真实浏览器渲染/登录态/抓网页背后的 XHR 接口，或用户说"用 Playwright/抓接口/浏览器自动化/装 Chromium/浏览器镜像"时使用。B 站投稿（biliup 技能）等站点级工作流以本工具箱为子集。
---

# Playwright 工具箱

本机已实战验证（2026-10-07 B 站代码投稿一战），三条核心能力：
**装得快（npmmirror 镜像）、进得去（cookie 注入）、挖得出（XHR 监听）**。

## 0. 环境状态（先查再装）

- Python venv：`C:\Users\12696\Documents\z-code\text\xiyouji\sdbgj\.venv`（已装 playwright）
- 浏览器：`C:\Users\12696\AppData\Local\ms-playwright\chromium-1243`（153.0.8010）
- 验证：`python -c "from playwright.sync_api import sync_playwright; ..."`

## 1. 新机器安装配方（国内不卡）

```bash
PY=<venv>/Scripts/python.exe
"$PY" -m pip install playwright -i https://pypi.tuna.tsinghua.edu.cn/simple
export PLAYWRIGHT_DOWNLOAD_HOST=https://cdn.npmmirror.com/binaries/playwright
"$PY" -m playwright install chromium
```

要点：
- **必须设 `PLAYWRIGHT_DOWNLOAD_HOST`**，否则浏览器走 playwright.cdntest 官方源慢/失败
- Windows 上 `--with-deps` 只会多拉一个 winldd，可省
- 装完落 `%LOCALAPPDATA%\ms-playwright\`

## 2. cookie 注入 = 登录态的唯二正道之一

```python
ctx = b.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) ... Chrome/131",
                    viewport={"width":1600,"height":900})   # 必设完整 UA，默认 headless UA 会被风控
ctx.add_cookies([{"name": k, "value": v, "domain": ".xxx.com", "path": "/"}
                 for k, v in cookies_dict.items()])
```

cookie 来源两条正道：
1. **目标站扫码登录 API**（推荐；完整范例见 biliup 技能：generate 出二维码 → cmd start 弹图 → poll 轮询 → Set-Cookie 响应头里拿会话字段）
2. 用户提供的 cookies.json

**邪路（勿走）**：偷运行中浏览器的 cookie 库——Chromium 127+ 全 v20 app-bound 加密，DPAPI 用户密钥解不开（InvalidTag），绕过需伪装浏览器进程=入侵技术；Edge/Chrome 默认 profile 已禁 `--remote-debugging-port`（CDP 连不上）。死路别再试。

## 3. SPA 接口考古 = response 监听（本工具箱的灵魂）

页面是 JS 壳时（静态 HTML 里挖不到 API、盲猜端点全 404），让**页面自己暴露**：

```python
caps = []
page.on("response", lambda r: caps.append({"url": r.url, "status": r.status,
      "body": (r.text()[:20000] if any(s in r.url for s in KEYWORDS) else "")}))
page.goto(URL, wait_until="domcontentloaded", timeout=60000)  # networkidle 常等不到
time.sleep(12)                                                # 给异步 XHR 时间
```

- 免启动版脚本：`scripts/capture_xhr.py --url ... --cookies ... --match "x/|api" --domain .xxx.com`
- 产出 `pw_xhrs.json`（URL+响应体）+ `pw_page.txt`（页面文本=看渲染结果）
- 找数据接口：grep 响应体里的特征字符串（如分 P 标题），一发命中
- 埋点/日志请求巨多，KEYWORDS 过滤；`api.` `member.` `x/` 是常见 API 域段

## 4. 表单与文件上传

- 文件选择：`page.set_input_files("input[type=file]", path)` —— **无原生对话框**，这是对 computer-use GUI 中继的降维打击
- 表单：`page.fill/locator.click`，等待 `page.wait_for_selector`

## 5. 坑册（全是实弹）

| 坑 | 解 |
|---|---|
| `wait_until="networkidle"` 超时 | 长连接/轮询站点永远等不到 → `domcontentloaded` + `sleep(10~15)` |
| 默认 headless UA 被风控/空白页 | `new_context(user_agent=完整桌面UA)` |
| 响应体 `resp.text()` 抛异常 | 二进制/已释放 → try 包住记 `<binary>` |
| 后台 Bash 里 heredoc 追加文件 | **会静默丢失**（stdin 未接）→ 用 Edit 工具或前台跑 |
| `python x.py \| tail` 吞退出码 | 假成功陷阱 → `set -o pipefail`，或后台任务读完整日志 |
| 中文路径/参数在 MSYS bash | python -c 里用 `C:/` 不用 `/c/`；`$ _` 等会被路径转换 → 写进 .ps1/.py 文件再调 |

## 6. 站点级应用（以本工具箱为子集）

- **biliup 技能**：B 站全代码投稿（扫码登录→本工具抓稿件接口→upos 分片→edit 编辑分 P），
  实录在其 `references/full-case-20261007.md`，可运行代码 `text/xiyouji/bili_up/`。
- 新站点工作流照此模式拆：通用手法留在本技能，站点端点/业务规则独立成技能。

