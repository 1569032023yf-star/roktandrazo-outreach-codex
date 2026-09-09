#!/usr/bin/env python3
"""Inventory 收敛 + Follow-up 模板统一 回归测试。

覆盖：
  1. 旧 Inventory 脚本已归档（根目录不存在，_archived_scripts/2026-08-07 含禁用标记）
  2. 生产 Inventory 模块无 SMTP 能力（源码断言：无 smtplib/sendmail/send_one）
  3. get_followup_email_for_lead 返回 Subject 以 "Re: " 开头、body_text 含固定文案、
     in_reply_to/references 等于 original_message_id、tracking 新 token 不等于首封 token

内存库 + mock，不真实发送任何 SMTP。
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVE_DIR = os.path.join(PROJECT_DIR, "_archived_scripts", "2026-08-07")

import bd_template

# ── 归档清单 ─────────────────────────────────────────────
ARCHIVED_SCRIPTS = [
    "push_to_30.py",
    "scale_to_30.py",
    "inventory_expansion_runner.py",
    "inventory_recovery_daemon.py",
]

# 生产模块：inventory_monitor_executor 由 bd_orchestrator stage_inventory 调用
PROD_INVENTORY_MODULES = [
    os.path.join(PROJECT_DIR, "inventory_monitor_executor.py"),
]


class TestInventoryArchival(unittest.TestCase):
    """旧 Inventory 脚本已归档且带禁用标记。"""

    def test_legacy_scripts_not_in_root(self):
        for name in ARCHIVED_SCRIPTS:
            self.assertFalse(
                os.path.exists(os.path.join(PROJECT_DIR, name)),
                f"{name} 不应存在于根目录",
            )

    def test_archived_scripts_have_disable_marker(self):
        for name in ARCHIVED_SCRIPTS:
            path = os.path.join(ARCHIVE_DIR, name)
            self.assertTrue(os.path.exists(path), f"{name} 应在 _archived_scripts/2026-08-07/")
            with open(path, "r", encoding="utf-8") as fh:
                head = fh.read(512)
            self.assertIn(
                'raise RuntimeError("LEGACY_INVENTORY_ARCHIVED: use inventory_monitor_executor")',
                head,
                f"{name} 文件头应含禁用标记",
            )

    def test_removed_inventory_recovery_loop_stays_absent(self):
        # 该旧共享库及其调用者均已从当前根目录移除；不得把备份副本恢复为活动代码。
        self.assertFalse(
            os.path.exists(os.path.join(PROJECT_DIR, "inventory_recovery_loop.py")),
            "inventory_recovery_loop.py 已退役，不应恢复到开发根目录",
        )

    def test_push_to_30_and_scale_to_30_absent_from_root(self):
        for name in ("push_to_30.py", "scale_to_30.py"):
            self.assertFalse(
                os.path.exists(os.path.join(PROJECT_DIR, name)),
                f"根目录不应再有 {name}",
            )


class TestInventoryNoSMTP(unittest.TestCase):
    """生产 Inventory 模块无 SMTP 能力。"""

    def test_inventory_modules_have_no_smtp_import(self):
        for path in PROD_INVENTORY_MODULES:
            self.assertTrue(os.path.exists(path), f"缺少模块 {path}")
            with open(path, "r", encoding="utf-8") as fh:
                src = fh.read()
            self.assertNotIn("smtplib", src, f"{path} 不应 import smtplib")
            self.assertNotIn("sendmail", src, f"{path} 不应出现 sendmail")
            self.assertNotIn("send_one", src, f"{path} 不应调用 send_one")

    def test_inventory_modules_declare_send_disabled(self):
        for path in PROD_INVENTORY_MODULES:
            with open(path, "r", encoding="utf-8") as fh:
                src = fh.read()
            self.assertIn(
                "SEND_ENABLED = False",
                src,
                f"{path} 应声明 SEND_ENABLED = False",
            )


class TestFollowupTemplate(unittest.TestCase):
    """Follow-up 模板统一断言。"""

    def test_followup_email_shape(self):
        lead = {
            "id": 42,
            "store_name": "Acme Toy Store",
            "email": "buyer@acme.example",
            "store_type": "toy_store",
        }
        original_subject = "Premium puzzles & card games for Acme Toy Store (Low MOQ / DDP)"
        original_message_id = "prod_42_plan123"
        first_token = "first_email_tracking_token_AAAA"

        # 首封 token 与 follow-up 传入的新 token 不同（mock 传入）
        followup_tracking = {
            "token": "followup_new_token_BBBB",
            "token_hash": "hash_BBBB",
            "tracking_message_id": "prod_42_followup_1",
            "pixel_html": '<img src="https://tracker.example/o/followup_new_token_BBBB.gif" />',
        }

        result = bd_template.get_followup_email_for_lead(
            lead,
            original_subject=original_subject,
            original_message_id=original_message_id,
            tracking=followup_tracking,
        )

        self.assertTrue(result["subject"].startswith("Re: "))
        self.assertEqual(result["subject"], f"Re: {original_subject}")
        self.assertIn("better understand what would be most useful", result["body_text"])
        self.assertEqual(result["in_reply_to"], original_message_id)
        self.assertEqual(result["references"], original_message_id)
        self.assertEqual(result["email_type"], "follow_up")
        # 新 tracking token 不复用首封 token
        self.assertNotEqual(result["tracking_token"], first_token)
        self.assertEqual(result["tracking_token"], followup_tracking["token"])
        self.assertEqual(result["tracking_token_hash"], followup_tracking["token_hash"])

    def test_followup_self_generated_token_when_no_tracking(self):
        # 未传 tracking 时，函数也应生成独立新 token，且不等于固定首封 token
        lead = {
            "id": 7,
            "store_name": "Beta Books",
            "email": "buyer@beta.example",
            "store_type": "bookstore",
        }
        first_token = "original_first_token_CCCC"
        result = bd_template.get_followup_email_for_lead(
            lead,
            original_subject="Custom Production & Procurement Support for Beta Books",
            original_message_id="prod_7_plan888",
        )
        self.assertNotEqual(result["tracking_token"], "")
        self.assertNotEqual(result["tracking_token"], first_token)
        self.assertTrue(result["subject"].startswith("Re: "))
        self.assertIn("better understand what would be most useful", result["body_text"])
        self.assertEqual(result["in_reply_to"], "prod_7_plan888")
        self.assertEqual(result["references"], "prod_7_plan888")

    def test_followup_v1_locked_stays_disabled(self):
        # 锁定模板状态不被改动（业务规则由系统配置控制）
        self.assertEqual(
            bd_template.get_template_status("follow_up_v1_locked"),
            "LOCKED_DISABLED",
        )

    def test_follow_up_enabled_is_env_driven(self):
        # FOLLOW_UP_ENABLED 不再永久硬编码在模板模块
        self.assertEqual(
            bd_template.FOLLOW_UP_ENABLED,
            os.environ.get("BD_FOLLOW_UP_ENABLED", "false").lower() == "true",
        )


if __name__ == "__main__":
    unittest.main()
