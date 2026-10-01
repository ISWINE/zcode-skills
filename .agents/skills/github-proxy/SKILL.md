---
name: github-proxy
description: GitHub 国内随机屏蔽的镜像代理池自愈工具。遇到 GitHub 打不开/clone 卡死/raw 超时/下载慢/push fail，或用户说"换个镜像/加速 github/又被墙了"时使用——先跑 check 自愈再继续任何 GitHub 操作。含采集(种子+scriptcat+聚合API)、双探针测速、基线劣化判定、git insteadOf 透明加速全流程。
---

# github-proxy：GitHub 镜像代理池（采集→测速→基线→劣化自愈）

## 何时用

- 任何 GitHub 操作失败/超时/龟速时（clone、fetch、push、raw、release、archive 下载）
- 用户抱怨"又被墙了 / 换个镜像 / github 抽风"
- 日常保健：每天跑一次 check

## 核心工作流（Workflow）

```bash
# 数据目录（基线池），首次创建
set GHPROXY_HOME=D:\tools\ghproxy   # 已初始化过则直接用

# 唯一需要记的命令：
python "%USERPROFILE%\.agents\skills\github-proxy\scripts\ghproxy.py" check
#   健康 -> 刷基线样本；劣化/不可达 -> 自动 采集+全量重测+换最优线
```

check 自愈后，git clone/pull/fetch 已透明走镜像（insteadOf），raw/zip 下载用：
```bash
python ...ghproxy.py url https://raw.githubusercontent.com/u/r/main/f   # 输出改写后 URL
python ...ghproxy.py clone https://github.com/u/r.git --depth 1        # 便捷克隆
```

**release/大文件下载直接用 download 子命令**（多级自愈，不要手写 curl）：
```bash
python ...ghproxy.py download https://github.com/u/r/releases/download/v1/x.exe -o D:\downloads\x.exe
```

## 子命令速查

| 命令 | 作用 |
|---|---|
| `check` | 体检+自愈（日常只跑这个） |
| `download <url> -o <路径>` | 多级自愈下载（详见下方下载策略） |
| `collect` / `test` / `rank` | 采集新节点 / 全池测速 / 排名表 |
| `apply [URL]` / `off` | 应用最优或指定节点 / 全部撤销恢复原状 |
| `url <gh-url>` / `clone <url>` | 改写任意 GitHub URL / 便捷克隆 |

## download 下载策略（2026-10-01 按用户规则实装）

- 候选节点 = prefix 模式活跃节点，**延迟从低到高**排序，每次下载从头开始
- 逐节点尝试：**失效 → 下一个；能下但速率不达标（<max(3MB/s, 池基线中位数×0.3)，本流满 1MB 判速）→ 也切下一个**，已下进度保留（Range 续传）
- **连续 5 个失效 / 连续 5 个不达标 → 自愈一次**（collect+test 后重排序从头再试），单次下载最多自愈 3 次
- **>10MB 文件 → 5 路并行竞速**：同时从延迟最低的 5 个节点开流，8s 窗口后按窗口速率留最快、淘汰其余；胜者中途断线则取磁盘上最大进度转顺序模式续传
- 已知 Content-Length 时完成必须字节吻合（防镜像断流静默截断）；实测 55MB exe 走竞速 ~12-19s（旧手写 curl 常挂/龟速）

## 方法论（为什么这样设计）

- **基线（baseline）= 近 10 次成功测速的中位数**（首测即建基线）
- 劣化判定：吞吐 < 基线×0.5 或 延迟 > 基线×3 或不可达 → 触发重采集+换线
- 三层采集源：内置种子 60+（含 clone 专用 gitclone.com/kkgithub.com、raw 专用 bgithub/jsdelivr）→ scriptcat 脚本源码页（id 900、7814，源码更新自动跟进）→ 聚合 API（git.mxg.pub 可用，api.akams.cn 间歇 502 自动跳过）
- 三种探针：小 raw 文件（延迟）、2.2MB zip（吞吐）、git ls-remote（clone 能力）
- 排名：clone 可用(+1000) > zip(+100) > raw(+10) > 吞吐；直连吞吐≥代理×2 时建议直连
- apply 写 4 条全局 git 配置：github/raw/codeload 三主机 insteadOf + 镜像主机 per-host 空代理（绕过 dev-sidecar）；off 全清

## 本机已知坑（详见 references/pitfalls.md）

1. dev-sidecar 全局 `http.proxy=127.0.0.1:31180` 会毁掉镜像内嵌 github.com 的 git 请求 → 已用 per-host 空代理解决，勿删
2. 部分镜像（如 git.yylx.win）git 协议响应体合法但 `Content-Type: text/plain`，git 严格校验拒绝 → 这类只配 raw/zip，clone 扫描自动识别
3. zcode-skills 仓库 remote 是硬编码 `https://gh-proxy.com/https://github.com//ISWINE/...`（带双斜杠）——若 push 失败先跑 check
## git 认证现状（2026-09-30 起，GCM 已出局）

- **GCM（弹登录框的元凶）已从凭据链移除**：系统级 `credential.helper manager` 已 unset，全局唯一 helper =
  `D:/Users/12696/AppData/Local/Programs/Python/Python315/python.exe D:/tools/ghproxy/cred_helper.py`
  （`git config --global credential.guiPrompt false` 另加一道保险）
- cred_helper.py：github.com + 当前应用镜像 + gh-proxy.com/ghfast.top/ghproxy.net 白名单 → 自动喂 gh CLI 的
  token（keyring，已登录 ISWINE）；其他域名静默放行走终端提问（永不弹 GUI）
- **因此裸 `git push` 即可静默认证**，无需任何配方；失败先跑 check 换线再推；仍失败=gh 过期，跑 `gh auth login`
- 应急备用配方（helper 失效时）：
  `GCM_INTERACTIVE=never GIT_TERMINAL_PROMPT=0 git -c credential.helper= -c "credential.helper=!f() { echo username=ISWINE; echo password=\$(gh auth token); }; f" push`
- 教训：git credential helper 里 python 必须写**绝对路径**（`python xxx.py` 在 git 的 exec 环境下不执行且无报错）；
  multivar 空值重置在 git 2.55 无效；GCM 留在链里会让 `git credential fill` 挂起
- 想找回 GUI 登录框：`git config --global --add credential.helper manager`

4. 手动 curl 验证镜像须带 `--ssl-no-revoke`（dev-sidecar 证书 + schannel 吊销检查）
