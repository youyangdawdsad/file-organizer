# 📂 File Organizer v2.1

> 本地文件夹智能整理工具 — 零依赖，纯 Python 标准库。

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/Version-2.1.0-orange.svg)](https://github.com/youyangdawdsad/file-organizer/releases)

## ✨ 功能

- **6 种整理模式**：按类型 / 五大类 / 按日期 / 按扩展名 / 按大小 / 仅查重
- **重复文件检测**：SHA-256 内容哈希，先按大小分组再精确比对
- **一键复原**：每次操作自动记录日志，随时 `--undo` 恢复原状
- **空文件夹清理**：`--clean-empty-dirs` 扫描并删除空目录
- **Markdown 报告**：每次整理自动生成详细报告
- **安全优先**：不删除文件、不覆盖同名、自动跳过隐藏文件

## 🚀 快速开始

```bash
# 预览（不会移动文件）
python organize.py ~/Downloads --dry-run

# 按类型整理
python organize.py ~/Downloads

# 一键复原
python organize.py ~/Downloads --undo
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

## 🛠️ 完整选项

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

## 📖 使用示例

```bash
# 默认按类型归档下载目录
python organize.py ~/Downloads

# 按五大类归档
python organize.py ~/Downloads --mode big5

# 按日期归档，详细输出
python organize.py ~/Downloads --mode date -v

# 预览按大小归档
python organize.py ~/Downloads --mode size --dry-run

# 仅查看重复文件
python organize.py ~/Downloads --duplicates-only

# 一键复原
python organize.py ~/Downloads --undo

# 扫描空文件夹
python organize.py ~/Downloads --clean-empty-dirs

# 删除空文件夹
python organize.py ~/Downloads --clean-empty-dirs --execute

# 跳过某些目录
python organize.py ~/Downloads --skip-dirs .git node_modules
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
| **预览模式** | `--dry-run` 先看效果再决定 |

## 📦 安装

```bash
git clone https://github.com/youyangdawdsad/file-organizer.git
cd file-organizer
python scripts/organize.py ~/Downloads --dry-run
```

或直接下载 [ZIP](https://github.com/youyangdawdsad/file-organizer/releases/download/v2.1.0/file-organizer.zip)。

## 📋 依赖

- **Python 3.8+**
- **仅标准库**：os, shutil, hashlib, pathlib, json, datetime, argparse, io, sys, concurrent.futures
- **零第三方包**

## 📄 许可证

[MIT License](LICENSE)
