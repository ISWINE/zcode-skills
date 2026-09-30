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
"""
import concurrent.futures as cf
import json
import os
import random
import re
import statistics
import subprocess
import sys
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
BIG_ZIP = "https://github.com/BurntSushi/ripgrep/archive/refs/tags/13.0.0.zip"            # ~2.2mb 吞吐探针
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
        # -c http.proxy= : 镜像必须直连，不走 dev-sidecar；部分镜像 Content-Type 不合规会被 git 拒绝，此处一并探出
        r = subprocess.run(["git", "-c", "http.proxy=", "-c", "http.sslVerify=false",
                            "ls-remote", "--exit-code", target, "HEAD"],
                           capture_output=True, timeout=25)
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
