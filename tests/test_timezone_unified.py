#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一时间体系 + 心跳真实性回归测试（P6）。

覆盖：
1. bd_orchestrator.py 不再调用 now_cst / today_cst 旧辅助函数。
2. bd_execution_host_service.py 的 SEND_SCHEDULE stage 名 ⊆ orchestrator argparse choices。
3. daily_session.py 生产调度路径不含 naive datetime.now()（允许 datetime.now(ASIA_SH)）。
4. 全生产树除 bd_ops_poller.py / bounce_pipeline.py 外无 bd_ops_poller_status.json 写入者。
5. orchestrator argparse choices 精确等于既定集合。

实现基于源码字符串 / AST 静态检查，不 import 生产模块，避免副作用。
"""

import ast
import re
import unittest
import warnings
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent

# 允许写 bd_ops_poller_status.json 的唯二生产文件
POLLER_STATUS_WRITERS_ALLOWED = {"bd_ops_poller.py", "bounce_pipeline.py"}

# 全生产树扫描时排除的目录（tests / 归档 / 备份 / 数据等）
EXCLUDED_DIRS = {"tests", "_archived_scripts", "backup", "backups", "data",
                 "__pycache__", ".pytest_cache", ".workbuddy", ".wrangler",
                 "output", "logs"}

EXPECTED_CHOICES = ['morning', 'pre-send', 'outreach', 'post-send',
                    'inventory', 'end-of-day', 'status']


def _read(relative: str) -> str:
    """读取项目内文件，返回文本。"""
    return (PROJECT_DIR / relative).read_text(encoding="utf-8", errors="replace")


def _orchestrator_choices() -> list[str]:
    """从 bd_orchestrator.py 提取 --stage 的 argparse choices。"""
    src = _read("bd_orchestrator.py")
    m = re.search(r"choices=\[([^\]]*)\]", src)
    if not m:
        raise AssertionError("bd_orchestrator.py 中未找到 choices=[...]")
    return [c.strip().strip("'\"") for c in m.group(1).split(",") if c.strip()]


def _safe_parse(src: str):
    """解析源码；既有生产文件可能含无效转义（SyntaxWarning），静默之。"""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        return ast.parse(src)


def _send_schedule_stages() -> list[tuple[str, str]]:
    """从 bd_execution_host_service.py 提取 SEND_SCHEDULE 的 (stage, --stage 参数)。"""
    src = _read("bd_execution_host_service.py")
    tree = _safe_parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = node.targets
            if len(targets) == 1 and isinstance(targets[0], ast.Name) and targets[0].id == "SEND_SCHEDULE":
                if not isinstance(node.value, ast.List):
                    raise AssertionError("SEND_SCHEDULE 不是 list")
                rows = []
                for elt in node.value.elts:
                    if not isinstance(elt, ast.Dict):
                        continue
                    fields = {}
                    for k, v in zip(elt.keys, elt.values):
                        if isinstance(k, ast.Constant) and isinstance(k.value, str):
                            fields[k.value] = v
                    stage = fields.get("stage")
                    args = fields.get("args")
                    arg_stage = None
                    if isinstance(args, ast.List):
                        arg_list = [a.value for a in args.elts if isinstance(a, ast.Constant)]
                        if "--stage" in arg_list:
                            idx = arg_list.index("--stage")
                            if idx + 1 < len(arg_list):
                                arg_stage = arg_list[idx + 1]
                    rows.append((stage.value if isinstance(stage, ast.Constant) else None,
                                 arg_stage))
                return rows
    raise AssertionError("bd_execution_host_service.py 中未找到 SEND_SCHEDULE")


def _mentions_poller_status(expr) -> bool:
    """判断 AST 表达式是否引用 bd_ops_poller_status.json 路径。"""
    if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
        return "bd_ops_poller_status" in expr.value
    if isinstance(expr, (ast.Call, ast.BinOp, ast.Attribute)):
        return any(_mentions_poller_status(child) for child in ast.iter_child_nodes(expr))
    return False


def _file_writes_poller_status(path: Path) -> bool:
    """静态判断文件是否向 bd_ops_poller_status.json 写入（open w 模式）。"""
    src = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = _safe_parse(src)
    except SyntaxError:
        return False

    # 1) 收集所有绑定到该 JSON 路径的变量名
    status_vars: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            value = node.value
            if _mentions_poller_status(value):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        status_vars.add(t.id)

    # 2) 检查 open(..., "w") 是否指向该文件（直接路径或已绑定变量）
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "open":
            if len(node.args) < 2:
                continue
            target, mode = node.args[0], node.args[1]
            is_poller = False
            if isinstance(target, ast.Constant) and isinstance(target.value, str):
                is_poller = "bd_ops_poller_status" in target.value
            elif isinstance(target, ast.Name) and target.id in status_vars:
                is_poller = True
            if is_poller and isinstance(mode, ast.Constant) and isinstance(mode.value, str) and "w" in mode.value:
                return True
    return False


def _production_py_files() -> list[Path]:
    """列出全生产树的 .py 文件（排除 tests / 归档 / 备份 / 数据等目录）。"""
    files = []
    for path in sorted(PROJECT_DIR.rglob("*.py")):
        rel = path.relative_to(PROJECT_DIR)
        if any(part in EXCLUDED_DIRS for part in rel.parts):
            continue
        files.append(path)
    return files


class TestTimezoneUnified(unittest.TestCase):

    def test_orchestrator_no_legacy_cst_refs(self):
        """bd_orchestrator.py 不含 now_cst / today_cst 旧辅助函数。"""
        src = _read("bd_orchestrator.py")
        for token in ("now_cst", "today_cst"):
            self.assertNotIn(token, src, f"bd_orchestrator.py 仍包含 {token}")
        # 新命名应存在
        self.assertIn("now_shanghai", src)
        self.assertIn("business_date_shanghai", src)
        self.assertIn("ASIA_SH", src)

    def test_send_schedule_stages_subset_of_choices(self):
        """SEND_SCHEDULE 的 stage 名 ⊆ orchestrator argparse choices。"""
        choices = set(_orchestrator_choices())
        rows = _send_schedule_stages()
        self.assertTrue(rows, "SEND_SCHEDULE 为空或未解析到条目")
        for stage, arg_stage in rows:
            self.assertIsNotNone(stage, "SEND_SCHEDULE 存在缺失 stage 字段的条目")
            self.assertIn(stage, choices,
                          f"SEND_SCHEDULE stage '{stage}' 不在 orchestrator choices 中")
            self.assertEqual(stage, arg_stage,
                             f"SEND_SCHEDULE 中 stage='{stage}' 与 args --stage='{arg_stage}' 不一致")

    def test_daily_session_no_naive_now(self):
        """daily_session.py 生产调度路径不含 naive datetime.now()（允许带时区参数）。"""
        src = _read("daily_session.py")
        matches = re.findall(r"datetime\.now\s*\(\s*\)", src)
        self.assertEqual(matches, [], f"daily_session.py 存在 naive datetime.now(): {matches}")
        # 带时区形式应存在
        self.assertIn("datetime.now(ASIA_SH)", src)
        self.assertIn("ASIA_SH", src)

    def test_no_extra_poller_status_writers(self):
        """除 bd_ops_poller.py / bounce_pipeline.py 外，无其他生产文件写 bd_ops_poller_status.json。"""
        offenders = []
        for path in _production_py_files():
            if path.name in POLLER_STATUS_WRITERS_ALLOWED:
                continue
            if _file_writes_poller_status(path):
                offenders.append(str(path))
        self.assertEqual(offenders, [],
                         f"发现 bd_ops_poller_status.json 的额外写入者: {offenders}")

    def test_orchestrator_choices_exact(self):
        """orchestrator argparse choices 精确等于既定集合。"""
        self.assertEqual(_orchestrator_choices(), EXPECTED_CHOICES)


if __name__ == "__main__":
    unittest.main()
