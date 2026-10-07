# -*- coding: utf-8 -*-
"""SPA 接口考古通用工具：注入 cookie 开页面，抓全部匹配 XHR 的 URL+响应体。
用法:
  python capture_xhr.py --url "https://..." --cookies cookies.json \
      --domain .bilibili.com --match "x/|arcmass|upload" --wait 12 [--headful] [--out dir]
cookies.json = {"SESSDATA": "...", ...}（简单 {name: value}）
产出: <out>/pw_xhrs.json + <out>/pw_page.txt
"""
import argparse
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--cookies", required=True, help="cookies.json 路径")
    ap.add_argument("--domain", default=".bilibili.com")
    ap.add_argument("--match", default="/x/|api\\.", help="URL 过滤正则（空=全抓）")
    ap.add_argument("--wait", type=int, default=12)
    ap.add_argument("--headful", action="store_true")
    ap.add_argument("--out", default=".")
    a = ap.parse_args()

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    ck = json.loads(Path(a.cookies).read_text(encoding="utf-8"))
    cookies = [{"name": k, "value": v, "domain": a.domain, "path": "/"}
               for k, v in ck.items() if v]
    import re
    pat = re.compile(a.match) if a.match else None

    caps = []
    with sync_playwright() as p:
        b = p.chromium.launch(headless=not a.headful)
        ctx = b.new_context(user_agent=UA, viewport={"width": 1600, "height": 900})
        if cookies:
            ctx.add_cookies(cookies)
        page = ctx.new_page()

        def on_resp(resp):
            u = resp.url
            if pat and not pat.search(u):
                return
            if any(s in u for s in ("data.bilibili.com/log", "ExClimbWuzhi")):
                return  # 埋点/风控噪声
            try:
                body = resp.text()[:30000]
            except Exception:
                body = "<binary>"
            caps.append({"url": u, "status": resp.status, "body": body})
            print(resp.status, u[:110])
        page.on("response", on_resp)
        page.goto(a.url, wait_until="domcontentloaded", timeout=60000)
        time.sleep(a.wait)
        try:
            body_txt = page.inner_text("body")[:3000]
        except Exception:
            body_txt = "<no body>"
        (out / "pw_page.txt").write_text(
            f"TITLE: {page.title()}\n\n{body_txt}", encoding="utf-8")
        b.close()

    (out / "pw_xhrs.json").write_text(
        json.dumps(caps, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"captured {len(caps)} -> {out/'pw_xhrs.json'}")


if __name__ == "__main__":
    main()
