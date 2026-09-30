# ghproxy — GitHub 镜像代理池（采集 → 测速 → 基线 → 劣化自愈）v2

纯 Python 标准库（stdlib-only），零依赖，Python 3.8+ 直接跑。
正本：`D:\projects\zcode-skills\.agents\skills\github-proxy\scripts\ghproxy.py`
数据：`GHPROXY_HOME=D:\tools\ghproxy\state.json`

## 1. 心智模型（Architecture）

```
   [采集 collect]                [测速 test]                [应用 apply]
   种子池(61+)        探针: TTFB延迟(小raw)       git insteadOf 全局透明改写
   scriptcat 脚本源码  +   纯传输吞吐(1.5MB样本) →  github/raw/codeload 三主机
   聚合API×2               + clone能力(ls-remote)    + 镜像主机绕过系统代理
        │                        │
        └──────→ state.json ←──── ┘
                  每节点: history[≤10] → baseline(中位数) = 理论速度

   [check 体检] 当前线路实测 vs 基线
        吞吐 < 基线×0.5 或 延迟 > 基线×3 或不可达
        → 劣化 → 自动: collect + test + apply（换最优线）
```

核心思想：**基线（baseline）= 近 10 次成功测速的中位数**。首次测速即建立基线；
之后每次 `check` 实测当前线路，偏离基线过远就是"随机屏蔽/节点劣化"，自动重采集换线。

## 2. 命令

| 命令 | 作用 |
|---|---|
| `python ghproxy.py collect` | 采集新节点入池（不重复）+ 修剪长期死节点 |
| `python ghproxy.py test` | 全池测速：TTFB延迟+吞吐+clone 能力扫描 |
| `python ghproxy.py rank` | 排名表（含直连参照） |
| `python ghproxy.py check` | **体检+自愈**（建议日常只跑这个） |
| `python ghproxy.py apply [URL]` | 应用最优/指定节点（写 git insteadOf） |
| `python ghproxy.py off` | 撤销全部改写，恢复原状 |
| `python ghproxy.py url <gh-url>` | 任意 github/raw/release/codeload URL 改写输出 |
| `python ghproxy.py clone <url> [args]` | 便捷克隆（自动改写，余参透传 git） |

## 3. 应用后效果（apply）

git 全局多 4 条配置（off 全清）：
```
url.<镜像>/https://github.com/.insteadOf               = https://github.com
url.<镜像>/https://raw.githubusercontent.com/.insteadOf = https://raw.githubusercontent.com
url.<镜像>/https://codeload.github.com/.insteadOf       = https://codeload.github.com
http.<镜像>/.proxy = ""      # 镜像主机绕过 dev-sidecar 等系统代理，直连
```
之后 `git clone https://github.com/u/r.git` / fetch / pull 全部透明走镜像，
raw / archive zip 下载用 `ghproxy.py url <原URL>` 取改写地址。
直连吞吐 ≥ 最优代理 ×2 时 apply 自动切回直连。

## 4. 采集源（三层）

1. **种子池**：内置 60+ 常青节点（ghfast.top / gh-proxy.com / ghproxy.net / moeyy …）+ clone 专用（gitclone.com / kkgithub.com）+ raw 专用（bgithub.xyz / jsdelivr 系）
2. **scriptcat 用户脚本源码**：`script-show-page/900`（X.I.U 系"Github 增强-高速下载"）、`/7814`（"GitHub 加速&增强助手"，内置 32 源）——正则挖 `域名/https` 前置形态节点，源码更新即自动跟进
3. **聚合 API**：`git.mxg.pub/api/github/list`（实测可用，JSON）+ `api.akams.cn/github`（间歇 502，挂了自动跳过、恢复后自动采）

## 5. v2 优化（DSA 向，2026-09-30，实测全量测速 117.5s → 63.8s）

1. `fetch()` 统一：一次下载同时带回 body（采集源从下载两遍变一遍；修 API 响应截断隐患）
2. 延迟 = **TTFB**（含 DNS/TCP/TLS 的首字节时刻），不再混入响应体传输
3. 吞吐 = 纯传输段 `bytes/(elapsed−ttfb)`，剔除 TLS 握手污染基线
4. **死节点闸门**：小探针死则不烧大探针（19 个死节点每轮省数分钟墙钟，实测提速主源）
5. **指数退避**：连挂 ≥3 次起每多挂一轮复测概率减半——池越用越快
6. **池修剪**：非种子连挂 ≥8 出池（采集源会再供，池保持有界）
7. 大探针样本 4MB → 1.5MB（流量省 60%，方差不变）
8. clone 扫描仅测本轮活跃节点（陈旧数据不重扫）
9. 并发 10 → 16（瓶颈在 TLS 握手 IO 等待）
10. baseline 中位数支持延迟-only 节点（raw-only 不再永远"无基线"）
11. prefix 吞吐探针 zip 失败回退 raw 大文件（能力探测更完整）
12. apply 遇"直连更优"自动切回直连

明确不做的：n=61 排序不换堆（瓶颈外）；不加连接池（丢 urllib 重定向语义，镜像 302 常见，得不偿失）。

## 6. 本机已踩平的坑（2026-09-30 实测）

1. **dev-sidecar 冲突**：全局 `http.proxy=127.0.0.1:31180` 会把镜像 URL 里嵌的 github.com 也改写，git 协议请求被毁 → 解法=apply 时给镜像主机写 per-host 空代理直连
2. **Content-Type 不合规镜像**：如 git.yylx.win 返回合法 git 协议体但 `Content-Type: text/plain`，git 严格校验直接拒 → 这类节点标为仅 raw/zip 可用（clone 扫描自动探出），apply 只选 clone 可用节点
3. **github.akams.cn**（ghproxy-next/hubp.org）：首页能开、代理下载匿名不可用，留池内每次复测，恢复即入围
4. 直连 GitHub 当前整体不可达（DNS/连接层随机屏蔽），故 direct 参照常为"不可达"属正常
5. `curl.exe` 手动验证镜像时须带 `--ssl-no-revoke`（dev-sidecar 证书链 + schannel 吊销检查）
6. **git push 防弹窗铁律**：本机零 GitHub 凭据，裸 push 会弹 GCM 登录框。统一走：
   `GCM_INTERACTIVE=never GIT_TERMINAL_PROMPT=0 git -c credential.helper= -c "credential.helper=!f() { echo username=ISWINE; echo password=\$(gh auth token); }; f" push`
   （gh CLI 已登录 ISWINE，镜像透传 Authorization 头）

## 7. 排名打分（score）

`clone 可用(+1000) > zip 吞吐能力(+100) > raw(+10) > 吞吐 MB/s − 延迟/10000`
→ 优先保 clone 全能力，其次快。直连若吞吐 ≥ 最优代理×2 会拒绝套代理自动直连。

## 8. 建议

- 日常只跑 `check`（劣化自动换线，健康则刷历史样本）
- 可挂 Windows 任务计划（Task Scheduler）每日 `check` 一次
- 换网络环境（出差/换宽带）后手动 `check` 即可重建世界认知
