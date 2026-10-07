# B 站全代码投稿实录（2026-10-07，14P 终态实战）

**任务**：对已发布视频 BV1zha96YEEX 更换 P8/P9 视频文件 + 追加 P10-P14，全程代码，不碰 GUI 文件对话框。

**可运行代码**：`C:\Users\12696\Documents\z-code\text\xiyouji\bili_up\`
（qr_login.py / extract_cookies.py / bili_up.py / run_submit.py / pw_capture.py）

## 全链路四步

### ① 扫码登录拿 cookie（qr_login.py）
```
GET  passport.bilibili.com/x/passport-login/web/qrcode/generate   → {url, qrcode_key}
     url → qrcode.make() 出 PNG → cmd /c start 弹屏给用户扫
GET  passport.bilibili.com/x/passport-login/web/qrcode/poll?qrcode_key=...（2s 轮询）
     code 86101=未扫 86090=已扫未确认 0=成功
     成功时响应头 Set-Cookie 里拿 SESSDATA / bili_jct / DedeUserID / sid → cookies.json
```

### ② Playwright 抓稿件信息接口（本技能第 3 节的实战）
- 注入 cookie 开 `member.bilibili.com/platform/upload/video/frame?type=edit&bvid=...`
- 响应监听一发命中：**`GET member.bilibili.com/x/vupre/web/archive/view?topic_grey=1&bvid=<BV>&t=<ms>`**
  - `data.archive`：aid/tid/title/cover/tag/desc/copyright/desc_format_id/no_reprint…（编辑时**原样回传**，不动无关字段）
  - `data.videos[]`：每分 P 的 **filename（upos 服务端名）+ cid + title + desc** —— 编辑提交的命门
- 盲猜了 12 个端点全 404、编辑页静态 HTML/JS 挖不到 —— **别猜，让页面自己说**

### ③ upos 分片上传（bili_up.py upload_file）
```
GET  member.bilibili.com/preupload?name=&r=upos&profile=ugcfx/bup&size=&upcdn=bda2
     → auth / biz_id / chunk_size / endpoint / upos_uri
POST https:<endpoint>/<upos_uri 去掉 upos://>?uploads=&output=json&profile=ugcfx/bup
     &filesize=&partsize=&biz_id=          (header X-Upos-Auth: <auth>)
     → upload_id
PUT  同 URL ?partNumber=<i,1起>&uploadId=&chunk=<i,0起>&chunks=&size=&start=&end=&total=
     body=分片(默认10MB)  响应头 etag 记下 → parts[]
POST 同 URL ?output=json&name=<原文件名>&profile=ugcfx%2Fbup&uploadId=&biz_id=
     body={"parts":[{partNumber,eTag}...]}   → OK:1
返回 filename = upos_uri 尾段去后缀；新分 P 的 cid = biz_id
```

### ④ 编辑提交（x/vu/web/edit）
```
POST member.bilibili.com/x/vu/web/edit?t=<ms>&csrf=<bili_jct>
JSON: {aid, videos[14], cover, copyright, tid, tag, desc_format_id, desc,
       recreate:-1, dynamic, interactive:0, no_disturbance, no_reprint,
       subtitle{open:0,lan:""}, web_os:1, csrf, new_web_edit:1}
```
**videos[] 全量规则（顺序=分 P 顺序，一锤定音）**：
- 保留的分 P：原 filename + 原 cid + 原 title/desc 原样
- **更换的分 P：该位置放 新 filename + 新 cid（biz_id），title/desc 不变**
- 追加的分 P：数组尾部 append {新 filename, 新 cid, title, desc:""}
- 提交前断言前 N 个 title 与线上一致；提交后重新 view() 验证 cid 变化符合预期

**分阶段策略**：先"换 P8/P9 + 追加 P10"一次 edit → 验证 → 再"追加 P11-P14"一次 edit。
上传结果缓存在 uploads.json（filename+biz_id），断点续传不重传。

## 本战新增坑（SKILL.md 坑册之外）

- `python run.py stage2` 静默无输出=追加的函数没挂进 `__main__` dispatch + heredoc 在后台 Bash 里根本没写进文件（双重静默）——**改脚本用编辑工具，跑完 grep 输出确认真执行**
- edit 响应 `code:0 message:OK` 即成功；`-400` 通常是 payload 缺必填字段（对照 view() 返回的字段补）
- 换分 P 后 cid 会更新为新 biz_id（P8/P9 实测），验证时以 cid 变化确认替换生效
- B 站转码异步，提交成功≠立即可播，等几分钟再看
