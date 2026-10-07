---
name: biliup
description: B 站（bilibili）全代码投稿：扫码登录拿 cookie → Playwright 抓稿件接口 → upos 分片直传 → edit 编辑稿件（更换分 P 视频文件 / 追加分 P），顺序保证、断点续传、不碰 GUI 文件对话框。用户说"传B站/投稿/投稿B站/换分P/追加分P/更换分P视频/B站上传"时使用。含 14P 实战实录。
---

# B 站全代码投稿

替代 GUI 中继（computer-use 点网页+原生文件框）的纯接口方案，2026-10-07 实战
（BV1zha96YEEX 换 P8/P9 + 追加 P10-P14，两次 edit 均 code 0）。

**可运行代码（本机真身，直接复用）**：`C:\Users\12696\Documents\z-code\text\xiyouji\bili_up\`

| 文件 | 作用 |
|---|---|
| `qr_login.py` | 扫码登录 → cookies.json（SESSDATA/bili_jct/…） |
| `bili_up.py` | preupload + upos 三步分片上传 + edit 提交底层 |
| `run_submit.py` | 分阶段编排：stage1/stage2/view/upload，uploads.json 断点缓存 |
| `pw_capture.py` | Playwright 抓稿件接口（通用版=playwright-toolkit 技能的 capture_xhr.py） |

## 流程四步（细节看 references/full-case-20261007.md）

1. **扫码登录**：`generate` 出二维码弹屏给用户扫 → `poll` 轮询 → Set-Cookie 头拿 SESSDATA/bili_jct
   （cookie 失效时重跑这步即可，别去偷浏览器的 cookie 库——v20 加密死路）
2. **抓稿件信息**：`GET x/vupre/web/archive/view?bvid=` 拿全量分 P filename+cid+稿件字段
   （该接口用 Playwright 注 cookie 开编辑页监听 response 抓出——手法见 **playwright-toolkit** 技能，它是本技能的工具子集）
3. **upos 上传**：preupload → 分片 PUT（记响应头 etag）→ complete；产出新 filename + biz_id(=新 cid)
4. **edit 提交**：`POST x/vu/web/edit`，一次带**全量 videos[]**：
   - 保留分 P：原 filename+原 cid 原样
   - **更换分 P：该位置换 新 filename+新 cid，title 不动**
   - 追加：尾部 append
   - 提交前断言顺序、提交后 view() 验证 cid 变化

## 硬规矩

- **先传后提交**：所有文件上传成功才 edit；分阶段（先小批验证再大批）
- **顺序=videos[] 数组序**，一锤定音；无关字段（标题/简介/标签）原样回传不碰
- 上传缓存 uploads.json 勿删（断点续传）；B 站转码异步，成功≠立即可播
- 坑：`python x.py stage2` 静默无输出=函数没挂 dispatch/heredoc 后台静默丢——改脚本用编辑工具+跑完 grep 输出确认

## 参考

- `references/full-case-20261007.md` —— 14P 终态全程实录（端点参数逐字+新增坑）
