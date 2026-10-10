#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ghproxy - GitHub 镜像代理池：采集 -> 测速 -> 基线 -> 劣化自动重采集
纯标准库，零依赖。Python 3.8+（本机 3.15b4 可用）

v2 优化（DSA 向）：
  fetch 统一单次下载带回 body（采集源不再下载两遍）；TTFB=延迟、吞吐=纯传输段
  （排除 TLS 握手污染基线）；死节点闸门（小探针死则不烧大探针）；指数退避复测；
  池修剪（非种子连挂>=8 出池）；大探针样本 4MB->1.5MB；clone 扫描仅测本轮活跃；
  并发 10->16；baseline 支持延迟-only 节点；zip 失败回退 raw 大文件。

用法:
  python ghproxy.py collect            # 采集：种子 + scriptcat 脚本源码 + 聚合API -> 合并入池
  python ghproxy.py test               # 测速：小探针(TTFB延迟) + 大探针(吞吐) + clone 能力扫描
  python ghproxy.py rank               # 排名表（含 direct 直连参照）
  python ghproxy.py check              # 方法论核心：当前线路 vs 基线，劣化则 采集+测速+自动换线
  python ghproxy.py apply [NAME]       # 应用最优（默认）或指定代理：写 git insteadOf 全局加速
  python ghproxy.py off                # 撤销 insteadOf，恢复直连
  python ghproxy.py url <github-url>   # 把任意 github/raw/codeload/release URL 改写成当前最优线路
  python ghproxy.py clone <url> [...]  # 便捷克隆（自动改写 + 透传其余参数给 git）
  python ghproxy.py download <url> [-o 输出路径]
                                      # 多级自愈下载：候选按延迟从低到高，失效/速率不达标逐个切换；
                                      # 连续 5 个失效或 5 个不达标触发自愈(collect+test 重排序)；
                                      # >10MB 多路并行竞速，留最快淘汰其余，胜者中断带进度转顺序续传
"""
import concurrent.futures as cf
import json
import os
import random
import re
import shutil
import socket
import statistics
import subprocess
import sys
import threading
import time
import urllib.request
import urllib.error
import ssl
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(os.environ.get("GHPROXY_HOME", HERE), "state.json")  # 技能化后数据与脚本分离
UA = "ghproxy/2.0"

# ---------------------------------------------------------------- 探针目标
RAW_SMALL = "https://raw.githubusercontent.com/octocat/Hello-World/master/README"          # ~200B 延迟探针
BIG_ZIP = "https://github.com/BurntSushi/ripgrep/archive/refs/tags/13.0.0.zip"            # ~0.6MB 吞吐探针(codeload 无 Content-Length)
RAW_BIG = "https://raw.githubusercontent.com/torvalds/linux/master/MAINTAINERS"            # ~150KB raw 备用吞吐
CLONE_REPO = "https://github.com/octocat/Hello-World.git"                                 # clone 探针
SMALL_TIMEOUT = 10
BIG_TIMEOUT = 20
BIG_SAMPLE_BYTES = int(1.5 * 1024 * 1024)   # 吞吐样本只需 1.5MB，够稳
DEGRADE_MBPS_RATIO = 0.5      # 吞吐 < 基线 50% 判劣化
DEGRADE_LATENCY_X = 3.0       # 延迟 > 基线 3 倍 判劣化
HISTORY_CAP = 10
BACKOFF_AFTER = 3             # 连挂 N 次后进入指数退避复测
PRUNE_FAILS = 8               # 非种子连挂 N 次出池

# download 子命令
RACE_BIG_BYTES = 10 * 1024 * 1024   # 超过 10MB -> 多路并行竞速
RACE_PARALLEL = 5                   # 竞速并行流数
RACE_JUDGE_SEC = 8                  # 竞速裁决窗口（秒）：窗口内比窗口速率，留最快
RACE_READ_TIMEOUT = 20              # 单流 read 阻塞上限（秒）
RACE_IO_TIMEOUT = 6                 # 竞速流 socket 超时：短超时+重试，保证 cancel 秒级生效
SPEED_FLOOR_MBPS = 3.0              # 顺序模式绝对达标线（MB/s）
SPEED_FLOOR_RATIO = 0.3             # 相对达标线 = 池基线吞吐中位数 * 此比率，取两者较大
PROBE_WINDOW_BYTES = 1024 * 1024    # 顺序模式：本流下载满 1MB 时判速（更小文件能下即成功）
HEAL_FAILS = 5                      # 连续 N 个节点失效 / 不达标 -> 自愈
HEAL_MAX = 3                        # 单次下载自愈次数上限
# 限速检测（2026-10-09 晚实锤：探针小文件全绿、真实大流量全池挂死）
RAMPUP_SEC = 5                      # 首字节后 5 秒提速窗口
RAMPUP_MIN_BYTES = 512 * 1024      # 5 秒内至少下到 512KB（≈100KB/s），否则判"未提速"
ETA_CAP_FLOOR = 120                  # 体量预期判定保底预算（秒）；实际上限 = max(此值, 文件字节数/0.5MBps)
                                      # 即要求单节点至少 ~0.5MB/s，否则判"速率对文件体量预期不符"
THROTTLE_HITS = 3                   # 连续 N 个节点"未提速/预期不符" -> 池级限速，跳过自愈直奔特殊手段
SPECIAL_FLOOR_MBPS = 0.05           # 特殊手段通道达标线：慢但活即可（gitproxy 实测 ~53KB/s 仍可贵）

# ---------------------------------------------------------------- 内置种子池
# mode: prefix=前置改写(全能力) hostmap=克隆换域 rawhost=raw换域 jsdelivr=CDN仅raw
SEED = [
    # 一线常青（记忆 + 今日采集交叉验证）
    ("https://ghfast.top", "prefix"), ("https://gh-proxy.com", "prefix"),
    ("https://ghproxy.net", "prefix"), ("https://gh-proxy.net", "prefix"),
    ("https://github.moeyu.xyz", "prefix"), ("https://github.moeyy.xyz", "prefix"),
    ("https://ghproxy.cn", "prefix"), ("https://gh.llkk.cc", "prefix"),
    ("https://gh.api.99988866.xyz", "prefix"), ("https://hub.gitmirror.com", "prefix"),
    ("https://github.akams.cn", "prefix"), ("https://tvv.tw", "prefix"),
    # scriptcat #900 (Github增强-高速下载) 源码采集
    ("https://gh-proxy.org", "prefix"), ("https://cdn.gh-proxy.org", "prefix"),
    ("https://edgeone.gh-proxy.org", "prefix"), ("https://hk.gh-proxy.org", "prefix"),
    ("https://gh.con.sh", "prefix"), ("https://gh.ddlc.top", "prefix"),
    ("https://gh.h233.eu.org", "prefix"), ("https://gh.idayer.com", "prefix"),
    ("https://gh.jasonzeng.dev", "prefix"), ("https://gh.monlor.com", "prefix"),
    ("https://gh.xxooo.cf", "prefix"), ("https://gh.zwy.one", "prefix"),
    ("https://ghfile.geekertao.top", "prefix"), ("https://ghp.keleyaa.com", "prefix"),
    ("https://ghproxy.1888866.xyz", "prefix"), ("https://ghproxy.it", "prefix"),
    ("https://ghproxy.monkeyray.net", "prefix"), ("https://ghpxy.hwinzniej.top", "prefix"),
    ("https://git.yylx.win", "prefix"), ("https://github.boki.moe", "prefix"),
    ("https://gitdl.cn", "prefix"), ("https://wget.la", "prefix"),
    ("https://down.npee.cn", "prefix"), ("https://fastgit.cc", "prefix"),
    ("https://gh.catmak.name", "prefix"), ("https://gh.chjina.com", "prefix"),
    ("https://hub.glowp.xyz", "prefix"), ("https://proxy.yaoyaoling.net", "prefix"),
    ("https://rapidgit.jjda.de5.net", "prefix"), ("https://ghproxy.homeboyc.cn", "prefix"),
    # scriptcat #7814 (GitHub加速&增强助手) 内置池补充
    ("https://ghproxy.053000.xyz", "prefix"), ("https://github.ednovas.xyz", "prefix"),
    ("https://github.geekery.cn", "prefix"), ("https://gitproxy.mrhjx.cn", "prefix"),
    ("https://hub.ddayh.com", "prefix"), ("https://gitproxy.click", "prefix"),
    ("https://github-proxy.lixxing.top", "prefix"),
    # 特殊改写形态
    ("https://gitclone.com", "hostmap"),     # clone: https://gitclone.com/github.com/u/r.git
    ("https://kkgithub.com", "hostmap"),     # clone: https://kkgithub.com/u/r.git
    ("https://raw.bgithub.xyz", "rawhost"),  # raw:  https://raw.bgithub.xyz/u/r/main/f
    ("https://cdn.jsdelivr.net", "jsdelivr"),
    ("https://gcore.jsdelivr.net", "jsdelivr"),
    ("https://fastly.jsdelivr.net", "jsdelivr"),
    ("https://testingcf.jsdelivr.net", "jsdelivr"),
]

AGG_APIS = [  # 聚合 API（JSON，取 *.url 字段）
    "https://git.mxg.pub/api/github/list",
    "https://api.akams.cn/github",
]
SCRIPTCAT_PAGES = [  # 用户脚本源码页（正则挖 prefix 形态域名）
    "https://scriptcat.org/zh-CN/script-show-page/900/code",
    "https://scriptcat.org/zh-CN/script-show-page/7814/code",
]
DOMAIN_BLACKLIST = re.compile(
    r"(googlesyndication|googletagmanager|gtag|w3\.org|example\.com|scriptcat|tampermonkey"
    r"|github\.com|githubusercontent\.com|jsdelivr\.net/gh$|akams\.cn/donate|\.qq\.com|umami)")
RE_PREFIX_IN_CODE = re.compile(r'https://([a-z0-9.-]+\.[a-z]{2,})/https', re.I)
RE_RAWHOST_IN_CODE = re.compile(r'https://(raw\.[a-z0-9.-]+\.[a-z]{2,})[/"\']', re.I)
RE_VALID_BASE = re.compile(r"^https://[a-z0-9.-]+\.[a-z]{2,}$", re.I)

# ---------------------------------------------------------------- HTTP 核心
CTX = ssl.create_default_context()          # Windows 系统证书库（dev-sidecar 根证书在此）
CTX_INSECURE = ssl._create_unverified_context()


def fetch(url, timeout=SMALL_TIMEOUT, max_bytes=None, want_body=False, ctx=CTX):
    """单次 GET。返回 {status, ttfb, elapsed, bytes[, body]}。
    ttfb=首字节时刻（含 DNS/TCP/TLS，即真实延迟）；SSL 验证失败自动降级重试一次。"""
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Connection": "close"})
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            status = r.status
            n, buf, ttfb = 0, bytearray(), None
            limit = max_bytes or 65536
            while n < limit:
                chunk = r.read(min(65536, limit - n))
                if not chunk:
                    break
                if ttfb is None:
                    ttfb = time.time()
                n += len(chunk)
                if want_body:
                    buf += chunk
            if ttfb is None:
                ttfb = time.time()          # 空响应体：以连接结束计
            res = {"status": status, "ttfb": ttfb - t0, "elapsed": time.time() - t0, "bytes": n}
            if want_body:
                res["body"] = bytes(buf)
            return res
    except urllib.error.HTTPError as e:
        return {"status": e.code, "ttfb": None, "elapsed": time.time() - t0, "bytes": 0}
    except Exception:
        if ctx is CTX:                      # 证书劣质镜像：降级一次（只下公开文件，可接受）
            return fetch(url, timeout, max_bytes, want_body, CTX_INSECURE)
        return {"status": 0, "ttfb": None, "elapsed": time.time() - t0, "bytes": 0}


# ---------------------------------------------------------------- URL 改写
def rewrite(base, mode, github_url):
    """按代理模式改写 github URL；不适用返回 None"""
    if mode == "prefix":
        return f"{base.rstrip('/')}/{github_url}"
    if mode == "hostmap":
        m = re.match(r"https://github\.com/(.+)$", github_url)
        if "raw.githubusercontent.com" in github_url or "codeload" in github_url:
            return None
        return f"{base.rstrip('/')}/{m.group(1)}" if m else None
    if mode == "rawhost":
        m = re.match(r"https://raw\.githubusercontent\.com/(.+)$", github_url)
        return f"{base.rstrip('/')}/{m.group(1)}" if m else None
    if mode == "jsdelivr":
        m = re.match(r"https://raw\.githubusercontent\.com/([^/]+)/([^/]+)/([^/]+)/(.+)$", github_url)
        if not m:
            return None
        u, r, br, f = m.groups()
        br = "master" if br in ("HEAD",) else br
        return f"{base.rstrip('/')}/gh/{u}/{r}@{br}/{f}"
    return None


# ---------------------------------------------------------------- 状态
def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"proxies": {}, "direct": {"history": []}, "applied": None}


def save_state(st):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def baseline(entry):
    """理论速度 = 近 HISTORY_CAP 次成功样本中位数；无吞吐样本时退化为延迟基线"""
    h = entry.get("history", [])
    mb = [x["mbps"] for x in h if x.get("mbps")]
    lat = [x["latency_ms"] for x in h if x.get("latency_ms")]
    if not mb and not lat:
        return None
    return {"mbps": round(statistics.median(mb), 2) if mb else None,
            "latency_ms": int(statistics.median(lat)) if lat else None,
            "samples": len(h)}


# ---------------------------------------------------------------- 采集
def collect(st, verbose=True):
    found = {}  # url -> (mode, src)

    def add(u, mode, src):
        u = u.rstrip("/")
        if not RE_VALID_BASE.match(u):
            return
        if DOMAIN_BLACKLIST.search(u):
            return
        found[u] = (mode, src)

    for u, m in SEED:
        add(u, m, "seed")

    # 聚合 API（一次下载带回 body，直接解析）
    for api in AGG_APIS:
        r = fetch(api, timeout=10, max_bytes=1024 * 1024, want_body=True)
        if r["status"] != 200 or not r.get("body"):
            if verbose:
                print(f"  [api 失效] {api} -> HTTP {r['status']}")
            continue
        try:
            data = json.loads(r["body"].decode("utf-8", "replace"))
            items = data.get("data", data) if isinstance(data, dict) else data
            for it in items:
                u = (it or {}).get("url") if isinstance(it, dict) else None
                if u:
                    add(u, "prefix", "api:" + re.sub(r"^https?://", "", api).split("/")[0])
        except Exception as e:
            if verbose:
                print(f"  [api 解析失败] {api}: {e}")

    # scriptcat 脚本源码页：挖 prefix 形态域名（域名后紧跟 /https 才算）
    for page in SCRIPTCAT_PAGES:
        r = fetch(page, timeout=15, max_bytes=2 * 1024 * 1024, want_body=True)
        if r["status"] != 200:
            if verbose:
                print(f"  [scriptcat 失效] {page} -> HTTP {r['status']}")
            continue
        body = r["body"].decode("utf-8", "replace")
        for m in RE_PREFIX_IN_CODE.finditer(body):
            add("https://" + m.group(1), "prefix", "scriptcat")
        for m in RE_RAWHOST_IN_CODE.finditer(body):
            add("https://" + m.group(1), "rawhost", "scriptcat")

    # 修剪：非种子连挂 >= PRUNE_FAILS 出池（采集源会再供，池保持有界）
    pruned = [k for k, e in st["proxies"].items()
              if e.get("consec_fail", 0) >= PRUNE_FAILS and e.get("src") != "seed"]
    for k in pruned:
        del st["proxies"][k]

    merged = new = 0
    for u, (mode, src) in found.items():
        if u in st["proxies"]:
            st["proxies"][u]["mode"] = mode
            merged += 1
        else:
            st["proxies"][u] = {"url": u, "mode": mode, "src": src,
                                "first_seen": now(), "history": [], "consec_fail": 0}
            new += 1
    save_state(st)
    if verbose:
        print(f"采集完成：新增 {new}，已有 {merged}，修剪 {len(pruned)}，池内共 {len(st['proxies'])} 个节点")
    return new


# ---------------------------------------------------------------- 测速
def _rate(res):
    """纯传输段吞吐 MB/s（剔除 TTFB/握手）"""
    if res["status"] == 200 and res["bytes"] > 100 * 1024:
        dt = max(res["elapsed"] - res["ttfb"], 1e-3)
        return round(res["bytes"] * 8 / dt / 1e6, 2)
    return None


def probe_one(entry):
    """小探针(TTFB 延迟) -> 死则止；活则大探针(吞吐)，zip 失败回退 raw 大文件"""
    url, mode = entry["url"], entry["mode"]
    res = {"latency_ms": None, "mbps": None, "cap_raw": False, "cap_zip": False}

    if mode == "hostmap":  # 仅支持 clone 的换域镜像：git ls-remote 当探针
        ms = clone_check(url, mode)
        if ms:
            res["latency_ms"] = ms
            entry["clone_ok"] = ms
        return res

    s_url = rewrite(url, mode, RAW_SMALL)
    if not s_url:
        return res
    r = fetch(s_url, timeout=SMALL_TIMEOUT)
    if r["status"] != 200 or r["bytes"] == 0:
        return res                          # 死节点闸门：不再烧大探针
    res["latency_ms"] = int(r["ttfb"] * 1000)
    res["cap_raw"] = True

    for big in ((BIG_ZIP, RAW_BIG) if mode == "prefix" else (RAW_BIG,)):
        b_url = rewrite(url, mode, big)
        if not b_url:
            continue
        r2 = fetch(b_url, timeout=BIG_TIMEOUT, max_bytes=BIG_SAMPLE_BYTES)
        res["mbps"] = _rate(r2)
        if res["mbps"]:
            res["cap_zip"] = big is BIG_ZIP
            break
    return res


def probe_direct():
    """直连参照（与节点同口径：TTFB 延迟 + 纯传输吞吐）"""
    res = {"latency_ms": None, "mbps": None, "cap_raw": False, "cap_zip": False}
    r = fetch(RAW_SMALL, timeout=SMALL_TIMEOUT)
    if r["status"] == 200 and r["bytes"]:
        res["latency_ms"] = int(r["ttfb"] * 1000)
        res["cap_raw"] = True
        r2 = fetch(BIG_ZIP, timeout=BIG_TIMEOUT, max_bytes=BIG_SAMPLE_BYTES)
        res["mbps"] = _rate(r2)
        res["cap_zip"] = res["mbps"] is not None
    return res


def record(entry, res):
    entry["last_test"] = now()
    entry["latency_ms"] = res["latency_ms"]
    entry["mbps"] = res["mbps"]
    entry["cap_raw"] = res["cap_raw"]
    entry["cap_zip"] = res["cap_zip"]
    if res["latency_ms"] or res["mbps"]:
        entry["consec_fail"] = 0
        entry["last_ok"] = now()
        entry.setdefault("history", []).append(
            {"ts": entry["last_test"], "latency_ms": res["latency_ms"], "mbps": res["mbps"]})
        entry["history"] = entry["history"][-HISTORY_CAP:]
    else:
        entry["consec_fail"] = entry.get("consec_fail", 0) + 1
    entry["baseline"] = baseline(entry)


def _should_test(e):
    """指数退避：连挂 BACKOFF_AFTER 次起，每多挂一轮复测概率减半"""
    f = e.get("consec_fail", 0)
    if f < BACKOFF_AFTER:
        return True
    return random.random() <= 2.0 ** (BACKOFF_AFTER - 1 - f)


def test(st, quiet=False):
    t0 = time.time()
    items = [(k, e) for k, e in st["proxies"].items() if _should_test(e)]
    skipped = len(st["proxies"]) - len(items)
    if not quiet:
        extra = f"（退避跳过 {skipped} 个长期死节点）" if skipped else ""
        print(f"测速 {len(items)} 个节点{extra}（小探针 {SMALL_TIMEOUT}s / 大探针 {BIG_TIMEOUT}s）...")
    tested = set()
    with cf.ThreadPoolExecutor(max_workers=min(16, len(items) or 1)) as ex:
        futs = {ex.submit(probe_one, e): k for k, e in items}
        for fut in cf.as_completed(futs):
            k = futs[fut]
            tested.add(k)
            record(st["proxies"][k], fut.result())

    record(st.setdefault("direct", {"history": []}), probe_direct())

    # clone 能力扫描：仅本轮活跃的 prefix 节点（陈旧数据不重扫）
    cands = [k for k in tested
             if st["proxies"][k].get("mode") == "prefix"
             and (st["proxies"][k].get("latency_ms") or st["proxies"][k].get("mbps"))]
    if not quiet:
        print(f"clone 能力扫描 {len(cands)} 个活跃 prefix 节点...")
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(clone_check, st["proxies"][k]["url"], "prefix"): k for k in cands}
        for fut in cf.as_completed(futs):
            st["proxies"][futs[fut]]["clone_ok"] = fut.result()
    save_state(st)
    if not quiet:
        show_rank(st)
        print(f"本轮耗时 {time.time() - t0:.1f}s")


def clone_check(url, mode):
    target = rewrite(url, mode, CLONE_REPO)
    if not target:
        return None
    t0 = time.time()
    try:
        # -c http.proxy= 镜像直连不走 dev-sidecar；credential.helper= 清空凭据链：
        # 探针是公开仓库，镜像偶发 401 也不许触发任何认证弹窗/终端提问
        env = {**os.environ, "GCM_INTERACTIVE": "never", "GIT_TERMINAL_PROMPT": "0"}
        r = subprocess.run(["git", "-c", "http.proxy=", "-c", "http.sslVerify=false",
                            "-c", "credential.helper=",
                            "ls-remote", "--exit-code", target, "HEAD"],
                           capture_output=True, timeout=25, env=env)
        return int((time.time() - t0) * 1000) if r.returncode == 0 else None
    except Exception:
        return None


def score(e):
    """可用 > 全能力 > 快"""
    if not (e.get("latency_ms") or e.get("mbps")):
        return -1
    sc = 0.0
    sc += 1000 if e.get("clone_ok") else 0
    sc += 100 if e.get("cap_zip") else 0
    sc += 10 if e.get("cap_raw") else 0
    sc += (e.get("mbps") or 0)
    sc -= (e.get("latency_ms") or 9999) / 10000.0
    return round(sc, 2)


def ranked(st):
    rows = [(k, e) for k, e in st["proxies"].items() if e.get("latency_ms") or e.get("mbps")]
    rows.sort(key=lambda ke: score(ke[1]), reverse=True)
    return rows


def show_rank(st):
    d = st.get("direct", {})
    db = d.get("baseline") or {}
    print(f"\n{'排名':<4}{'节点':<38}{'延迟ms':>8}{'吞吐MB/s':>10}{'基线MB/s':>10}{'能力':>14}  来源")
    for i, (k, e) in enumerate(ranked(st)[:15], 1):
        b = e.get("baseline") or {}
        cap = "+".join(x for x, on in (("clone", e.get("clone_ok")), ("zip", e.get("cap_zip")), ("raw", e.get("cap_raw"))) if on)
        bl = b.get("mbps") if b else None
        mark = " <-- 当前" if st.get("applied") == k else ""
        print(f"{i:<4}{k:<38}{e.get('latency_ms') or '-':>8}{e.get('mbps') or '-':>10}"
              f"{bl if bl else '-':>10}{cap:>14}  {e.get('src','')}{mark}")
    print(f"直连参照: {'延迟 %sms  吞吐 %s MB/s  基线 %s' % (d.get('latency_ms'), d.get('mbps'), db.get('mbps')) if d.get('latency_ms') else '不可达'}")


# ---------------------------------------------------------------- 应用 / 撤销
def git_config(*args):
    return subprocess.run(["git", "config", "--global", *args], capture_output=True, text=True)


def apply_proxy(st, name=None):
    if name:
        e = st["proxies"].get(name)
        if not e:
            print(f"池中无此节点：{name}（先 collect/test）")
            return False
    else:
        rows = ranked(st)
        if not rows:
            print("池为空，先 collect && test")
            return False
        # 优先 clone 可用的 prefix 节点（clone 不可用的只能加速 raw/zip）
        cloneable = [(k, e) for k, e in rows if e.get("clone_ok") and e.get("mode") == "prefix"]
        name, e = cloneable[0] if cloneable else rows[0]
        # 直连健康且明显更快：直接切回直连
        d = st.get("direct", {})
        if d.get("mbps") and e.get("mbps") and d["mbps"] > e["mbps"] * 2 and d.get("latency_ms"):
            off(st, silent=True)
            print(f"直连吞吐 {d['mbps']} MB/s 远超最优代理 {e['mbps']} -> 已切回直连")
            return True
    if e["mode"] != "prefix":
        print(f"仅 prefix 模式可写 insteadOf（{name} 是 {e['mode']}），请用 clone/url 子命令手动改写")
        return False
    if not e.get("clone_ok") and name != st.get("applied"):
        e["clone_ok"] = clone_check(name, "prefix")
    if not e.get("clone_ok"):
        print(f"警告：{name} clone 协议不合规（仅能加速 raw/zip/codeload），git clone 将不可用")
    off(st, silent=True)
    p = name.rstrip("/") + "/"
    for gh_host in ("github.com", "raw.githubusercontent.com", "codeload.github.com"):
        git_config(f"url.{p}https://{gh_host}/.insteadOf", f"https://{gh_host}")
    git_config(f"http.{name}/.proxy", "")  # 镜像直连，绕过 dev-sidecar 等系统代理
    st["applied"] = name
    st["applied_at"] = now()
    save_state(st)
    ok = e.get("clone_ok")
    print(f"已应用 {name} -> insteadOf(github/raw/codeload) + 镜像直连；clone 验证: {'OK %sms' % ok if ok else '不可用'}")
    return True


def off(st, silent=False):
    out = subprocess.run(["git", "config", "--global", "--list"], capture_output=True, text=True).stdout
    n = 0
    for line in out.splitlines():
        low = line.lower()
        if any(t in low for t in (".insteadof=https://github.com",
                                  ".insteadof=https://raw.githubusercontent.com",
                                  ".insteadof=https://codeload.github.com")) or \
           (re.match(r"^http\.https://[^=]+\.proxy=$", low) and line.split("=", 1)[1] == ""):
            git_config("--unset", line.split("=")[0])
            n += 1
    st["applied"] = None
    save_state(st)
    if not silent:
        print(f"已移除 {n} 条全局 git 配置，恢复原状")


# ---------------------------------------------------------------- check：基线方法论
def check(st, report_only=False):
    print(f"== 基线体检 {now()} ==")
    need_collect = False

    # 1) 当前线路
    if st.get("applied"):
        e = st["proxies"].get(st["applied"]) or {}
        cur, label = probe_one(e), f"代理 {st['applied']}"
        base = e.get("baseline") or {}
    else:
        cur, label = probe_direct(), "直连"
        base = st.get("direct", {}).get("baseline") or {}

    if cur.get("latency_ms") is None and cur.get("mbps") is None:
        print(f"[{label}] 不可达！")
        need_collect = True
    elif not base:
        print(f"[{label}] 首次测速，建立基线：延迟 {cur.get('latency_ms')}ms 吞吐 {cur.get('mbps')} MB/s")
    else:
        ok_mbps = cur.get("mbps") is None or base.get("mbps") is None or \
            cur["mbps"] >= base["mbps"] * DEGRADE_MBPS_RATIO
        ok_lat = cur.get("latency_ms") is None or base.get("latency_ms") is None or \
            cur["latency_ms"] <= base["latency_ms"] * DEGRADE_LATENCY_X
        verdict = "符合预期" if (ok_mbps and ok_lat) else "劣化！"
        print(f"[{label}] 延迟 {cur.get('latency_ms')}ms / 基线 {base.get('latency_ms')}ms | "
              f"吞吐 {cur.get('mbps')} / 基线 {base.get('mbps')} MB/s -> {verdict}")
        need_collect = not (ok_mbps and ok_lat)

    # 2) 劣化 -> 采集 + 全量测速 + 重应用
    if need_collect and not report_only:
        print("\n触发自愈：重新采集 -> 全量测速 -> 换最优线路")
        collect(st)
        test(st, quiet=True)
        apply_proxy(st)
    elif need_collect:
        print("(report-only：建议运行 check 自愈或手动 collect && test && apply)")
    else:
        if st.get("applied"):
            record(st["proxies"][st["applied"]], cur)
        else:
            record(st.setdefault("direct", {"history": []}), cur)
        save_state(st)
    return need_collect


# ---------------------------------------------------------------- download：多级自愈下载
def speed_floor(st):
    """顺序模式达标线 MB/s = max(绝对下限, 池基线吞吐中位数 * 比率)"""
    mb = [e["baseline"]["mbps"] for e in st["proxies"].values()
          if (e.get("baseline") or {}).get("mbps")]
    rel = round(statistics.median(mb) * SPEED_FLOOR_RATIO, 1) if mb else 0
    return max(SPEED_FLOOR_MBPS, rel)


def download_candidates(st):
    """下载候选：prefix 模式活跃节点（release/raw 文件只有 prefix 能改写），
    延迟从低到高排序（同延迟吞吐高者优先）"""
    rows = [(k, e) for k, e in st["proxies"].items()
            if e.get("mode") == "prefix" and (e.get("latency_ms") or e.get("mbps"))]
    rows.sort(key=lambda ke: (ke[1].get("latency_ms") or 99999, -(ke[1].get("mbps") or 0)))
    return rows


def _open(url, timeout=30, headers=None, method="GET"):
    """urlopen；HTTP 错误码原样抛，连接类错误返回 None。
    仅证书校验失败才降级无校验连接（并打印提示）——download 落盘的是用户要执行的
    文件，其余错误（DNS/超时）静默换无校验重试会扩大中间人投毒面"""
    h = {"User-Agent": UA, "Connection": "close"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h, method=method)
    try:
        return urllib.request.urlopen(req, timeout=timeout, context=CTX)
    except urllib.error.HTTPError:
        raise
    except ssl.SSLCertVerificationError:
        print(f"  [SSL 降级] {url}：证书校验失败，改用无校验连接")
        try:
            return urllib.request.urlopen(req, timeout=timeout, context=CTX_INSECURE)
        except urllib.error.HTTPError:
            raise
        except Exception:
            return None
    except Exception:
        return None


def probe_size(cands, target):
    """探目标文件大小：HEAD 优先，失败退 GET 只读响应头；前 3 个候选内尝试，拿不到返回 None"""
    for k, e in cands[:3]:
        url = rewrite(e["url"], e["mode"], target)
        if not url:
            continue
        for kwargs in ({"method": "HEAD"}, {}):
            try:
                with _open(url, timeout=10, **kwargs) as r:
                    if r.status == 200:
                        cl = r.headers.get("Content-Length")
                        if cl and cl.isdigit():
                            return int(cl)
            except Exception:
                continue
    return None


def stream_to_file(url, path, floor_mbps, resume=0, expect=None):
    """顺序模式单节点流式下载（resume>0 时 Range 续传）。
    本流满 PROBE_WINDOW_BYTES 判速：低于达标线返回 slow（保留已写进度供下一节点续传）。
    expect=已知 Content-Length 时完成必须字节吻合，防镜像提前断流静默截断。
    返回 (state, mbps, total_bytes, err)，state: done / fail / slow"""
    n, ttfb = 0, None
    headers = {"Range": f"bytes={resume}-"} if resume else None
    try:
        r = _open(url, timeout=RACE_READ_TIMEOUT, headers=headers)
    except urllib.error.HTTPError as e:
        return "fail", None, resume, f"HTTP {e.code}"
    if r is None:
        return "fail", None, resume, "连接失败"
    try:
        if r.status not in (200, 206):
            return "fail", None, resume, f"HTTP {r.status}"
        append = resume and r.status == 206
        if resume and r.status == 200:      # 镜像不支持 Range：从头下
            resume = 0
        t_open = time.time()                # 响应打开即起表：提速窗口不含等首块的时间
        with r, open(path, "ab" if append else "wb") as f:
            while True:
                chunk = r.read(64 * 1024)   # 64KB 粒度：限速判定不必等满大块
                if not chunk:
                    break
                f.write(chunk)
                n += len(chunk)
                if ttfb is None:
                    ttfb = time.time()
                if n >= PROBE_WINDOW_BYTES:
                    mbs = round(n / (time.time() - t_open) / 1e6, 2)
                    if mbs < floor_mbps:
                        return "slow", mbs, resume + n, f"速率 {mbs} < 达标线 {floor_mbps} MB/s"
                else:
                    el0 = time.time() - t_open
                    if el0 >= RAMPUP_SEC and n < RAMPUP_MIN_BYTES:
                        return "slow", round(n / el0 / 1e6, 2), resume + n, \
                            f"{RAMPUP_SEC}s 未提速（{n // 1024}KB@{el0:.0f}s）"
                    if expect is not None and el0 > 2 and n >= 65536:
                        speed = n / el0
                        eta_cap = max(ETA_CAP_FLOOR, int(expect / 5e5))
                        if speed < floor_mbps * 1e6 and (expect - resume - n) / speed > eta_cap:
                            return "slow", round(speed / 1e6, 2), resume + n, (
                                f"速率对文件体量预期不符（{n // 1024}KB@{el0:.0f}s，"
                                f"预计超 {eta_cap}s 预算）")
        if n == 0 and not resume:
            return "fail", None, resume, "空响应"
        total = resume + n
        if expect is not None and total != expect:
            return "fail", None, total, f"大小不符 {total} != {expect}"
        mbs = round(n / max(time.time() - ttfb, 1e-3) / 1e6, 2) if ttfb else 0
        return "done", mbs, total, ""
    except Exception as e:
        return "fail", None, resume + n, str(e)[:80]


class Racer(threading.Thread):
    """竞速流：整文件下载到独占 part 文件，可被 cancel 淘汰"""
    def __init__(self, node, url, path, expect=None):
        super().__init__(daemon=True)
        self.node, self.url, self.path = node, url, path
        self.expect = expect
        self.cancel = threading.Event()
        self.done = 0
        self.ttfb = None
        self.state = "running"              # running / done / dead
        self.err = ""

    def run(self):
        try:
            r = _open(self.url, timeout=RACE_IO_TIMEOUT)
            if r is None:
                self.state, self.err = "dead", "连接失败"
                return
            with r, open(self.path, "wb") as f:
                if r.status != 200:
                    self.state, self.err = "dead", f"HTTP {r.status}"
                    return
                while True:
                    try:
                        chunk = r.read(256 * 1024)
                    except socket.timeout:        # 短超时轮询：cancel 后即时退出
                        if self.cancel.is_set():
                            self.state, self.err = "dead", "被淘汰"
                            return
                        continue
                    if not chunk:
                        if self.expect is not None and self.done != self.expect:
                            self.state, self.err = "dead", f"大小不符 {self.done} != {self.expect}"
                        else:
                            self.state = "done"
                        return
                    f.write(chunk)
                    self.done += len(chunk)
                    if self.ttfb is None:
                        self.ttfb = time.time()
                    if self.cancel.is_set():
                        self.state, self.err = "dead", "被淘汰"
                        return
        except Exception as e:
            self.state, self.err = "dead", str(e)[:80]


def _cleanup_race(part_dir):
    shutil.rmtree(part_dir, ignore_errors=True)


def race_download(st, cands, target, out, expect=None):
    """>10MB 多路竞速：RACE_JUDGE_SEC 秒后按窗口速率留最快、淘汰其余；胜者中断则带回
    最大磁盘进度转顺序续传。返回 (ok, offset)"""
    n = min(RACE_PARALLEL, len(cands))
    part_dir = out + ".race"
    os.makedirs(part_dir, exist_ok=True)
    racers = [Racer(k, rewrite(e["url"], e["mode"], target), os.path.join(part_dir, f"{i}.part"), expect)
              for i, (k, e) in enumerate(cands[:n])]
    print(f"竞速模式：{n} 路并行 [{' '.join(r.node for r in racers)}]，{RACE_JUDGE_SEC}s 后留最快淘汰其余")
    for r in racers:
        r.start()

    samples = {r.node: [] for r in racers}      # (t, done_bytes, state) 采样
    winner, t_end = None, time.time() + RACE_JUDGE_SEC
    while time.time() < t_end:
        time.sleep(0.5)
        t = time.time()
        for r in racers:
            samples[r.node].append((t, r.done, r.state))
        if any(r.state == "done" for r in racers):
            winner = max((r for r in racers if r.state == "done"), key=lambda r: r.done)
            break
        if all(r.state != "running" for r in racers):
            break

    def window_rate(r):
        s = [x for x in samples[r.node] if x[2] == "running"]
        if len(s) >= 2 and s[-1][0] > s[0][0]:
            return (s[-1][1] - s[0][1]) / (s[-1][0] - s[0][0]) / 1e6
        return -1

    if winner is None:
        alive = [r for r in racers if r.state == "running"]
        if alive:
            alive.sort(key=window_rate, reverse=True)
            winner = alive.pop(0)
            print("竞速裁决：" + "  ".join(
                f"{r.node} {max(window_rate(r), 0):.1f}MB/s" for r in [winner] + alive)
                + f" -> {winner.node} 胜出")
    # 出窗收尾：胜者以外仍在跑的流一律淘汰（含胜者提前完成的情况）
    for r in racers:
        if r is not winner and r.state == "running":
            r.cancel.set()
    if winner is None:
        print("竞速窗口内全部节点失联")

    # 等全部流退出：cancel 后 read 最长 RACE_IO_TIMEOUT 内让路
    for r in racers:
        r.join(timeout=RACE_IO_TIMEOUT + 2)

    best, best_off = None, 0
    for r in racers:
        if os.path.exists(r.path):
            sz = os.path.getsize(r.path)
            if sz > best_off:
                best, best_off = r.path, sz

    if winner is not None and winner.state == "done":
        os.replace(winner.path, out)
        _cleanup_race(part_dir)
        el = time.time() - winner.ttfb if winner.ttfb else 1
        print(f"下载完成 {out}（{winner.done / 1048576:.1f} MB via {winner.node}，"
              f"均速 {winner.done / el / 1e6:.1f} MB/s）")
        return True, 0
    if winner is not None:
        print(f"胜者 {winner.node} 中断（{winner.err}）")
    if best:
        shutil.copy(best, out + ".part")        # 顺序模式以最大进度续传
        with open(out + ".part.url", "w", encoding="utf-8") as f:
            f.write(target)
        print(f"保留进度 {best_off / 1048576:.1f} MB 转入顺序模式")
    _cleanup_race(part_dir)
    return False, best_off


def heal(st, reason):
    print(f"触发自愈（{reason}）：重新采集 -> 全量测速（约 1-2 分钟）...")
    collect(st, verbose=False)
    test(st, quiet=True)


def _resume_state(path, target):
    """断点续传状态：.part 与旁置 .url 元数据同时存在且 URL 匹配才续传，
    否则视为残留（上次别的下载/远端已更新）删掉重下。返回可续传字节数"""
    meta = path + ".url"
    if os.path.exists(path):
        try:
            if os.path.exists(meta) and open(meta, encoding="utf-8").read().strip() == target:
                return os.path.getsize(path)
        except OSError:
            pass
        os.remove(path)
    if os.path.exists(meta):
        os.remove(meta)
    with open(meta, "w", encoding="utf-8") as f:
        f.write(target)
    return 0


def _clear_meta(path):
    p = path + ".url"
    if os.path.exists(p):
        try:
            os.remove(p)
        except OSError:
            pass


def _clear_part(path):
    for p in (path, path + ".url"):
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass


def sequential_download(st, target, out, expect=None):
    """顺序模式：候选按延迟低->高逐节点尝试。失效 -> 下一个；正常但速率不达标 -> 下一个；
    连续 HEAL_FAILS 个失效 / 不达标触发自愈（collect+test 后重排序从头再试）。
    连续 THROTTLE_HITS 个节点 5 秒未提速/体量预期不符 -> 判池级大流量限速，
    跳过自愈（小文件探针会骗过 collect+test）返回 2，由调用方走特殊手段链。"""
    floor = speed_floor(st)
    print(f"顺序模式：达标线 {floor} MB/s（满 {PROBE_WINDOW_BYTES // 1048576}MB 或 {RAMPUP_SEC}s 未提速判速）")
    path = out + ".part"
    resume = _resume_state(path, target)
    fails = slows = heals = throttle_hits = 0
    while True:
        cands = download_candidates(st)
        if not cands:
            if heals >= HEAL_MAX:
                print("无可用节点且自愈额度耗尽")
                _clear_part(out + ".part")
                return 1
            heal(st, "候选为空")
            heals += 1
            continue
        broke = False
        for i, (k, e) in enumerate(cands, 1):
            url = rewrite(e["url"], e["mode"], target)
            if not url:
                continue
            resume = os.path.getsize(path) if os.path.exists(path) else 0
            tag = f"[{i}/{len(cands)}] {k}" + (f"（续传 @{resume / 1048576:.1f}MB）" if resume else "")
            state, mbs, total, err = stream_to_file(url, path, floor, resume, expect)
            if state == "done":
                os.replace(path, out)
                _clear_meta(path)
                print(f"{tag} 完成：{out} {total / 1048576:.1f} MB，均速 {mbs} MB/s")
                return 0
            if state == "slow":
                if "未提速" in err or "预期不符" in err:
                    throttle_hits += 1
                slows, fails = slows + 1, 0
                print(f"{tag} 速率不达标（{err}）-> 切下一个（连续不达标 {slows}/{HEAL_FAILS}，"
                      f"限速命中 {throttle_hits}/{THROTTLE_HITS}）")
                if throttle_hits >= THROTTLE_HITS:
                    print(f"连续 {THROTTLE_HITS} 个节点提速失败 -> 判定池级大流量限速"
                          f"（此状态下小文件探针全绿、自愈无意义，保留进度直奔特殊手段）")
                    return 2
                if slows >= HEAL_FAILS:
                    broke = True
                    break
            else:
                if err.startswith("大小不符"):
                    _clear_part(path)      # 镜像给了错误内容，已写前缀不可信，弃续传
                fails, slows = fails + 1, 0
                print(f"{tag} 失效（{err}）-> 下一个（连续失效 {fails}/{HEAL_FAILS}）")
                if fails >= HEAL_FAILS:
                    broke = True
                    break
        if not broke:
            print(f"全部 {len(cands)} 个候选尝试未成功")
        if heals >= HEAL_MAX:
            print(f"自愈额度（{HEAL_MAX} 次）耗尽，放弃")
            _clear_part(path)
            return 1
        heal(st, "连续 %d 个失效/不达标" % HEAL_FAILS if broke else "全池尝试未成功")
        heals += 1


def _sm_gh_api_archive(target, out, expect):
    """特殊手段 a：gh api tarball/zipball 直连——api.github.com 小报文通道独立于网页/git 通道，
    池级限速夜实测常绿。仅覆盖 archive 链接；release 资产走 b 兜底。"""
    m = re.match(r"^https://github\.com/([^/]+)/([^/?]+)/archive/refs/(heads|tags)/"
                 r"([^/#?]+)\.(zip|tar\.gz)$", target)
    if not m:
        return False, "非 archive 链接（gh api 通道不适用）"
    if not shutil.which("gh"):
        return False, "gh CLI 不可用"
    owner, repo, _kind, ref, ext = m.groups()
    kind = "zipball" if ext == "zip" else "tarball"
    tmp = out + ".sma"
    cap = 300 if expect is None else max(120, int(expect / (0.3 * 1e6)) + 60)
    try:
        with open(tmp, "wb") as f:
            subprocess.run(["gh", "api", f"repos/{owner}/{repo}/{kind}/{ref}"],
                           stdout=f, stderr=subprocess.DEVNULL, timeout=cap, check=True)
    except Exception as e:
        if os.path.exists(tmp):
            os.remove(tmp)
        return False, f"gh api 失败/超时（{str(e)[:48]}）"
    got = os.path.getsize(tmp)
    if expect is not None and got != expect:
        os.remove(tmp)
        return False, f"大小不符 {got} != {expect}"
    os.replace(tmp, out)
    return True, f"gh api 直连 {got / 1048576:.1f} MB"


def _sm_overwall(target, out, expect):
    """特殊手段 b：overwall 官方中继（dev-sidecar 公益 URL 嵌入式二层代理）。
    GET https://ow-prod.docmirror.top/X2dvX292ZXJfd2FsbF8/<真实URL> + dspassword 头。
    实测(2026-10-10)：raw 200@0.39s / google 204@0.65s；github.com 与 api 500 不吃。
    红线：第三方公共中继=不可信，仅匿名流量，勿带凭据。"""
    import urllib.request
    if not target.startswith("https://raw.githubusercontent.com/"):
        return False, "仅 raw 域适用"
    url = "https://ow-prod.docmirror.top/X2dvX292ZXJfd2FsbF8/" + target[len("https://"):]
    req = urllib.request.Request(url, headers={"dspassword": "dev_sidecar_is_666",
                                               "User-Agent": "Mozilla/5.0"})
    tmp = out + ".smc"
    try:
        with urllib.request.urlopen(req, timeout=90) as r, open(tmp, "wb") as f:
            while True:
                chunk = r.read(256 * 1024)
                if not chunk:
                    break
                f.write(chunk)
    except Exception as e:
        if os.path.exists(tmp):
            os.remove(tmp)
        return False, f"overwall 失败（{str(e)[:48]}）"
    got = os.path.getsize(tmp)
    if expect is not None and got != expect:
        os.remove(tmp)
        return False, f"大小不符 {got} != {expect}"
    os.replace(tmp, out)
    return True, f"overwall 中继 {got / 1048576:.1f} MB"


def _sm_gitproxy(target, out, expect):
    """特殊手段 c：api.gitproxy.dev 前缀直连——CF Workers 架构与池节点不同源，
    池限速夜实测 ~53KB/s 慢而稳，支持 Range 续传（沿用 .part 进度）。"""
    url = "https://api.gitproxy.dev/" + target[len("https://"):]
    path = out + ".part"
    resume = _resume_state(path, target)
    state, mbs, total, err = stream_to_file(url, path, SPECIAL_FLOOR_MBPS, resume, expect)
    if state == "done":
        os.replace(path, out)
        _clear_meta(path)
        return True, f"gitproxy {total / 1048576:.1f} MB 均 {mbs} MB/s"
    return False, f"gitproxy {state}（{err}）"


def special_means_download(target, out, expect=None):
    """特殊手段链：池级限速时的绕行通道，按实测可靠性排序。
    全部失败时提示人工调研（技能坑5/坑6：code-search/contents API 小报文取证）。"""
    print("== 特殊手段链：池级限速绕行 ==")
    for name, fn in (("gh api 直连（api.github.com 独立通道）", _sm_gh_api_archive),
                     ("overwall 官方中继（raw 专用，免节点亚秒级）", _sm_overwall),
                     ("api.gitproxy.dev（CF Workers 前缀，支持续传）", _sm_gitproxy)):
        print(f"[特殊手段] {name} ...")
        ok, msg = fn(target, out, expect)
        print(f"[特殊手段] {'✅ ' if ok else '❌ '}{msg}")
        if ok:
            return 0
    print("特殊手段全部失败 -> 人工介入：github-proxy 技能坑5/坑6"
          "（code-search/contents API 小报文取证可替代整包下载；或后台 -C - 慢爬）")
    return 1


def cmd_download(st, target, out=None):
    if not re.match(r"^https://(github\.com|raw\.githubusercontent\.com|codeload\.github\.com)/", target):
        print("仅支持 github.com / raw.githubusercontent.com / codeload 的 URL")
        return 1
    out = os.path.abspath(out or os.path.basename(target.split("?")[0]) or "ghproxy-download.bin")
    print(f"== 下载 {target}\n   -> {out}")
    cands = download_candidates(st)
    if not cands:
        heal(st, "池为空")
        cands = download_candidates(st)
        if not cands:
            print("无可用节点")
            return special_means_download(target, out)
    size = probe_size(cands, target)
    if size is None:
        print("文件大小：未知（直接顺序模式）")
    else:
        print(f"文件大小：{size / 1048576:.1f} MB（>10MB 走竞速）")
        if size == 0:                       # 空文件：0 是合法 Content-Length，直接落盘
            open(out, "wb").close()
            print(f"空文件，已落盘 {out}")
            return 0
        if size > RACE_BIG_BYTES:
            ok, _off = race_download(st, cands, target, out, size)
            if ok:
                return 0
    rc = sequential_download(st, target, out, size)
    if rc == 2:                             # 池级限速：跳自愈直接特殊手段
        rc = special_means_download(target, out, size)
    return rc


# ---------------------------------------------------------------- CLI
def cmd_url(st, target):
    if st.get("applied"):
        e = st["proxies"][st["applied"]]
    else:
        rows = ranked(st)
        if not rows:
            print("池为空，先 collect && test")
            return None
        e = rows[0][1]
    u = rewrite(e["url"], e["mode"], target)
    print(u or "（该 URL 当前最优线路不支持，先 test）")
    return u


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    st = load_state()

    if cmd == "collect":
        collect(st)
    elif cmd in ("test", "--full"):        # v2 起 clone 扫描已默认，--full 保留兼容
        if not st["proxies"]:
            collect(st, verbose=False)
        test(st)
    elif cmd in ("rank", "status"):
        show_rank(st)
    elif cmd == "check":
        check(st, report_only="--report-only" in sys.argv)
    elif cmd == "apply":
        apply_proxy(st, sys.argv[2] if len(sys.argv) > 2 else None)
    elif cmd == "off":
        off(st)
    elif cmd == "url":
        if len(sys.argv) < 3:
            print("用法: ghproxy.py url <github-url>")
        else:
            cmd_url(st, sys.argv[2])
    elif cmd == "download":
        args = [a for a in sys.argv[2:] if a != "-o"]
        out = None
        if "-o" in sys.argv[2:]:
            i = sys.argv.index("-o")
            out = sys.argv[i + 1] if i + 1 < len(sys.argv) else None
        if not args or args[0].startswith("-") or not out:
            print("用法: ghproxy.py download <github-url> -o <输出路径>")
        else:
            sys.exit(cmd_download(st, args[0], out))
    elif cmd == "clone":
        if len(sys.argv) < 3:
            print("用法: ghproxy.py clone https://github.com/u/r.git [dir] [git args...]")
            return
        target = sys.argv[2]
        rest = sys.argv[3:]
        u = cmd_url(st, target)
        os.execvp("git", ["git", "clone", u or target, *rest])
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
