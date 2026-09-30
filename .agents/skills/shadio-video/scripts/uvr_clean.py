# -*- coding: utf-8 -*-
"""UVR 人声分离驱动（绕 CLI 网络坑：代理+免校验+hf-mirror）
用法: sdbgj/.venv/Scripts/python uvr_clean.py 文件1.wav 文件2.wav ...
输出: clean/ 下 *_vocals.wav
"""
import os
import sys
import warnings
from pathlib import Path

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["https_proxy"] = "http://127.0.0.1:31181"
os.environ["http_proxy"] = "http://127.0.0.1:31181"
_ff = Path(r"C:\Users\12696\Documents\z-code\text\xiyouji\sdbgj\tools\bin")
if _ff.is_dir():
    os.environ["PATH"] = str(_ff) + os.pathsep + os.environ["PATH"]

import requests
import urllib3

urllib3.disable_warnings()
_old = requests.Session.request
requests.Session.request = lambda self, *a, **k: _old(self, *a, **{**k, "verify": False})
warnings.filterwarnings("ignore")

from audio_separator.separator import Separator  # noqa: E402

REFS = Path("D:/tools/voicekit/refs")
sep = Separator(model_file_dir=str(REFS / "uvr_models"),
                output_dir=str(REFS / "clean"),
                output_format="WAV")
sep.load_model("UVR-MDX-NET-Voc_FT.onnx")
for f in sys.argv[1:]:
    outs = sep.separate(str(REFS / f))
    print(f, "->", outs)
