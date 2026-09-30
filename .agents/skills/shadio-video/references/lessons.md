# 踩坑全记录

## ffmpeg 安装

npmmirror 二进制镜像是 Windows 最快路径（12MB/s vs gyan.dev 9KB/s）：

```bash
# 列出可用版本
curl -sS --ssl-no-revoke "https://registry.npmmirror.com/-/binary/ffmpeg-static/b6.1.1/"
# 下载（必须 -L 跟 302）
curl -sS -L --ssl-no-revoke -o ffmpeg.gz "https://registry.npmmirror.com/-/binary/ffmpeg-static/b6.1.1/ffmpeg-win32-x64.gz"
gzip -dc ffmpeg.gz > ffmpeg.exe
```

gyan essentials 构建含 libx264/aac/libass/DirectWrite 字体提供器。

## GPT-SoVITS 安装

1. 整合包 7.62GB：ModelScope `FlowerCry/gpt-sovits-7z-pacakges` → `GPT-SoVITS-v2pro-20250604.7z`
2. 解压后改 `GPT_SoVITS/configs/tts_infer.yaml`：`device: cpu`、`is_half: false`
3. 启动：`runtime\python.exe api_v2.py -a 127.0.0.1 -p 9880 -c GPT_SoVITS/configs/tts_infer.yaml`
4. 无 `-d cpu` 参数，CPU 由配置决定
5. API 调用：POST /tts，字段名是 `ref_audio_path`（非 ref_audio）

## GPT-SoVITS 克隆头号坑：EOS 早停

**症状**：生成 0.74 秒截断片段。

**根因**：BGM 污染参考音频 → GPT 语义生成第 11 步撞 EOS。片头曲段必炸，片中段较稳。

**解法**：
1. 参考段选片中（避开片头/片尾曲）
2. 先用 UVR 洗净参考（见下节）
3. 重试护栏：生成时长 < 字数/9 秒 → 自动重试 4 次
4. 偶发顽固截断：换 `text_split_method: cut5` + 微调 speed_factor

## UVR 人声分离

```bash
pip install audio-separator audioread
# 需要 ffmpeg 在 PATH
# 模型清单拉 raw.githubusercontent 被卡 → 驱动脚本走代理+verify=False+hf-mirror
python scripts/uvr_clean.py ref1.wav ref2.wav
```

模型 `UVR-MDX-NET-Voc_FT.onnx` 从 hf-mirror 下载。

## edge-tts 陷阱

| 陷阱 | 解法 |
|---|---|
| rate/pitch/volume 必须带显式符号 | `"+0%"` 不是 `"0%"`，否则 ValueError |
| 纯拟声词被拒 | "汪汪汪。" → NoAudioReceived，改用真音效 |
| 偶发 NoAudioReceived | 重试 3 次 + 0.3s 间隔 |
| 个别音色+负 pitch 被拒 | 降级梯子：参数减半 → 归零 |

## Python 3.15 beta 兼容

- 无 aiohttp wheel → edge-tts 装在 uv 3.12 venv
- 无 numpy → 依赖 numpy 的包全装在 3.12 侧

## novel_analyzer 踩坑

| 坑 | 解法 |
|---|---|
| 光杆「道」不在言说动词表 | SAY_VERV 加 `\|道` |
| 跨行引号（排版拆行） | 段落按引号配平合并 |
| 变身称谓归属 | 段落级变身注册表 + 同义扩展 |
| 描写性引导词 | DESC_JUNK 黑名单 + 主语回收正则 |
| 拟声词混入对白 | conf=onomatopoeia → perf:sfx: 指令 |
| 网文虚词污染 | AUTO_STOP + FUNC_CHARS + 介词剥离 |
| action beat 归属 | 引号后 14 字内人名匹配 |
| 代词回指 | 段内实体追踪 |

## 算法优化

人名匹配正则从循环内 O(n·m) 重建 → 模块级一次预编译 O(1) 查询（163 万字实测提速显著）。

## ffmpeg 滤镜链

| 坑 | 解法 |
|---|---|
| amix 多输入静默丢场景 | 极简拼接器 simple_mix.py 替代 |
| concat 相对路径找不到文件 | 列表必须绝对路径 |
| loudnorm 压平分声动态 | 分声集改用 volume+alimiter |
| fontsdir 盘符冒号被吞 | Windows libass 走 DirectWrite，不需要 fontsdir |

## Git Bash 特有

| 坑 | 解法 |
|---|---|
| `python x | tail` 吞退出码 | `set -o pipefail` |
| for 循环里 `cmd //c mklink` 转义失败 | 逐条写，不用循环 |
| `/tmp` 路径 Windows Python 不认 | 用项目内绝对路径 |
| heredoc 里正则替换 `\n` 变真换行 | 用 Edit 工具替代 |

## 音色资产库最佳实践

| 音色 | 适合角色 | 不适合 |
|---|---|---|
| Yunjian | 武将/旁白/老年（压嗓+DSP） | 主角（旁白腔） |
| Yunyang | 主角/利落青年 | — |
| Yunxi | 搞笑配角/吐槽役 | 主角（林黛玉感） |
| Xiaobei（东北） | 综艺旁白/唠叨角色 | 男性角色 |
| Xiaoxiao | 温柔女性/伪装态 | — |
| Yunxia | 童声/小妖/弹幕 | — |
