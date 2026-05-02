# 📂 File Organizer v2.1

> 本地文件夹智能整理工具 — 零依赖，纯 Python 标准库。

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/Version-2.1.0-orange.svg)](https://github.com/youyangdawdsad/file-organizer/releases)

## ✨ 功能

- **6 种整理模式**：按类型 / 五大类 / 按日期 / 按扩展名 / 按大小 / 仅查重
- **重复文件检测**：SHA-256 内容哈希，先按大小分组再精确比对
- **一键复原**：每次操作自动记录日志，随时撤销
- **空文件夹清理**：扫描并删除空目录
- **Markdown 报告**：每次整理自动生成详细报告
- **GUI + CLI 双模式**：双击即用 / 命令行批量
- **安全优先**：不删除文件、不覆盖同名、自动跳过隐藏文件

## 🚀 快速开始

### GUI 模式（推荐）

**双击 `organizer_gui.pyw` 即可运行**，无需打开终端。

![GUI Screenshot](https://img.shields.io/badge/界面-Dark_Theme-blueviolet?style=flat-square)

功能：
- 📁 一键选择目录
- 📦 5 种整理模式切换
- 🔍 预览模式（默认开启，不移动文件）
- 🔁 一键查重
- ↩ 一键复原
- 🧹 空文件夹清理
- 📋 实时日志输出

### CLI 模式

```bash
python scripts/organize.py ~/Downloads --dry-run    # 预览
python scripts/organize.py ~/Downloads              # 按类型整理
python scripts/organize.py ~/Downloads --undo       # 复原
```

## 📋 整理模式

| 模式 | 参数 | 效果 |
|------|------|------|
| **按类型** | `--mode type`（默认） | Documents / Images / Videos / Music / Archives / Code |
| **五大类** | `--mode big5` | 文档 / 图片 / 视频音频 / 压缩包 / 安装程序 |
| **按日期** | `--mode date` | `2026-01/` `2026-03/` 等年月目录 |
| **按扩展名** | `--mode ext` | `pdf/` `jpg/` `mp4/` 等 |
| **按大小** | `--mode size` | `<1MB/` `1-10MB/` `10-100MB/` `100MB-1GB/` `>1GB` |
| **仅查重** | `--duplicates-only` | 只检测重复，不移动 |

## 🛠️ CLI 完整选项

```
organize.py <目标目录> [选项]

--mode {type,big5,date,ext,size}  整理模式（默认: type）
--dry-run               预览，不实际移动
--duplicates-only       仅检测重复文件
--undo                  一键复原上次整理
--report-only           仅生成报告
--clean-empty-dirs      扫描空文件夹
--execute               配合 --clean-empty-dirs 执行删除
--skip-dirs DIR [DIR]   跳过指定子目录
-v, --verbose           详细输出
```

## 📁 项目结构

```
file-organizer/
├── README.md
├── LICENSE
├── SKILL.md                    # MiClaw Skill 描述
├── scripts/
│   └── organize.py             # CLI 版本
└── gui/
    └── organizer_gui.pyw       # GUI 版本（双击即用）
```

## 🔍 重复文件检测

1. 按文件大小分组（大小不同 → 不可能重复）
2. 同大小文件计算快速指纹（头尾 64KB + 大小）
3. 指纹相同 → SHA-256 精确比对
4. 报告中标注"保留"和"可清理"

## 🛡️ 安全设计

| 保障 | 说明 |
|------|------|
| **不删除文件** | 只移动和重命名 |
| **不覆盖同名** | 自动加 `_1`、`_2` 后缀 |
| **一键复原** | 操作日志记录每一步 |
| **跳过隐藏文件** | 默认跳过 `.` 开头的目录 |
| **预览模式** | 先看效果再决定 |

## 📦 安装

```bash
git clone https://github.com/youyangdawdsad/file-organizer.git
```

或下载 [ZIP](https://github.com/youyangdawdsad/file-organizer/releases/download/v2.1.0/file-organizer.zip)。

**GUI 使用**：解压后双击 `gui/organizer_gui.pyw`
**CLI 使用**：`python scripts/organize.py ~/Downloads --dry-run`

## 📋 依赖

- **Python 3.8+**
- **仅标准库**：os, shutil, hashlib, pathlib, json, datetime, argparse, io, sys, tkinter, threading, concurrent.futures
- **零第三方包**

## 📄 许可证

[MIT License](LICENSE)
