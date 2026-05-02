#!/usr/bin/env python3
"""
File Organizer GUI v2.1 — 双击即用的文件夹整理工具
零依赖，纯 Python 标准库（tkinter）。
"""

import os
import sys
import io
import json
import shutil
import hashlib
import datetime
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

__version__ = "2.1.0"

# ══════════════════════════════════════════════════════════
#  核心逻辑（从 organize.py 提取）
# ══════════════════════════════════════════════════════════

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
    "Fonts": {".ttf", ".otf", ".woff", ".woff2", ".eot"},
    "Installers": {
        ".exe", ".msi", ".dmg", ".pkg", ".deb", ".rpm", ".apk",
        ".appimage", ".snap", ".flatpak",
    },
}

EXT_TO_CATEGORY = {}
for _cat, _exts in CATEGORY_MAP.items():
    for _ext in _exts:
        EXT_TO_CATEGORY[_ext] = _cat

BIG5_MAP = {
    "文档": {
        ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt",
        ".txt", ".csv", ".md", ".rtf", ".odt", ".ods", ".odp",
        ".epub", ".mobi", ".pages", ".numbers", ".key", ".dwg", ".dxf",
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

LOG_FILENAME = "._file_organizer_log.json"
REPORT_FILENAME = "._file_organizer_report.md"


def format_size(size_bytes):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def is_internal(name):
    return name.startswith("._file_organizer_")


def _is_empty_recursive(path):
    if not path.is_dir():
        return False
    for item in path.iterdir():
        if item.is_file():
            return False
        if item.is_dir() and not _is_empty_recursive(item):
            return False
    return True


def _remove_empty_recursive(path):
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


def _find_empty_dirs_recursive(root):
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


def scan_directory(target, skip_dirs):
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


def _same_partition(p1, p2):
    try:
        return p1.resolve().drive.lower() == p2.resolve().drive.lower()
    except AttributeError:
        return True


def safe_move(src, dst_dir):
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


def _quick_hash(path):
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


def _full_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(131072)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def find_duplicates(files):
    size_groups = defaultdict(list)
    for f in files:
        try:
            size = f.stat().st_size
            if size == 0:
                continue
            size_groups[size].append(f)
        except (OSError, PermissionError):
            continue

    candidates = [g for g in size_groups.values() if len(g) >= 2]
    if not candidates:
        return []

    to_quick = []
    for g in candidates:
        to_quick.extend(g)

    quick_results = {}
    with ThreadPoolExecutor(min(16, len(to_quick))) as ex:
        fmap = {ex.submit(_quick_hash, f): f for f in to_quick}
        for fut in as_completed(fmap):
            f = fmap[fut]
            try:
                quick_results[f] = fut.result()
            except (OSError, PermissionError):
                continue

    qgroups = defaultdict(list)
    for f, qh in quick_results.items():
        qgroups[qh].append(f)

    to_full = []
    for g in qgroups.values():
        if len(g) >= 2:
            to_full.extend(g)

    if not to_full:
        return []

    full_results = {}
    with ThreadPoolExecutor(min(8, len(to_full))) as ex:
        fmap = {ex.submit(_full_hash, f): f for f in to_full}
        for fut in as_completed(fmap):
            f = fmap[fut]
            try:
                full_results[f] = fut.result()
            except (OSError, PermissionError):
                continue

    hgroups = defaultdict(list)
    for f, fh in full_results.items():
        hgroups[fh].append(f)

    return [g for g in hgroups.values() if len(g) > 1]


class OperationLog:
    def __init__(self, target):
        self.target = target
        self.log_path = target / LOG_FILENAME
        self.entries = []
        self.meta = {}

    def set_meta(self, **kw):
        self.meta.update(kw)

    def record_move(self, original, destination):
        self.entries.append({"action": "move", "src": original, "dst": destination})

    def record_mkdir(self, dirpath):
        for e in self.entries:
            if e["action"] == "mkdir" and e["path"] == dirpath:
                return
        self.entries.append({"action": "mkdir", "path": dirpath})

    def record_snapshot(self, dirs):
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
    def load(cls, target):
        log_path = target / LOG_FILENAME
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


def undo_operations(target, callback=None):
    log = OperationLog.load(target)
    if log is None:
        return False, "未找到操作日志"

    entries = log.entries
    if not entries:
        return True, "日志为空，无需复原"

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
                        c = 1
                        while dst_path.exists():
                            dst_path = dst_path.parent / f"{stem}_undo_{c}{suffix}"
                            c += 1
                    shutil.move(str(src_path), str(dst_path))
                    undone += 1
                    if callback:
                        callback(f"  [复原] {src_path.name} → {dst_path.parent.name}/")
                except Exception as e:
                    errors.append(f"复原失败 {src_path}: {e}")
            else:
                errors.append(f"文件不存在：{src_path}")

    log.log_path.unlink(missing_ok=True)

    our_dirs = {e["path"] for e in entries if e["action"] == "mkdir"}
    for d in sorted(our_dirs, key=lambda p: p.count(os.sep), reverse=True):
        dp = Path(d)
        if dp.exists() and dp.is_dir():
            try:
                if _is_empty_recursive(dp):
                    _remove_empty_recursive(dp)
            except Exception:
                pass

    return len(errors) == 0, f"复原 {undone} 条" + (f"，{len(errors)} 个问题" if errors else "")


# ── 整理模式 ──

def _base_stats():
    return {
        "moved": 0, "skipped": 0, "errors": [],
        "by_category": defaultdict(int), "unmatched": [],
    }


def organize_by_type(target, files, op_log, dry_run=False, callback=None):
    stats = _base_stats()
    for f in files:
        cat = EXT_TO_CATEGORY.get(f.suffix.lower())
        if cat is None:
            stats["skipped"] += 1
            stats["unmatched"].append(f.name)
            continue
        dst = target / cat
        try:
            if not dry_run:
                actual = safe_move(f, dst)
                op_log.record_move(str(f), str(actual))
                op_log.record_mkdir(str(dst))
            if callback:
                callback(f"  {'预览' if dry_run else '移动'} {f.name} → {cat}/")
            stats["moved"] += 1
            stats["by_category"][cat] += 1
        except Exception as e:
            stats["errors"].append(f"{f.name}: {e}")
    return stats


def organize_by_big5(target, files, op_log, dry_run=False, callback=None):
    stats = _base_stats()
    for f in files:
        cat = EXT_TO_BIG5.get(f.suffix.lower())
        if cat is None:
            stats["skipped"] += 1
            stats["unmatched"].append(f.name)
            continue
        dst = target / cat
        try:
            if not dry_run:
                actual = safe_move(f, dst)
                op_log.record_move(str(f), str(actual))
                op_log.record_mkdir(str(dst))
            if callback:
                callback(f"  {'预览' if dry_run else '移动'} {f.name} → {cat}/")
            stats["moved"] += 1
            stats["by_category"][cat] += 1
        except Exception as e:
            stats["errors"].append(f"{f.name}: {e}")
    return stats


def organize_by_date(target, files, op_log, dry_run=False, callback=None):
    stats = _base_stats()
    for f in files:
        try:
            folder = datetime.datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m")
        except (OSError, PermissionError):
            stats["skipped"] += 1
            continue
        dst = target / folder
        try:
            if not dry_run:
                actual = safe_move(f, dst)
                op_log.record_move(str(f), str(actual))
                op_log.record_mkdir(str(dst))
            if callback:
                callback(f"  {'预览' if dry_run else '移动'} {f.name} → {folder}/")
            stats["moved"] += 1
            stats["by_category"][folder] += 1
        except Exception as e:
            stats["errors"].append(f"{f.name}: {e}")
    return stats


def organize_by_ext(target, files, op_log, dry_run=False, callback=None):
    stats = _base_stats()
    for f in files:
        ext = f.suffix.lower().lstrip(".") or "no_ext"
        dst = target / ext
        try:
            if not dry_run:
                actual = safe_move(f, dst)
                op_log.record_move(str(f), str(actual))
                op_log.record_mkdir(str(dst))
            if callback:
                callback(f"  {'预览' if dry_run else '移动'} {f.name} → {ext}/")
            stats["moved"] += 1
            stats["by_category"][ext] += 1
        except Exception as e:
            stats["errors"].append(f"{f.name}: {e}")
    return stats


def organize_by_size(target, files, op_log, dry_run=False, callback=None):
    BUCKETS = [
        ("<1MB", 0, 1_000_000), ("1-10MB", 1_000_000, 10_000_000),
        ("10-100MB", 10_000_000, 100_000_000), ("100MB-1GB", 100_000_000, 1_000_000_000),
        (">1GB", 1_000_000_000, float("inf")),
    ]
    stats = _base_stats()
    for f in files:
        try:
            size = f.stat().st_size
        except (OSError, PermissionError):
            stats["skipped"] += 1
            continue
        bucket = ">1GB"
        for name, lo, hi in BUCKETS:
            if lo <= size < hi:
                bucket = name
                break
        dst = target / bucket
        try:
            if not dry_run:
                actual = safe_move(f, dst)
                op_log.record_move(str(f), str(actual))
                op_log.record_mkdir(str(dst))
            if callback:
                callback(f"  {'预览' if dry_run else '移动'} {f.name} ({format_size(size)}) → {bucket}/")
            stats["moved"] += 1
            stats["by_category"][bucket] += 1
        except Exception as e:
            stats["errors"].append(f"{f.name}: {e}")
    return stats


MODES = {
    "按类型": organize_by_type,
    "五大类": organize_by_big5,
    "按日期": organize_by_date,
    "按扩展名": organize_by_ext,
    "按大小": organize_by_size,
}


def generate_report(target, total, stats, duplicates, dry_run, mode_name):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "# 📁 文件整理报告", "",
        f"- **目录**: `{target}`",
        f"- **时间**: {now}",
        f"- **模式**: {'预览' if dry_run else '执行'} — {mode_name}",
        f"- **版本**: v{__version__}", "",
        "## 📊 操作摘要", "",
        "| 指标 | 数量 |", "|------|------|",
        f"| 扫描文件 | {total} |",
        f"| 已移动 | {stats['moved']} |",
        f"| 跳过 | {stats['skipped']} |",
        f"| 错误 | {len(stats['errors'])} |", "",
    ]
    if stats["by_category"]:
        lines += ["## 📂 分类统计", "", "| 类别 | 数量 |", "|------|------|"]
        for cat, cnt in sorted(stats["by_category"].items(), key=lambda x: -x[1]):
            lines.append(f"| {cat} | {cnt} |")
        lines.append("")
    if duplicates:
        lines += [f"## 🔁 重复文件（{len(duplicates)} 组）", ""]
        for i, grp in enumerate(duplicates, 1):
            lines.append(f"### 第 {i} 组")
            for j, f in enumerate(grp):
                try:
                    sz = format_size(f.stat().st_size)
                except OSError:
                    sz = "?"
                tag = "保留" if j == 0 else "可清理"
                lines.append(f"- `{f.name}` ({sz}) — {tag}")
            lines.append("")
    if stats["errors"]:
        lines += ["## ⚠️ 错误", ""]
        for e in stats["errors"]:
            lines.append(f"- {e}")
        lines.append("")
    lines += ["---", f"*File Organizer v{__version__}*"]
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════
#  GUI
# ══════════════════════════════════════════════════════════

# ── 颜色主题 ──
BG = "#1e1e2e"
BG2 = "#282840"
BG3 = "#313150"
FG = "#cdd6f4"
FG2 = "#a6adc8"
ACCENT = "#89b4fa"
ACCENT2 = "#74c7ec"
GREEN = "#a6e3a1"
RED = "#f38ba8"
YELLOW = "#f9e2af"
PEACH = "#fab387"
SURFACE = "#45475a"

FONT_TITLE = ("Microsoft YaHei UI", 16, "bold")
FONT_BODY = ("Microsoft YaHei UI", 10)
FONT_SMALL = ("Microsoft YaHei UI", 9)
FONT_MONO = ("Cascadia Mono", 9)
FONT_BTN = ("Microsoft YaHei UI", 10, "bold")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"📂 File Organizer v{__version__}")
        self.geometry("820x680")
        self.minsize(700, 550)
        self.configure(bg=BG)
        self.resizable(True, True)

        # 居中
        self.update_idletasks()
        w, h = 820, 680
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

        self._build_ui()
        self._running = False

    def _build_ui(self):
        # ── 顶部标题栏 ──
        header = tk.Frame(self, bg=BG2, height=56)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="📂 File Organizer", font=FONT_TITLE,
                 bg=BG2, fg=ACCENT).pack(side="left", padx=16, pady=10)
        tk.Label(header, text=f"v{__version__}", font=FONT_SMALL,
                 bg=BG2, fg=FG2).pack(side="left", pady=10)

        # ── 主内容区 ──
        main = tk.Frame(self, bg=BG)
        main.pack(fill="both", expand=True, padx=16, pady=(12, 16))

        # -- 目录选择 --
        dir_frame = tk.LabelFrame(main, text=" 📁 目标目录 ", font=FONT_BODY,
                                  bg=BG, fg=FG2, bd=1, relief="groove",
                                  labelanchor="nw")
        dir_frame.pack(fill="x", pady=(0, 10))

        row = tk.Frame(dir_frame, bg=BG)
        row.pack(fill="x", padx=10, pady=8)

        self.dir_var = tk.StringVar()
        self.dir_entry = tk.Entry(row, textvariable=self.dir_var, font=FONT_BODY,
                                  bg=BG3, fg=FG, insertbackground=FG,
                                  relief="flat", bd=6)
        self.dir_entry.pack(side="left", fill="x", expand=True)

        btn_browse = tk.Button(row, text="浏览...", font=FONT_BTN,
                               bg=ACCENT, fg=BG, activebackground=ACCENT2,
                               relief="flat", bd=0, padx=14, pady=4,
                               command=self._browse)
        btn_browse.pack(side="right", padx=(8, 0))

        # -- 模式选择 --
        mode_frame = tk.LabelFrame(main, text=" 📦 整理模式 ", font=FONT_BODY,
                                   bg=BG, fg=FG2, bd=1, relief="groove",
                                   labelanchor="nw")
        mode_frame.pack(fill="x", pady=(0, 10))

        modes_row = tk.Frame(mode_frame, bg=BG)
        modes_row.pack(fill="x", padx=10, pady=8)

        self.mode_var = tk.StringVar(value="按类型")
        modes = list(MODES.keys())
        for i, m in enumerate(modes):
            rb = tk.Radiobutton(
                modes_row, text=m, variable=self.mode_var, value=m,
                font=FONT_BODY, bg=BG, fg=FG, selectcolor=BG3,
                activebackground=BG, activeforeground=ACCENT,
                indicatoron=False, padx=14, pady=6,
                relief="flat", bd=1,
            )
            rb.pack(side="left", padx=(0, 6))

        # -- 选项行 --
        opts_row = tk.Frame(main, bg=BG)
        opts_row.pack(fill="x", pady=(0, 10))

        self.dryrun_var = tk.BooleanVar(value=True)
        tk.Checkbutton(opts_row, text="预览模式（不实际移动）", variable=self.dryrun_var,
                       font=FONT_BODY, bg=BG, fg=YELLOW, selectcolor=BG3,
                       activebackground=BG).pack(side="left")

        self.verbose_var = tk.BooleanVar(value=True)
        tk.Checkbutton(opts_row, text="详细输出", variable=self.verbose_var,
                       font=FONT_BODY, bg=BG, fg=FG2, selectcolor=BG3,
                       activebackground=BG).pack(side="left", padx=(16, 0))

        # -- 操作按钮 --
        btn_frame = tk.Frame(main, bg=BG)
        btn_frame.pack(fill="x", pady=(0, 10))

        self.btn_run = tk.Button(btn_frame, text="▶ 开始整理", font=FONT_BTN,
                                 bg=GREEN, fg=BG, activebackground="#85d67a",
                                 relief="flat", bd=0, padx=24, pady=8,
                                 command=self._run)
        self.btn_run.pack(side="left")

        self.btn_dup = tk.Button(btn_frame, text="🔁 查重", font=FONT_BTN,
                                 bg=PEACH, fg=BG, activebackground="#e89a6e",
                                 relief="flat", bd=0, padx=18, pady=8,
                                 command=self._dup_only)
        self.btn_dup.pack(side="left", padx=(8, 0))

        self.btn_undo = tk.Button(btn_frame, text="↩ 复原", font=FONT_BTN,
                                  bg=YELLOW, fg=BG, activebackground="#e6d48e",
                                  relief="flat", bd=0, padx=18, pady=8,
                                  command=self._undo)
        self.btn_undo.pack(side="left", padx=(8, 0))

        self.btn_empty = tk.Button(btn_frame, text="🧹 空文件夹", font=FONT_BTN,
                                   bg=ACCENT, fg=BG, activebackground=ACCENT2,
                                   relief="flat", bd=0, padx=14, pady=8,
                                   command=self._clean_empty)
        self.btn_empty.pack(side="left", padx=(8, 0))

        self.btn_stop = tk.Button(btn_frame, text="⏹ 停止", font=FONT_BTN,
                                  bg=RED, fg=BG, activebackground="#d66a7a",
                                  relief="flat", bd=0, padx=14, pady=8,
                                  command=self._stop, state="disabled")
        self.btn_stop.pack(side="right")

        # -- 进度条 --
        self.progress = ttk.Progressbar(main, mode="indeterminate", length=200)
        self.progress.pack(fill="x", pady=(0, 8))

        # -- 日志输出 --
        log_frame = tk.LabelFrame(main, text=" 📋 输出 ", font=FONT_BODY,
                                  bg=BG, fg=FG2, bd=1, relief="groove",
                                  labelanchor="nw")
        log_frame.pack(fill="both", expand=True)

        self.log_text = tk.Text(log_frame, font=FONT_MONO, bg=BG3, fg=FG,
                                insertbackground=FG, relief="flat", bd=6,
                                wrap="word", state="disabled",
                                selectbackground=ACCENT, selectforeground=BG)
        scrollbar = tk.Scrollbar(log_frame, command=self.log_text.yview,
                                 bg=BG3, troughcolor=BG)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.log_text.pack(fill="both", expand=True, padx=(6, 0), pady=6)

        # 日志标签
        self.log_text.tag_configure("info", foreground=FG)
        self.log_text.tag_configure("success", foreground=GREEN)
        self.log_text.tag_configure("warn", foreground=YELLOW)
        self.log_text.tag_configure("error", foreground=RED)
        self.log_text.tag_configure("accent", foreground=ACCENT)
        self.log_text.tag_configure("dim", foreground=FG2)

        # -- 底部状态栏 --
        self.status_var = tk.StringVar(value="就绪")
        status_bar = tk.Label(self, textvariable=self.status_var, font=FONT_SMALL,
                              bg=BG2, fg=FG2, anchor="w", padx=12)
        status_bar.pack(fill="x", side="bottom")

    def _browse(self):
        d = filedialog.askdirectory(title="选择要整理的目录")
        if d:
            self.dir_var.set(d)

    def _log(self, msg, tag="info"):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", msg + "\n", tag)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _get_target(self):
        d = self.dir_var.get().strip()
        if not d:
            messagebox.showwarning("提示", "请先选择要整理的目录")
            return None
        p = Path(d)
        if not p.is_dir():
            messagebox.showerror("错误", f"目录不存在：\n{d}")
            return None
        return p

    def _set_running(self, running):
        self._running = running
        if running:
            self.btn_run.config(state="disabled")
            self.btn_dup.config(state="disabled")
            self.btn_undo.config(state="disabled")
            self.btn_empty.config(state="disabled")
            self.btn_stop.config(state="normal")
            self.progress.start(12)
        else:
            self.btn_run.config(state="normal")
            self.btn_dup.config(state="normal")
            self.btn_undo.config(state="normal")
            self.btn_empty.config(state="normal")
            self.btn_stop.config(state="disabled")
            self.progress.stop()

    def _stop(self):
        self._running = False

    def _run(self):
        target = self._get_target()
        if not target:
            return
        self._clear_log()
        self._set_running(True)
        self.status_var.set("正在整理...")

        def worker():
            try:
                self._do_organize(target)
            except Exception as e:
                self._log(f"\n❌ 异常: {e}", "error")
            finally:
                self.after(0, lambda: (self._set_running(False),
                                       self.status_var.set("完成")))

        threading.Thread(target=worker, daemon=True).start()

    def _do_organize(self, target):
        dry_run = self.dryrun_var.get()
        mode_name = self.mode_var.get()
        mode_func = MODES[mode_name]

        self._log(f"🔍 扫描: {target}", "accent")
        files = scan_directory(target, set())
        self._log(f"   找到 {len(files)} 个文件", "dim")

        if not files:
            self._log("   目录为空，无需整理。", "warn")
            return

        self._log("🔄 检测重复文件...", "accent")
        duplicates = find_duplicates(files)
        dup_count = sum(len(g) - 1 for g in duplicates)
        if duplicates:
            self._log(f"   发现 {len(duplicates)} 组重复（{dup_count} 个冗余）", "warn")
        else:
            self._log("   无重复 ✓", "success")

        tag = "预览" if dry_run else "执行"
        self._log(f"\n📦 {tag}: {mode_name}", "accent")
        self._log("─" * 40, "dim")

        op_log = OperationLog(target)
        op_log.set_meta(mode=mode_name, file_count=len(files), dry_run=dry_run)
        pre_dirs = [str(d) for d in target.iterdir()
                    if d.is_dir() and not d.name.startswith(".")]
        op_log.record_snapshot(pre_dirs)

        def cb(msg):
            self.after(0, lambda m=msg: self._log(m))

        stats = mode_func(target, files, op_log, dry_run=dry_run, callback=cb)

        self._log("─" * 40, "dim")
        self._log(f"✅ 移动 {stats['moved']}，跳过 {stats['skipped']}", "success")
        if stats["errors"]:
            self._log(f"⚠️ {len(stats['errors'])} 个错误", "error")

        if not dry_run and stats["moved"] > 0:
            op_log.save()
            self._log("📝 操作日志已保存（可点「复原」撤销）", "dim")

        # 报告
        report = generate_report(target, len(files), stats, duplicates, dry_run, mode_name)
        if not dry_run:
            rp = target / REPORT_FILENAME
            rp.write_text(report, encoding="utf-8")
            self._log(f"📝 报告: {rp}", "dim")

        # 重复文件详情
        if duplicates:
            self._log(f"\n🔁 重复文件详情:", "accent")
            for i, grp in enumerate(duplicates, 1):
                self._log(f"\n  第 {i} 组:", "warn")
                for j, f in enumerate(grp):
                    try:
                        sz = format_size(f.stat().st_size)
                    except OSError:
                        sz = "?"
                    tag2 = "✅ 保留" if j == 0 else "🗑️ 可清理"
                    self._log(f"    {tag2} {f.name} ({sz})")

        self.status_var.set(f"完成 — 移动 {stats['moved']} 个文件")

    def _dup_only(self):
        target = self._get_target()
        if not target:
            return
        self._clear_log()
        self._set_running(True)
        self.status_var.set("检测重复文件...")

        def worker():
            try:
                self._log(f"🔍 扫描: {target}", "accent")
                files = scan_directory(target, set())
                self._log(f"   找到 {len(files)} 个文件", "dim")

                self._log("🔄 检测重复...", "accent")
                duplicates = find_duplicates(files)

                if not duplicates:
                    self._log("\n✅ 未发现重复文件", "success")
                else:
                    dup_count = sum(len(g) - 1 for g in duplicates)
                    self._log(f"\n🔁 发现 {len(duplicates)} 组重复（{dup_count} 个冗余）", "warn")
                    for i, grp in enumerate(duplicates, 1):
                        self._log(f"\n  第 {i} 组:", "accent")
                        for j, f in enumerate(grp):
                            try:
                                sz = format_size(f.stat().st_size)
                                mt = datetime.datetime.fromtimestamp(
                                    f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                            except OSError:
                                sz, mt = "?", "?"
                            tag = "✅ 保留" if j == 0 else "🗑️ 可清理"
                            self._log(f"    {tag} {f.name} ({sz}, {mt})")

                self.status_var.set(f"查重完成 — {len(duplicates)} 组重复")
            except Exception as e:
                self._log(f"\n❌ 异常: {e}", "error")
            finally:
                self.after(0, lambda: self._set_running(False))

        threading.Thread(target=worker, daemon=True).start()

    def _undo(self):
        target = self._get_target()
        if not target:
            return
        self._clear_log()
        self._set_running(True)
        self.status_var.set("复原中...")

        def worker():
            try:
                self._log(f"🔄 复原: {target}", "accent")
                ok, msg = undo_operations(target, callback=lambda m: self.after(0, lambda m=m: self._log(m)))
                if ok:
                    self._log(f"\n✅ {msg}", "success")
                else:
                    self._log(f"\n⚠️ {msg}", "warn")
                self.status_var.set(msg)
            except Exception as e:
                self._log(f"\n❌ 异常: {e}", "error")
            finally:
                self.after(0, lambda: self._set_running(False))

        threading.Thread(target=worker, daemon=True).start()

    def _clean_empty(self):
        target = self._get_target()
        if not target:
            return
        self._clear_log()
        self._set_running(True)
        self.status_var.set("扫描空文件夹...")

        def worker():
            try:
                self._log(f"🔍 扫描空文件夹: {target}", "accent")
                empty = _find_empty_dirs_recursive(target)
                if not empty:
                    self._log("✅ 未发现空文件夹", "success")
                    self.after(0, lambda: self._set_running(False))
                    return

                self._log(f"📂 发现 {len(empty)} 个空文件夹:", "warn")
                for d in empty:
                    self._log(f"   {d.relative_to(target)}/")

                self.after(0, lambda: self.status_var.set(f"发现 {len(empty)} 个空文件夹，确认删除？"))

                # 弹窗确认
                confirm = messagebox.askyesno(
                    "确认删除",
                    f"发现 {len(empty)} 个空文件夹，确定删除？\n\n"
                    + "\n".join(str(d.relative_to(target)) + "/" for d in empty[:15])
                    + ("\n..." if len(empty) > 15 else "")
                )
                if confirm:
                    deleted = 0
                    for d in sorted(empty, key=lambda p: len(p.parts), reverse=True):
                        try:
                            d.rmdir()
                            deleted += 1
                            self._log(f"   🗑️ {d.relative_to(target)}/", "dim")
                        except OSError as e:
                            self._log(f"   ❌ {d.relative_to(target)}/: {e}", "error")
                    self._log(f"\n✅ 删除 {deleted}/{len(empty)} 个空文件夹", "success")
                    self.after(0, lambda: self.status_var.set(f"清理 {deleted} 个空文件夹"))
                else:
                    self._log("已取消", "dim")
                    self.after(0, lambda: self.status_var.set("已取消"))
            except Exception as e:
                self._log(f"\n❌ 异常: {e}", "error")
            finally:
                self.after(0, lambda: self._set_running(False))

        threading.Thread(target=worker, daemon=True).start()


if __name__ == "__main__":
    app = App()
    app.mainloop()
