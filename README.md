# 📂 File Organizer v2.1

> 本地文件夹智能整理工具 — 零 API 依赖，纯 Python 标准库实现。

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/Version-2.1.0-orange.svg)](https://github.com/youyangdawdsad/file-organizer/releases)

## ✨ 功能特性

- **5 种整理模式**：按类型 / 按日期 / 按扩展名 / 按大小 / 仅查重
- **重复文件检测**：SHA-256 内容哈希，先按大小分组再精确比对
- **一键复原**：每次操作自动记录日志，随时 `--undo` 恢复原状
- **空文件夹清理**：`--clean-empty-dirs` 扫描并删除空目录
- **Markdown 报告**：每次整理自动生成详细报告
- **安全优先**：不删除文件、不覆盖同名、自动跳过隐藏文件

## 🚀 快速开始

```bash
# 预览模式（不会实际移动文件）
python organize.py ~/Downloads --dry-run

# 按类型整理（默认）
python organize.py ~/Downloads

# 一键复原
python organize.py ~/Downloads --undo
```

## 📋 整理模式

| 模式 | 命令 | 效果 |
|------|------|------|
| **按类型** | `--mode type`（默认） | 归档到 Documents / Images / Videos / Music / Archives / Code 等 |
| **按日期** | `--mode date` | 归档到 `2024-01/` `2024-03/` 等年月目录 |
| **按扩展名** | `--mode ext` | 归档到 `pdf/` `jpg/` `mp4/` 等扩展名目录 |
| **按大小** | `--mode size` | 归档到 `<1MB/` `1-10MB/` `10-100MB/` `100MB-1GB/` `>1GB` |
| **仅查重** | `--duplicates-only` | 只检测重复文件，不做归档 |

## 🛠️ 完整选项

```
organize.py <目标目录> [选项]

位置参数：
  target_dir              要整理的目录路径

选项：
  --mode {type,date,ext,size}  整理模式（默认: type）
  --dry-run               预览模式，不实际操作
  --duplicates-only       仅检测重复文件，不做归档
  --undo                  一键复原上次整理操作
  --report-only           仅生成报告，不做任何操作
  --clean-empty-dirs      扫描并清理空文件夹
  --execute               配合 --clean-empty-dirs 执行删除
  --skip-dirs DIR [DIR]   跳过指定子目录
  -v, --verbose           详细输出
  -h, --help              帮助
```

## 📖 使用示例

```bash
# 默认按类型归档下载目录
python organize.py ~/Downloads

# 按日期归档，详细输出
python organize.py ~/Downloads --mode date -v

# 先预览按大小归档的效果
python organize.py ~/Downloads --mode size --dry-run

# 仅查看重复文件
python organize.py ~/Downloads --duplicates-only

# 不满意？一键复原
python organize.py ~/Downloads --undo

# 扫描空文件夹
python organize.py ~/Downloads --clean-empty-dirs

# 删除空文件夹
python organize.py ~/Downloads --clean-empty-dirs --execute

# 跳过某些目录
python organize.py ~/Downloads --skip-dirs .git node_modules
```

## 🔍 重复文件检测

检测流程：

1. 按文件大小分组（大小不同 → 不可能重复，快速排除）
2. 同大小文件计算 SHA-256 哈希
3. 报告中标注"保留"和"可清理"
4. 0 字节空文件不参与检测

## 🛡️ 安全设计

| 保障 | 说明 |
|------|------|
| **不删除文件** | 只移动和重命名，永远不删 |
| **不覆盖同名** | 自动加 `_1`、`_2` 后缀 |
| **一键复原** | 操作日志记录每一步，随时可逆 |
| **跳过隐藏文件** | 默认跳过 `.` 开头的目录 |
| **跳过内部文件** | 跳过 `._file_organizer_*` 系列文件 |
| **预览模式** | `--dry-run` 先看效果再决定 |

## 📁 项目结构

```
file-organizer/
├── README.md              # 本文档
├── LICENSE                # MIT 许可证
├── SKILL.md               # MiClaw Skill 描述文件
└── scripts/
    └── organize.py        # 主程序（单文件，零依赖）
```

## 📦 安装

无需安装，直接运行：

```bash
# 下载
git clone https://github.com/youyangdawdsad/file-organizer.git
cd file-organizer

# 或下载 zip
# https://github.com/youyangdawdsad/file-organizer/releases

# 运行
python scripts/organize.py ~/Downloads --dry-run
```

## 📋 依赖

- **Python 3.8+**
- **仅标准库**：`os`, `shutil`, `hashlib`, `pathlib`, `json`, `datetime`, `argparse`, `io`, `sys`
- **零第三方包**

## 📄 许可证

[MIT License](LICENSE) — 自由使用、修改、分发。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

> Made with ❤️ by [youyangdawdsad](https://github.com/youyangdawdsad)
