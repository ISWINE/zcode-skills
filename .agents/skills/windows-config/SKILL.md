---
name: windows-config
description: Windows 系统配置项手册——已在本机验证的 Windows / Windows Terminal / 注册表 / 系统声音等修改方案，每项含原理、改法、验证、回滚。用户想 关提示音/去报错声、修改 Windows Terminal、调整 Windows 系统设置，或说「把这个加进 windows 配置/配置项」时使用——即使只是随口抱怨某个系统行为也应触发。
---

# windows-config：Windows 配置项手册

收集本机**已验证**的 Windows 配置修改项。一项一个文件放 `configs/`，本文件只放索引和规矩。

## 流程

1. 按用户需求查下方索引，命中 → 读对应 `configs/*.md` 照做。
2. 未命中 → 现场解决，解决后主动问用户是否收录；收录 = 新建 `configs/<主题>.md`（套下方模板）+ 更新本文件索引 + commit & push。
3. 动手前先看目标现状（文件当前内容 / 注册表当前值），改注册表或系统设置能备份就备份（导出 .reg 或记录原值）。
4. 改完必须验证，验证方法写在每个配置项文件里。
5. 动手前读 `references/lessons.md`（命令行坑与身份配置）。

## 配置项索引

| 配置项 | 文件 | 状态 |
|---|---|---|
| Windows Terminal 关闭命令行错误提示音 | configs/windows-terminal-bell.md | 已验证 2026-09-29 |

## 新增配置项模板

`configs/` 下每项按此结构，保持可复制、可回滚：

- `# <配置项名>`
- `## 需求 / 症状`：用户视角，什么场景、什么烦扰。
- `## 原理`：一句话讲清机制——谁触发、谁响应、改的是哪一层。
- `## 改法`：编号步骤，含确切文件路径 / 命令 / 配置片段；GUI 与命令行两种都给（有就给）。
- `## 验证`：改完做什么操作、预期看到/听到什么。
- `## 回滚 / 变体`：恢复原状的方法 + 常见替代值。
- 末尾一行状态：`已验证 <日期>，本机 <系统/程序版本>`。

## 仓库

本技能是 `ISWINE/zcode-skills`（私有）的子目录，随仓库统一 commit & push（见根 README「同步」）。本机部署：真身 `D:\projects\zcode-skills\.agents\skills\windows-config`，C: 侧 `~/.agents/skills/windows-config` 为 junction 联接。
