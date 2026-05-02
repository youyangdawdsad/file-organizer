#!/usr/bin/env python3
"""
File Organizer v2.2 — 本地文件夹智能整理工具
零 API 依赖，纯 Python 标准库实现。

核心功能：
  1. 多种整理模式：按类型 / 按日期 / 按扩展名 / 仅查重
  2. 重复文件检测（SHA-256 内容哈希）
  3. 操作日志记录 → 一键复原
  4. Markdown 整理报告
  5. 空文件夹扫描与清理
"""

import os
import sys
import io
import json
import shutil
import hashlib
import argparse
import datetime
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── 版本 ──────────────────────────────────────────────────
__version__ = "2.2.0"

# ── 分类规则 ──────────────────────────────────────────────
CATEGORY_MAP = {
    "Documents": {
        ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt",
        ".txt", ".csv", ".md", ".rtf", ".odt", ".ods", ".odp",
        ".epub", ".mobi", ".pages", ".numbers", ".key",
    },
    "Images": {
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp",
        ".ico", ".tiff", ".tif", ".heic", ".heif", ".raw", ".cr2",
        ".nef", ".arw", ".dng", ".psd", ".ai", ".eps",
    },
    "Videos": {
        ".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm",
        ".m4v", ".3gp", ".ts", ".vob", ".ogv",
    },
    "Music": {
        ".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a",
        ".opus", ".aiff", ".ape",
    },
    "Archives": {
        ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz",
        ".tgz", ".tar.gz", ".zst",
    },
    "Code": {
        ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css",
        ".java", ".c", ".cpp", ".h", ".hpp", ".go", ".rs", ".rb",
        ".php", ".swift", ".kt", ".scala", ".r", ".m", ".mm",
        ".sh", ".bat", ".ps1", ".cmd", ".zsh", ".fish",
        ".json", ".yaml", ".yml", ".toml", ".xml", ".ini", ".cfg",
        ".sql", ".graphql", ".proto",
    },
    "Fonts": {
        ".ttf", ".otf", ".woff", ".woff2", ".eot",
    },
    "Installers": {
        ".exe", ".msi", ".dmg", ".pkg", ".deb", ".rpm", ".apk",
        ".appimage", ".snap", ".flatpak",
    },
}

EXT_TO_CATEGORY = {}
for _cat, _exts in CATEGORY_MAP.items():
    for _ext in _exts:
        EXT_TO_CATEGORY[_ext] = _cat

# ── 五大类映射（合并细分类） ──────────────────────────────
BIG5_MAP = {
    "文档": {
        ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt",
        ".txt", ".csv", ".md", ".rtf", ".odt", ".ods", ".odp",
        ".epub", ".mobi", ".pages", ".numbers", ".key",
        ".dwg", ".dxf",
    },
    "图片": {
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp",
        ".ico", ".tiff", ".tif", ".heic", ".heif", ".raw", ".cr2",
        ".nef", ".arw", ".dng", ".psd", ".ai", ".eps",
    },
    "视频音频": {
        ".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm",
        ".m4v", ".3gp", ".ts", ".vob", ".ogv",
        ".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a",
        ".opus", ".aiff", ".ape",
    },
    "压缩包": {
        ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz",
        ".tgz", ".tar.gz", ".zst",
    },
    "安装程序": {
        ".exe", ".msi", ".dmg", ".pkg", ".deb", ".rpm", ".apk",
        ".appimage", ".snap", ".flatpak",
    },
}

EXT_TO_BIG5 = {}
for _cat, _exts in BIG5_MAP.items():
    for _ext in _exts:
        EXT_TO_BIG5[_ext] = _cat

# ── 内部文件标记 ──────────────────────────────────────────
HIDDEN_DIR = ".file-organizer"
REPORT_FILENAME = "report.md"
LOG_FILENAME = "log.json"


# ══════════════════════════════════════════════════════════
#  工具函数
# ══════════════════════════════════════════════════════════

def setup_encoding():
    """Windows 终端 UTF-8 兼容。"""
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer, encoding="utf-8", errors="replace"
            )
            sys.stderr = io.TextIOWrapper(
                sys.stderr.buffer, encoding="utf-8", errors="replace"
            )


def format_size(size_bytes: int) -> str:
    """字节数 → 人类可读大小。"""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def get_category(ext: str) -> str | None:
    return EXT_TO_CATEGORY.get(ext.lower())


def is_internal(name: str) -> bool:
    """判断是否为自身生成的内部文件或目录。"""
    return name.startswith("._file_organizer_") or name == HIDDEN_DIR


def _is_empty_recursive(path: Path) -> bool:
    """递归检查目录是否为空（或只包含空子目录）。"""
    if not path.is_dir():
        return False
    for item in path.iterdir():
        if item.is_file():
            return False
        if item.is_dir() and not _is_empty_recursive(item):
            return False
    return True


def _remove_empty_recursive(path: Path):
    """递归删除空目录（从最深的开始）。"""
    if not path.is_dir():
        return
    for item in list(path.iterdir()):
        if item.is_dir():
            _remove_empty_recursive(item)
    try:
        if not any(path.iterdir()):
            path.rmdir()
    except OSError:
        pass


def _find_empty_dirs_recursive(root: Path) -> list[Path]:
    """递归查找所有空文件夹（或只包含空子文件夹的目录）。"""
    empty_dirs = []
    if not root.is_dir():
        return empty_dirs
    for item in root.iterdir():
        if item.is_dir() and not item.name.startswith("."):
            if _is_empty_recursive(item):
                empty_dirs.append(item)
            else:
                empty_dirs.extend(_find_empty_dirs_recursive(item))
    return empty_dirs


def scan_directory(target: Path, skip_dirs: set[str]) -> list[Path]:
    """扫描目录，返回所有普通文件（排除隐藏目录和内部文件）。"""
    files = []
    for item in target.iterdir():
        if item.name.startswith(".") and item.is_dir():
            continue
        if item.name in skip_dirs:
            continue
        if is_internal(item.name):
            continue
        if item.is_file():
            files.append(item)
    return files


def _same_partition(p1: Path, p2: Path) -> bool:
    """判断两个路径是否在同一磁盘分区。"""
    try:
        return p1.resolve().drive.lower() == p2.resolve().drive.lower()
    except AttributeError:
        return True


def safe_move(src: Path, dst_dir: Path) -> Path:
    """安全移动文件。同分区用 os.rename，跨分区用 shutil.copy2+delete。"""
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / src.name
    if dst.exists() and dst.resolve() != src.resolve():
        stem, suffix = src.stem, src.suffix
        counter = 1
        while dst.exists():
            dst = dst_dir / f"{stem}_{counter}{suffix}"
            counter += 1
    if src.resolve() == dst.resolve():
        return dst
    if _same_partition(src, dst_dir):
        os.rename(str(src), str(dst))
    else:
        shutil.copy2(str(src), str(dst))
        src.unlink()
    return dst


# ══════════════════════════════════════════════════════════
#  重复文件检测
# ══════════════════════════════════════════════════════════

def _quick_hash(path: Path) -> str:
    """快速指纹：文件头 64KB + 文件尾 64KB + 文件大小。"""
    size = path.stat().st_size
    h = hashlib.md5(str(size).encode())
    with open(path, "rb") as f:
        head = f.read(65536)
        h.update(head)
        if size > 65536:
            f.seek(-65536, 2)
            tail = f.read(65536)
            h.update(tail)
    return h.hexdigest()


def _full_hash(path: Path) -> str:
    """完整 SHA-256 哈希。"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(131072)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def find_duplicates(files: list[Path], verbose: bool = False) -> list[list[Path]]:
    """两阶段查重：按大小分组 → quick_hash → full_hash，全程并行。"""
    size_groups: dict[int, list[Path]] = defaultdict(list)
    for f in files:
        try:
            size = f.stat().st_size
            if size == 0:
                continue
            size_groups[size].append(f)
        except (OSError, PermissionError):
            continue

    candidates: list[list[Path]] = [g for g in size_groups.values() if len(g) >= 2]
    if not candidates:
        return []

    to_quick_hash: list[Path] = []
    for g in candidates:
        to_quick_hash.extend(g)

    if verbose:
        print(f"   阶段1：并行快速指纹 {len(to_quick_hash)} 个文件...")

    quick_results: dict[Path, str] = {}
    max_workers = min(16, len(to_quick_hash))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {executor.submit(_quick_hash, f): f for f in to_quick_hash}
        for future in as_completed(future_map):
            f = future_map[future]
            try:
                quick_results[f] = future.result()
            except (OSError, PermissionError):
                continue

    quick_groups: dict[str, list[Path]] = defaultdict(list)
    for f, qh in quick_results.items():
        quick_groups[qh].append(f)

    to_full_hash: list[Path] = []
    for qh, group in quick_groups.items():
        if len(group) >= 2:
            to_full_hash.extend(group)

    if not to_full_hash:
        return []

    if verbose:
        print(f"   阶段2：精确哈希确认 {len(to_full_hash)} 个候选文件...")

    full_results: dict[Path, str] = {}
    max_workers = min(8, len(to_full_hash))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {executor.submit(_full_hash, f): f for f in to_full_hash}
        for future in as_completed(future_map):
            f = future_map[future]
            try:
                full_results[f] = future.result()
            except (OSError, PermissionError):
                continue

    hash_groups: dict[str, list[Path]] = defaultdict(list)
    for f, fh in full_results.items():
        hash_groups[fh].append(f)

    return [g for g in hash_groups.values() if len(g) > 1]


# ══════════════════════════════════════════════════════════
#  操作日志（支持一键复原）
# ══════════════════════════════════════════════════════════

class OperationLog:
    """记录每次移动/重命名操作，用于一键复原。"""

    def __init__(self, target: Path):
        self.target = target
        self.hidden_dir = target / HIDDEN_DIR
        self.hidden_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.hidden_dir / LOG_FILENAME
        self.entries: list[dict] = []
        self.meta: dict = {}

    def set_meta(self, **kwargs):
        self.meta.update(kwargs)

    def record_move(self, original: str, destination: str):
        self.entries.append({
            "action": "move",
            "src": original,
            "dst": destination,
        })

    def record_rename(self, original: str, new_name: str):
        self.entries.append({
            "action": "rename",
            "src": original,
            "dst": new_name,
        })

    def record_mkdir(self, dirpath: str):
        for e in self.entries:
            if e["action"] == "mkdir" and e["path"] == dirpath:
                return
        self.entries.append({
            "action": "mkdir",
            "path": dirpath,
        })

    def record_snapshot(self, dirs: list[str]):
        """记录整理前已存在的目录，undo 时只清理我们创建的。"""
        self.meta["pre_existing_dirs"] = dirs

    def save(self):
        data = {
            "version": __version__,
            "timestamp": datetime.datetime.now().isoformat(),
            "target": str(self.target),
            "meta": self.meta,
            "entries": self.entries,
        }
        self.log_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, target: Path) -> "OperationLog | None":
        # 优先从隐藏目录读取，兼容旧路径
        hidden_path = target / HIDDEN_DIR / LOG_FILENAME
        old_path = target / LOG_FILENAME
        log_path = hidden_path if hidden_path.exists() else old_path
        if not log_path.exists():
            return None
        try:
            data = json.loads(log_path.read_text(encoding="utf-8"))
            log = cls(target)
            log.meta = data.get("meta", {})
            log.entries = data.get("entries", [])
            return log
        except (json.JSONDecodeError, KeyError):
            return None


def undo_operations(target: Path, verbose: bool = False) -> bool:
    """读取操作日志，逆序执行复原。"""
    log = OperationLog.load(target)
    if log is None:
        print(f"❌ 未找到操作日志：{target / LOG_FILENAME}")
        print("   可能原因：该目录从未被 File Organizer 整理过，或日志已被删除。")
        return False

    entries = log.entries
    if not entries:
        print("日志为空，无需复原。")
        return True

    print(f"📋 找到操作日志：{len(entries)} 条记录（{log.meta.get('timestamp', '未知时间')}）")
    print(f"   整理模式：{log.meta.get('mode', '未知')}")
    print()

    undone = 0
    errors = []

    for entry in reversed(entries):
        action = entry["action"]

        if action == "move":
            src_path = Path(entry["dst"])
            dst_path = Path(entry["src"])
            if src_path.exists():
                try:
                    dst_path.parent.mkdir(parents=True, exist_ok=True)
                    if dst_path.exists() and dst_path.resolve() != src_path.resolve():
                        stem, suffix = dst_path.stem, dst_path.suffix
                        counter = 1
                        while dst_path.exists():
                            dst_path = dst_path.parent / f"{stem}_undo_{counter}{suffix}"
                            counter += 1
                    shutil.move(str(src_path), str(dst_path))
                    undone += 1
                    if verbose:
                        print(f"  [复原] {src_path.name} → {dst_path.parent.name}/")
                except Exception as e:
                    errors.append(f"复原失败 {src_path}: {e}")
            else:
                errors.append(f"文件不存在，跳过：{src_path}")

        elif action == "rename":
            src_path = Path(entry["dst"])
            dst_path = Path(entry["src"])
            if src_path.exists():
                try:
                    shutil.move(str(src_path), str(dst_path))
                    undone += 1
                    if verbose:
                        print(f"  [复原重命名] {src_path.name} → {dst_path.name}")
                except Exception as e:
                    errors.append(f"复原重命名失败 {src_path}: {e}")
            else:
                errors.append(f"文件不存在，跳过：{src_path}")

        elif action == "mkdir":
            dirpath = Path(entry["path"])
            if dirpath.exists() and dirpath.is_dir():
                try:
                    remaining = list(dirpath.iterdir())
                    if not remaining:
                        dirpath.rmdir()
                        if verbose:
                            print(f"  [删除空目录] {dirpath.name}/")
                    else:
                        if verbose:
                            print(f"  [保留目录] {dirpath.name}/ （仍包含 {len(remaining)} 个文件）")
                except Exception as e:
                    errors.append(f"删除目录失败 {dirpath}: {e}")

        log.log_path.unlink(missing_ok=True)

    # 如果隐藏目录为空则删除
    if log.hidden_dir.exists() and not any(log.hidden_dir.iterdir()):
        log.hidden_dir.rmdir()

    print(f"\n✅ 复原完成：成功 {undone} 条")
    if errors:
        print(f"⚠️ {len(errors)} 个问题：")
        for err in errors:
            print(f"   - {err}")

    # 递归清理空目录
    our_dirs = set()
    for entry in entries:
        if entry["action"] == "mkdir":
            our_dirs.add(entry["path"])

    cleaned = 0
    sorted_dirs = sorted(our_dirs, key=lambda p: p.count(os.sep), reverse=True)
    for dirpath_str in sorted_dirs:
        dirpath = Path(dirpath_str)
        if dirpath.exists() and dirpath.is_dir():
            try:
                if _is_empty_recursive(dirpath):
                    _remove_empty_recursive(dirpath)
                    cleaned += 1
            except Exception as e:
                errors.append(f"清理目录失败 {dirpath}: {e}")

    if cleaned > 0:
        print(f"🧹 清理了 {cleaned} 个空目录（含子目录）")

    return len(errors) == 0


# ══════════════════════════════════════════════════════════
#  整理模式
# ══════════════════════════════════════════════════════════

def _base_stats() -> dict:
    return {
        "moved": 0, "skipped": 0, "renamed": 0,
        "by_category": defaultdict(int), "unmatched": [], "errors": [],
    }


def organize_by_type(target, files, op_log, dry_run=False, verbose=False):
    stats = _base_stats()
    for f in files:
        ext = f.suffix.lower()
        category = get_category(ext)
        if category is None:
            stats["skipped"] += 1
            stats["unmatched"].append(f.name)
            if verbose:
                print(f"  [跳过] {f.name} — 未知类型 {ext}")
            continue
        dst_dir = target / category
        try:
            if not dry_run:
                actual = safe_move(f, dst_dir)
                op_log.record_move(str(f), str(actual))
                op_log.record_mkdir(str(dst_dir))
            if verbose:
                tag = "预览" if dry_run else "移动"
                print(f"  [{tag}] {f.name} → {category}/")
            stats["moved"] += 1
            stats["by_category"][category] += 1
        except Exception as e:
            stats["errors"].append(f"移动失败 {f.name}: {e}")
    return stats


def organize_by_date(target, files, op_log, dry_run=False, verbose=False):
    stats = _base_stats()
    for f in files:
        try:
            mtime = datetime.datetime.fromtimestamp(f.stat().st_mtime)
            folder_name = mtime.strftime("%Y-%m")
        except (OSError, PermissionError):
            stats["skipped"] += 1
            stats["unmatched"].append(f.name)
            continue
        dst_dir = target / folder_name
        try:
            if not dry_run:
                actual = safe_move(f, dst_dir)
                op_log.record_move(str(f), str(actual))
                op_log.record_mkdir(str(dst_dir))
            if verbose:
                tag = "预览" if dry_run else "移动"
                print(f"  [{tag}] {f.name} → {folder_name}/")
            stats["moved"] += 1
            stats["by_category"][folder_name] += 1
        except Exception as e:
            stats["errors"].append(f"移动失败 {f.name}: {e}")
    return stats


def organize_by_extension(target, files, op_log, dry_run=False, verbose=False):
    stats = _base_stats()
    for f in files:
        ext = f.suffix.lower().lstrip(".")
        if not ext:
            ext = "no_extension"
        dst_dir = target / ext
        try:
            if not dry_run:
                actual = safe_move(f, dst_dir)
                op_log.record_move(str(f), str(actual))
                op_log.record_mkdir(str(dst_dir))
            if verbose:
                tag = "预览" if dry_run else "移动"
                print(f"  [{tag}] {f.name} → {ext}/")
            stats["moved"] += 1
            stats["by_category"][ext] += 1
        except Exception as e:
            stats["errors"].append(f"移动失败 {f.name}: {e}")
    return stats


def organize_by_size(target, files, op_log, dry_run=False, verbose=False):
    SIZE_BUCKETS = [
        ("<1MB", 0, 1_000_000),
        ("1-10MB", 1_000_000, 10_000_000),
        ("10-100MB", 10_000_000, 100_000_000),
        ("100MB-1GB", 100_000_000, 1_000_000_000),
        (">1GB", 1_000_000_000, float("inf")),
    ]
    stats = _base_stats()
    for f in files:
        try:
            size = f.stat().st_size
        except (OSError, PermissionError):
            stats["skipped"] += 1
            stats["unmatched"].append(f.name)
            continue
        bucket_name = ">1GB"
        for name, lo, hi in SIZE_BUCKETS:
            if lo <= size < hi:
                bucket_name = name
                break
        dst_dir = target / bucket_name
        try:
            if not dry_run:
                actual = safe_move(f, dst_dir)
                op_log.record_move(str(f), str(actual))
                op_log.record_mkdir(str(dst_dir))
            if verbose:
                tag = "预览" if dry_run else "移动"
                print(f"  [{tag}] {f.name} ({format_size(size)}) → {bucket_name}/")
            stats["moved"] += 1
            stats["by_category"][bucket_name] += 1
        except Exception as e:
            stats["errors"].append(f"移动失败 {f.name}: {e}")
    return stats


def organize_by_big5(target, files, op_log, dry_run=False, verbose=False):
    stats = _base_stats()
    for f in files:
        ext = f.suffix.lower()
        category = EXT_TO_BIG5.get(ext)
        if category is None:
            stats["skipped"] += 1
            stats["unmatched"].append(f.name)
            if verbose:
                print(f"  [跳过] {f.name} — 未归入五大类 ({ext})")
            continue
        dst_dir = target / category
        try:
            if not dry_run:
                actual = safe_move(f, dst_dir)
                op_log.record_move(str(f), str(actual))
                op_log.record_mkdir(str(dst_dir))
            if verbose:
                tag = "预览" if dry_run else "移动"
                print(f"  [{tag}] {f.name} → {category}/")
            stats["moved"] += 1
            stats["by_category"][category] += 1
        except Exception as e:
            stats["errors"].append(f"移动失败 {f.name}: {e}")
    return stats


# ── 模式注册表 ────────────────────────────────────────────
MODES = {
    "type": ("按类型归档", organize_by_type),
    "big5": ("五大类归档", organize_by_big5),
    "date": ("按日期归档", organize_by_date),
    "ext":  ("按扩展名归档", organize_by_extension),
    "size": ("按大小归档", organize_by_size),
}


# ══════════════════════════════════════════════════════════
#  报告生成
# ══════════════════════════════════════════════════════════

def generate_report(target, total_files, stats, duplicates, dry_run, mode_desc):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "# 📁 文件整理报告",
        "",
        f"- **整理目录**: `{target}`",
        f"- **执行时间**: {now}",
        f"- **模式**: {'预览（dry-run）' if dry_run else '实际执行'} — {mode_desc}",
        f"- **版本**: v{__version__}",
        "",
        "## 📊 操作摘要",
        "",
        "| 指标 | 数量 |",
        "|------|------|",
        f"| 扫描文件总数 | {total_files} |",
        f"| 已移动/归档 | {stats['moved']} |",
        f"| 已重命名 | {stats.get('renamed', 0)} |",
        f"| 跳过 | {stats['skipped']} |",
        f"| 错误 | {len(stats['errors'])} |",
        "",
    ]

    if stats["by_category"]:
        lines += ["## 📂 分类统计", "", "| 类别 | 文件数 |", "|------|--------|"]
        for cat, count in sorted(stats["by_category"].items(), key=lambda x: -x[1]):
            lines.append(f"| {cat} | {count} |")
        lines.append("")

    if stats["unmatched"]:
        lines += ["## ❓ 未匹配文件（保留在原位）", ""]
        for name in stats["unmatched"][:50]:
            lines.append(f"- {name}")
        if len(stats["unmatched"]) > 50:
            lines.append(f"- ...还有 {len(stats['unmatched']) - 50} 个")
        lines.append("")

    if duplicates:
        lines += [
            "## 🔁 重复文件检测", "",
            f"共发现 **{len(duplicates)}** 组重复文件：", "",
        ]
        for i, group in enumerate(duplicates, 1):
            lines += [
                f"### 第 {i} 组（{len(group)} 份）", "",
                "| # | 文件 | 大小 | 修改时间 | 状态 |",
                "|---|------|------|---------|------|",
            ]
            for j, f in enumerate(group):
                try:
                    st = f.stat()
                    sz = format_size(st.st_size)
                    mt = datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")
                except OSError:
                    sz, mt = "未知", "未知"
                marker = "✅ 保留" if j == 0 else "🗑️ 可清理"
                lines.append(f"| {j+1} | `{f.name}` | {sz} | {mt} | {marker} |")
            lines.append("")

    if stats["errors"]:
        lines += ["## ⚠️ 错误记录", ""]
        for err in stats["errors"]:
            lines.append(f"- {err}")
        lines.append("")

    lines += [
        "---",
        f"*由 File Organizer v{__version__} 生成*",
        f"*复原命令: `python organize.py \"{target}\" --undo`*",
    ]
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════
#  主入口
# ══════════════════════════════════════════════════════════

def main():
    setup_encoding()

    parser = argparse.ArgumentParser(
        description="File Organizer v2.2 — 本地文件夹智能整理",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
整理模式:
  type    按文件类型归档（Documents/Images/Videos/...）
  big5    五大类归档（文档/图片/视频音频/压缩包/安装程序）
  date    按修改日期归档（2026-05/）
  ext     按扩展名归档（pdf/ jpg/ mp4/...）
  size    按文件大小归档（<1MB/ 1-10MB/...）

示例:
  python organize.py ~/Downloads                    # 默认按类型归档
  python organize.py ~/Downloads --mode date        # 按日期归档
  python organize.py ~/Downloads --mode ext -v      # 按扩展名，详细输出
  python organize.py ~/Downloads --duplicates-only  # 仅查重
  python organize.py ~/Downloads --undo             # 一键复原上次整理
  python organize.py ~/Downloads --dry-run --mode size  # 预览按大小归档
  python organize.py ~/Downloads --clean-empty-dirs # 扫描空文件夹
  python organize.py ~/Downloads --clean-empty-dirs --execute  # 删除空文件夹
""",
    )
    parser.add_argument("target_dir", help="要整理的目录路径")
    parser.add_argument(
        "--mode", choices=list(MODES.keys()), default="type",
        help="整理模式（默认: type）",
    )
    parser.add_argument("--dry-run", action="store_true", help="预览模式，不实际操作")
    parser.add_argument("--duplicates-only", action="store_true", help="仅检测重复文件")
    parser.add_argument("--undo", action="store_true", help="一键复原上次整理操作")
    parser.add_argument("--report-only", action="store_true", help="仅生成报告")
    parser.add_argument("--skip-dirs", nargs="+", default=[], help="额外跳过的子目录名")
    parser.add_argument("--clean-empty-dirs", action="store_true", help="扫描空文件夹（仅报告，不删除）")
    parser.add_argument("--execute", action="store_true", help="配合 --clean-empty-dirs 实际删除空文件夹")
    parser.add_argument("--category", type=str, default=None,
                        help="仅整理指定分类的文件（文档/图片/视频音频/压缩包/安装程序）")
    parser.add_argument("-v", "--verbose", action="store_true", help="详细输出")

    args = parser.parse_args()
    target = Path(args.target_dir).resolve()

    if not target.is_dir():
        print(f"❌ 错误：目录不存在 — {target}")
        sys.exit(1)

    skip_dirs = set(args.skip_dirs)

    # ── 一键复原 ──
    if args.undo:
        print(f"🔄 复原目录: {target}")
        success = undo_operations(target, verbose=args.verbose)
        sys.exit(0 if success else 1)

    # ── 空文件夹扫描 ──
    if args.clean_empty_dirs:
        print(f"🔍 扫描空文件夹: {target}")
        empty_dirs = _find_empty_dirs_recursive(target)
        if empty_dirs:
            print(f"\n📂 发现 {len(empty_dirs)} 个空文件夹：")
            for d in empty_dirs:
                print(f"   - {d.relative_to(target)}/")
            if args.execute:
                print("\n🗑️  执行删除...")
                deleted = 0
                for d in sorted(empty_dirs, key=lambda p: len(p.parts), reverse=True):
                    try:
                        d.rmdir()
                        deleted += 1
                        if args.verbose:
                            print(f"   [删除] {d.relative_to(target)}/")
                    except OSError as e:
                        print(f"   [失败] {d.relative_to(target)}/: {e}")
                print(f"\n✅ 删除完成：{deleted}/{len(empty_dirs)} 个空文件夹")
            else:
                print("\n💡 要删除这些空文件夹，请运行：")
                print(f"   python organize.py \"{target}\" --clean-empty-dirs --execute")
        else:
            print("✅ 未发现空文件夹")
        sys.exit(0)

    # ── 扫描 ──
    print(f"🔍 扫描目录: {target}")
    files = scan_directory(target, skip_dirs)
    print(f"   找到 {len(files)} 个文件")

    if not files:
        print("   目录为空，无需整理。")
        sys.exit(0)

    # ── 分类过滤 ──
    if args.category:
        cat_lower = args.category.lower()
        # 支持中文分类名映射
        cat_aliases = {"文档": "documents", "图片": "images", "视频音频": "videos",
                       "压缩包": "archives", "安装程序": "installers"}
        cat_en = cat_aliases.get(cat_lower, cat_lower)
        before = len(files)
        files = [f for f in files if (cat := get_category(f.suffix.lower())) is not None and (cat.lower() == cat_en.lower() or cat.lower() == cat_lower)]
        print(f"   分类过滤: {before} → {len(files)} 个文件（{args.category}）")
        if not files:
            print("   该分类下没有文件，无需整理。")
            sys.exit(0)

    # ── 重复检测 ──
    print("🔄 检测重复文件...")
    duplicates = find_duplicates(files, verbose=args.verbose)
    dup_count = sum(len(g) - 1 for g in duplicates)
    if duplicates:
        print(f"   发现 {len(duplicates)} 组重复（共 {dup_count} 个冗余文件）")
    else:
        print("   未发现重复 ✓")

    # ── 仅查重模式 ──
    if args.duplicates_only:
        mode_desc = "仅重复检测"
        stats = _base_stats()
    else:
        mode_label, mode_func = MODES[args.mode]
        mode_desc = mode_label
        print(f"📦 执行: {mode_desc} {'(预览)' if args.dry_run else ''}")

        op_log = OperationLog(target)
        op_log.set_meta(
            mode=mode_desc,
            file_count=len(files),
            dry_run=args.dry_run,
        )

        if args.report_only:
            stats = _base_stats()
        else:
            pre_dirs = [
                str(d) for d in target.iterdir()
                if d.is_dir() and not d.name.startswith(".")
            ]
            op_log.record_snapshot(pre_dirs)

            stats = mode_func(
                target, files, op_log,
                dry_run=args.dry_run,
                verbose=args.verbose,
            )
            print(
                f"   完成: 移动 {stats['moved']}, "
                f"跳过 {stats['skipped']}"
            )
            if stats["errors"]:
                print(f"   ⚠️ {len(stats['errors'])} 个错误")

            if not args.dry_run and stats["moved"] > 0:
                op_log.save()
                print("📝 操作日志已保存（可用 --undo 复原）")

    # ── 生成报告 ──
    report = generate_report(target, len(files), stats, duplicates, args.dry_run, mode_desc)
    report_path = target / HIDDEN_DIR / REPORT_FILENAME

    if not args.dry_run:
        report_path.write_text(report, encoding="utf-8")
        print(f"📝 报告已保存: {report_path}")
    else:
        print(f"\n📝 预览报告:")
        print(report)

    print("\n✅ 完成!")


if __name__ == "__main__":
    main()
