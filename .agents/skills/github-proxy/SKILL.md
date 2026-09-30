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

## 子命令速查

| 命令 | 作用 |
|---|---|
| `check` | 体检+自愈（日常只跑这个） |
| `collect` / `test` / `rank` | 采集新节点 / 全池测速 / 排名表 |
| `apply [URL]` / `off` | 应用最优或指定节点 / 全部撤销恢复原状 |
| `url <gh-url>` / `clone <url>` | 改写任意 GitHub URL / 便捷克隆 |

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
4. 手动 curl 验证镜像须带 `--ssl-no-revoke`（dev-sidecar 证书 + schannel 吊销检查）
