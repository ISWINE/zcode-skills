#!/usr/bin/env python3
"""nvimg - NVIDIA build.nvidia.com free image generation (flux.1-dev).

Usage:
  python nvimg.py "prompt text" [-o out.jpg]

Key resolution order:
  1. env NVIDIA_API_KEY
  2. ZCode provider_config.json (providerName=nvidia -> access.apiKey)

Output: JPEG file (flux returns artifacts[0].base64 as JPEG).
"""
import argparse
import base64
import json
import os
import sys
import time
import urllib.request

ENDPOINT = "https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.1-dev"
PROVIDER_CFG = os.path.expandvars(r"%USERPROFILE%\.zcode\v2\provider_config.json")


def find_key():
    k = os.environ.get("NVIDIA_API_KEY")
    if k:
        return k.strip()
    try:
        with open(PROVIDER_CFG, encoding="utf-8") as f:
            cfg = json.load(f)
        for r in cfg["config"]["providerConfigRules"]["providerRules"]:
            if r.get("providerName") == "nvidia":
                return r["config"]["access"]["apiKey"]
    except Exception:
        pass
    sys.exit("ERROR: no API key found (set NVIDIA_API_KEY or add nvidia provider to "
             + PROVIDER_CFG)


def main():
    ap = argparse.ArgumentParser(description="NVIDIA flux.1-dev image generation")
    ap.add_argument("prompt", help="image prompt, English recommended")
    ap.add_argument("-o", "--out", default=None, help="output jpg path")
    args = ap.parse_args()

    out = args.out or time.strftime("nvidia_flux_%Y%m%d_%H%M%S.jpg")
    body = json.dumps({"prompt": args.prompt}).encode("utf-8")
    req = urllib.request.Request(ENDPOINT, data=body, headers={
        "Authorization": "Bearer " + find_key(),
        "Content-Type": "application/json",
        "Accept": "application/json",
    })
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=180) as r:
        data = json.load(r)
    raw = base64.b64decode(data["artifacts"][0]["base64"])
    with open(out, "wb") as f:
        f.write(raw)
    print("OK %s (%d bytes, %.1fs) magic=%s" % (out, len(raw), time.time() - t0, raw[:3].hex()))


if __name__ == "__main__":
    main()
