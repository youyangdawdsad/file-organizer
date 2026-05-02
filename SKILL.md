---
name: file-organizer
description: "文件夹整理：当用户提到整理文件夹、清理下载目录、文件归档、查找重复文件、文件夹太乱、复原上次整理、按类型/日期/扩展名/大小整理、下载目录太乱了需要收拾时，必须使用此 skill。"
version: 2.1.0
---

# File Organizer

零依赖文件夹整理工具。纯 Python 标准库，无需安装任何第三方包。

## 运行方式

```bash
python "<skill_dir>/scripts/organize.py" <目标目录> [选项]
```

`<skill_dir>` 替换为此 skill 的实际路径（从 runtimeRoot 获取）。

## 用户意图 → 命令映射

| 用户说的话 | 命令 |
|-----------|------|
| "整理一下下载文件夹" | `organize.py ~/Downloads` |
| "下载目录太乱了" | `organize.py ~/Downloads` |
| "按日期整理桌面" | `organize.py ~/Desktop --mode date` |
| "按五大类整理" | `organize.py ~/Downloads --mode big5` |
| "找找重复文件" | `organize.py ~/Downloads --duplicates-only` |
| "上次整理的不满意" | `organize.py ~/Downloads --undo` |
| "恢复一下" | `organize.py ~/Downloads --undo` |
| "先看看会怎么整理" | `organize.py ~/Downloads --dry-run` |
| "按扩展名整理" | `organize.py ~/Downloads --mode ext` |
| "按文件大小整理" | `organize.py ~/Downloads --mode size` |
| "清理空文件夹" | `organize.py ~/Downloads --clean-empty-dirs --execute` |

## 整理模式

| 模式 | 参数 | 效果 |
|------|------|------|
| 按类型 | `--mode type`（默认） | Documents / Images / Videos / Music / Archives / Code / Fonts / Installers |
| 五大类 | `--mode big5` | 文档 / 图片 / 视频音频 / 压缩包 / 安装程序 |
| 按日期 | `--mode date` | 2026-01/ 2026-03/ 等年月目录 |
| 按扩展名 | `--mode ext` | pdf/ jpg/ mp4/ 等 |
| 按大小 | `--mode size` | <1MB / 1-10MB / 10-100MB / 100MB-1GB / >1GB |
| 仅查重 | `--duplicates-only` | 只检测重复，不移动 |

## 完整参数

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

## 关键行为

1. **始终先预览**：用户首次请求整理时，先用 `--dry-run` 展示效果，确认后再实际执行
2. **重复检测**：每次整理前自动执行，按大小分组 → 快速指纹 → SHA-256 精确比对
3. **一键复原**：每次实际执行后自动记录日志，用户不满意随时 `--undo`
4. **安全底线**：不删除文件、不覆盖同名（自动加后缀）、跳过隐藏目录

## 依赖

- Python 3.8+
- 仅标准库（os, shutil, hashlib, pathlib, json, datetime, argparse, io, sys, concurrent.futures）
- 零第三方包
