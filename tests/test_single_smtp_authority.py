#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P3 唯一 SMTP 权威静态测试
========================
生产收敛后，唯一允许真实客户 SMTP 的文件是 bd_sender.py。
其他生产代码禁止 import smtplib / 创建 SMTP_SSL / sendmail / send_message；
若旧文件仍含相关引用，则必须 fail-closed（含禁用标记，无法真正发送）。

本套件不依赖外部命令，纯 os.walk + 读文件实现；扫描结果带缓存，避免重复读盘。
"""
import os
import re
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 生产树排除目录（与 P3 规格一致）
EXCLUDED_DIRS = {
    "tests",
    "_archived_scripts",
    "backup",
    "backups",
    "data",
    ".workbuddy",
    "workbuddy_candidate_modules",
    "output",
    "migrations",
    "cloudflare",
    "__pycache__",
}

# 测试 1：smtplib 相关引用模式
_SMTP_PATTERNS = [
    ("import smtplib", re.compile(r"\bimport\s+smtplib\b")),
    ("from smtplib", re.compile(r"\bfrom\s+smtplib\b")),
    ("SMTP_SSL(", re.compile(r"SMTP_SSL\s*\(")),
    ("smtplib.SMTP", re.compile(r"smtplib\.SMTP\b")),
]

# 测试 2：发送调用模式
_SEND_PATTERNS = [
    ("sendmail(", re.compile(r"\bsendmail\s*\(")),
    (".send_message(", re.compile(r"\.send_message\s*\(")),
]

# 测试 4：SEND_LIVE = True
_SEND_LIVE_RE = re.compile(r"SEND_LIVE\s*=\s*True")

# 测试 3：根目录"已归档定时发送脚本"命名模式（对应规格枚举：
#   _send_*.py / _preflight_*.py / _prepare_*.py / _run_*pilot*.py
#   / _catchup*.py / *_20260*.py）
# 注意：final_send_plan.py / post_send_reconciliation.py 是正式模块，
#   以 final/post 开头，不会被 ^_ 前缀模式命中，额外再加一道保险。
DATED_SEND_PATTERNS = [
    re.compile(r"^_send"),
    re.compile(r"^_preflight"),
    re.compile(r"^_prepare"),
    re.compile(r"^_run_.*pilot"),
    re.compile(r"^_catchup"),
    re.compile(r"_20260"),
]

# fail-closed 禁用标记：
#   1) 显式字符串 LEGACY_SMTP_DISABLED / LEGACY_LIVE_DISABLED
#   2) raise RuntimeError（规格指定的禁用标记）
#   3) raise <xxx>Disabled<xxx>Error（代码库实际使用的硬禁用，
#      如 sender.py 的 raise LegacySMTPDisabledError，导入即抛，fail-closed）
_FAIL_CLOSED_STRINGS = (
    "LEGACY_SMTP_DISABLED", "LEGACY_LIVE_DISABLED", "raise RuntimeError",
    "DEVELOPMENT_EXTERNAL_TRANSPORT_DISABLED",
)
_HARD_DISABLE_RAISE = re.compile(r"raise\s+[A-Za-z_]\w*Disabled\w*Error")

ARCHIVE_DIR = os.path.join(PROJECT_ROOT, "_archived_scripts", "2026-08-07")


def _has_fail_closed_marker(content):
    """判断文件内容是否携带 fail-closed 禁用标记。"""
    if any(m in content for m in _FAIL_CLOSED_STRINGS):
        return True
    return _HARD_DISABLE_RAISE.search(content) is not None


_SCAN_CACHE = None


def _iter_production_files():
    """惰性扫描生产树（排除目录见 EXCLUDED_DIRS），返回 {绝对路径: 文件内容}。"""
    global _SCAN_CACHE
    if _SCAN_CACHE is None:
        files = {}
        for dirpath, dirnames, filenames in os.walk(PROJECT_ROOT):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]
            for fn in filenames:
                if not fn.endswith(".py"):
                    continue
                path = os.path.join(dirpath, fn)
                try:
                    with open(path, "r", encoding="utf-8", errors="replace") as f:
                        files[path] = f.read()
                except OSError:
                    continue
        _SCAN_CACHE = files
    return _SCAN_CACHE


def _find_pattern_hits(content, patterns):
    """行级正则匹配，忽略空行与纯注释行，返回 [(行号, 模式名, 原文), ...]。"""
    hits = []
    for lineno, line in enumerate(content.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        for name, rx in patterns:
            if rx.search(line):
                hits.append((lineno, name, line.strip()[:120]))
    return hits


def _print_hit_report(title, all_hits):
    """打印命中清单（含是否带禁用标记），unittest 默认不缓冲 stdout，直接可见。"""
    if not all_hits:
        return
    print(f"\n[扫描结果] {title}")
    for rel in sorted(all_hits):
        content = _iter_production_files()[os.path.join(PROJECT_ROOT, rel)]
        marker = "有(fail-closed)" if _has_fail_closed_marker(content) else "无"
        print(f"  {rel}  [禁用标记: {marker}]")
        for lineno, name, line in all_hits[rel]:
            print(f"    - L{lineno}: {name} | {line}")


class TestSingleSmtpAuthority(unittest.TestCase):
    """唯一 SMTP 权威（bd_sender.py）静态约束测试。"""

    def test_only_bd_sender_imports_smtplib(self):
        """生产树中仅 bd_sender.py 可含 smtplib；其余命中必须 fail-closed。"""
        offenders, all_hits = [], {}
        for path, content in _iter_production_files().items():
            hits = _find_pattern_hits(content, _SMTP_PATTERNS)
            if not hits:
                continue
            rel = os.path.relpath(path, PROJECT_ROOT)
            all_hits[rel] = hits
            if os.path.basename(path) == "bd_sender.py":
                continue  # 唯一 SMTP 权威
            if _has_fail_closed_marker(content):
                continue  # 已 fail-closed，视为通过
            offenders.append(rel)
        _print_hit_report("smtplib / SMTP_SSL 命中清单（唯一权威：bd_sender.py）", all_hits)
        self.assertEqual([], offenders,
                         "以下生产文件含 smtplib 引用且无禁用标记（必须 fail-closed 或改用 bd_sender）: "
                         + ", ".join(offenders))

    def test_no_sendmail_in_production(self):
        """生产树中 sendmail() / .send_message() 仅允许 bd_sender.py；其余须 fail-closed。"""
        offenders, all_hits = [], {}
        for path, content in _iter_production_files().items():
            hits = _find_pattern_hits(content, _SEND_PATTERNS)
            if not hits:
                continue
            rel = os.path.relpath(path, PROJECT_ROOT)
            all_hits[rel] = hits
            if os.path.basename(path) == "bd_sender.py":
                continue
            if _has_fail_closed_marker(content):
                continue
            offenders.append(rel)
        _print_hit_report("sendmail / .send_message 命中清单（唯一权威：bd_sender.py）", all_hits)
        self.assertEqual([], offenders,
                         "以下生产文件含 sendmail/.send_message 调用且无禁用标记: "
                         + ", ".join(offenders))

    def test_no_dated_send_scripts_in_root(self):
        """根目录不得残留已归档的定时发送脚本。"""
        found = []
        for fn in sorted(os.listdir(PROJECT_ROOT)):
            if not fn.endswith(".py"):
                continue
            if fn.startswith("final") or fn.startswith("post"):
                continue  # final_send_plan.py / post_send_reconciliation.py 为正式模块
            if any(rx.search(fn) for rx in DATED_SEND_PATTERNS):
                found.append(fn)
        self.assertEqual([], found,
                         "根目录存在已归档的定时发送脚本（应移入 _archived_scripts/）: "
                         + ", ".join(found))

    def test_only_one_send_live(self):
        """生产树中不得出现 SEND_LIVE = True。"""
        hits = []
        for path, content in _iter_production_files().items():
            for lineno, line in enumerate(content.splitlines(), start=1):
                if _SEND_LIVE_RE.search(line):
                    hits.append(f"{os.path.relpath(path, PROJECT_ROOT)}:{lineno}")
        self.assertEqual([], hits, "生产树中发现 SEND_LIVE = True: " + ", ".join(hits))

    def test_archived_scripts_fail_closed(self):
        """_archived_scripts/2026-08-07/ 下每个 .py 前 20 行必须含禁用标记。"""
        missing = []
        for fn in sorted(os.listdir(ARCHIVE_DIR)):
            if not fn.endswith(".py"):
                continue
            path = os.path.join(ARCHIVE_DIR, fn)
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                head = "".join(f.readlines()[:20])
            if not _has_fail_closed_marker(head):
                missing.append(fn)
        self.assertEqual([], missing,
                         "以下归档脚本前 20 行缺少 LEGACY_SMTP_DISABLED / raise RuntimeError 禁用标记: "
                         + ", ".join(missing))


if __name__ == "__main__":
    unittest.main()
