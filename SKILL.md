---
name: file-organizer
description: "文件夹整理：当用户提到整理文件夹、清理下载目录、文件归档、查找重复文件、文件夹太乱、复原上次整理、按类型/日期/扩展名/大小整理、下载目录太乱了需要收拾时，必须使用此 skill。"
version: 2.0.0
---

# File Organizer v2.0 — 一句话搞定文件夹整理

零 API 依赖，纯 Python 标准库。用户可自选文件夹、自选整理方式、一键复原。

## 快速开始

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
| "找找重复文件" | `organize.py ~/Downloads --duplicates-only` |
| "上次整理的不满意" | `organize.py ~/Downloads --undo` |
| "恢复一下" | `organize.py ~/Downloads --undo` |
| "先看看会怎么整理" | `organize.py ~/Downloads --dry-run` |
| "按扩展名整理" | `organize.py ~/Downloads --mode ext` |
| "按文件大小整理" | `organize.py ~/Downloads --mode size` |

## 四种整理模式

| 模式 | 命令 | 效果 |
|------|------|------|
| **按类型** | `--mode type`（默认） | 归档到 Documents/Images/Videos/Music/... |
| **按日期** | `--mode date` | 归档到 2024-01/ 2024-03/ 等年月目录 |
| **按扩展名** | `--mode ext` | 归档到 pdf/ jpg/ mp4/ 等扩展名目录 |
| **按大小** | `--mode size` | 归档到 <1MB/ 1-10MB/ 10-100MB/ 100MB-1GB/ >1GB |

## 一键复原

每次实际执行整理后，自动保存操作日志（`._file_organizer_log.json`）。随时可以一键复原：

```bash
python "<skill_dir>/scripts/organize.py" ~/Downloads --undo
```

复原操作：
- 逆序执行所有移动/重命名，把文件放回原位
- 删除整理时创建的空目录
- 清理日志文件
- 如果原位已有同名文件，自动加 `_undo_` 后缀避免覆盖

## 完整选项

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
  --skip-dirs DIR [DIR]   跳过指定子目录
  -v, --verbose           详细输出
  -h, --help              帮助
```

## 使用示例

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
```

## 重复文件检测

始终在归档前执行：
1. 按文件大小分组（大小不同 → 不可能重复，快速排除）
2. 同大小文件计算 SHA-256 哈希
3. 报告中标注"保留"和"可清理"
4. 0 字节空文件不参与检测

## 安全设计

- **不删除任何文件**：只移动和重命名
- **不覆盖同名文件**：自动加 `_1`、`_2` 后缀
- **一键复原**：操作日志记录每一步，随时可逆
- **不移动隐藏文件**：默认跳过 `.` 开头的目录
- **不移动内部文件**：跳过 `._file_organizer_*` 系列文件

## 依赖

- Python 3.8+
- 仅标准库：`os`, `shutil`, `hashlib`, `pathlib`, `json`, `datetime`, `argparse`
- 零第三方包
