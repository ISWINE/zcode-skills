# -*- coding: utf-8 -*-
"""gh_mirror —— GitHub 镜像测速调度器（用户规则：每次用之前测速，取最快调用）
镜像池含 2026-09 搜集的 ghproxy 类前缀 + jsdelivr(raw 专用) + 本地 dev-sidecar 代理直连。

CLI:
  python gh_mirror.py test                 # 测速排行（每次现测，不缓存）
  python gh_mirror.py fetch <URL> -o 本地   # 自动改写走最快镜像下载
库用法（重要）:
  from gh_mirror import patch_requests; patch_requests()   # 给 requests 打全局补丁：
  #   raw.githubusercontent.com / github.com release / objects.githubusercontent → 最快镜像
  #   首次触发时测速一次并缓存到进程内；verify=False 容忍代理 MITM
"""
import json
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

# 前缀型镜像（拼在完整 URL 前）；akams.cn 来自用户提供的 github.akams.cn（ghproxy-next 系）
PREFIX_MIRRORS = [
    "https://akams.cn/",
    "https://ghfast.top/",
    "https://gh-proxy.com/",
    "https://ghproxy.net/",
    "https://ghproxy.cc/",
    "https://mirror.ghproxy.com/",
]
# 直连候选：本地 dev-sidecar 代理（透明转发）与裸连（不走代理）
DIRECT = ["proxy_local", "direct"]
PROBE_URL = ("https://raw.githubusercontent.com/TRvlvr/application_data/main/"
             "filelists/download_checks.json")   # 用真实小文件测（UVR 需要的那个）
CURL = "curl.exe"


def _curl(args, timeout=12):
    return subprocess.run([CURL, *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


def speed_test(url=PROBE_URL, quiet=False):
    """对每个候选测速：拉同一文件，返回 [(秒, 名字, 改写URL)] 升序。"""
    cands = []
    for m in PREFIX_MIRRORS:
        cands.append((m, m + url))
    cands.append(("proxy_local", url))          # 由 dev-sidecar 兜底
    cands.append(("direct", url))
    results = []
    for name, u in cands:
        extra = ["-x", "http://127.0.0.1:31181"] if name == "proxy_local" else \
                (["--noproxy", "*"] if name == "direct" else [])
        try:
            t0 = time.time()
            r = _curl(["-sS", "--ssl-no-revoke", "-m", "12", "-o", "NUL",
                       "-w", "%{http_code} %{size_download}", *extra, u])
            dt = time.time() - t0
            code_size = (r.stdout or "0 0").split()
            if code_size and code_size[0] == "200" and int(code_size[1]) > 50:
                results.append((round(dt, 2), name, u))
            elif not quiet:
                results.append((99.0, name + "(bad)", u))
        except Exception:
            results.append((99.0, name + "(err)", u))
    results.sort()
    return results


def best(url=PROBE_URL):
    """每次现测，返回 (最快名, 改写URL, 耗时)。"""
    r = speed_test(url)
    return r[0][1], r[0][2], r[0][0]


def rewrite(url):
    """按最快镜像改写任意 github 系 URL。"""
    name, u, dt = best()
    if name in ("proxy_local", "direct"):
        return u
    return u if PROBE_URL not in u else u  # placeholder


MIRRORABLE = ("raw.githubusercontent.com", "github.com", "objects.githubusercontent.com",
              "codeload.github.com", "gist.githubusercontent.com")


def patch_requests():
    """requests 全局补丁：URL 改写到最快镜像 + verify=False。进程内只测速一次。"""
    import requests
    import urllib3
    urllib3.disable_warnings()
    state = {"map": None}

    def build_map():
        _, base, dt = best()
        rank = speed_test()
        top = [x for x in rank[:2] if x[0] < 90]      # 冠亚军
        m = {}
        for host in MIRRORABLE:
            for sec, name, u in top:
                if name in ("proxy_local", "direct"):
                    m[host] = ("direct", None)
                    break
                m[host] = ("prefix", name)
            else:
                continue
            break
        state["map"] = m
        print(f"[gh_mirror] fastest={top[0][1]} {top[0][0]}s -> map={m}")

    old = requests.Session.request

    def patched(self, method, url, **kw):
        if state["map"] is None:
            build_map()
        p = urllib.parse.urlparse(url)
        host = p.netloc
        if host in MIRRORABLE:
            mode, prefix = state["map"].get(host, ("prefix", PREFIX_MIRRORS[0]))
            if mode == "prefix":
                url = prefix + url
        kw.setdefault("verify", False)
        return old(self, method, url, **kw)

    requests.Session.request = patched


def fetch(url, out):
    name, u, dt = best(url)
    r = _curl(["-sS", "-L", "--ssl-no-revoke", "-m", "600", "-o", str(out),
               "-w", "%{http_code} %{size_download}B %{speed_download}B/s", u])
    print(f"[gh_mirror] {name} {dt:.2f}s -> {r.stdout}")
    return r.returncode == 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        print(f"探测文件: {PROBE_URL}\n")
        for sec, name, _ in speed_test():
            print(f"  {sec:6.2f}s  {name}")
        Path(__file__).with_name("gh_mirror_rank.json").write_text(
            json.dumps(speed_test(), ensure_ascii=False, indent=1), encoding="utf-8")
    elif len(sys.argv) > 2 and sys.argv[1] == "fetch":
        fetch(sys.argv[2], Path(sys.argv[3]))
