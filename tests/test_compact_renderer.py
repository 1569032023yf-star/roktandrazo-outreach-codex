"""P0 邮件排版恢复：紧凑渲染器回归测试（纯内存逻辑，不碰生产 DB）。

覆盖：
  - 两套锁定模板渲染后 content SHA 不变（ccb51505 / 5893dbc9）
  - 无 3+ 连续换行；正文→署名、署名→退订各恰 1 空行
  - tracking pixel 计数 <= 1；追踪开启时 HTML 恰 1 个、sender-copy 0 个
  - 无禁用 CSS 属性（flex/space-between/margin-top:auto/绝对定位/固定 height）
  - renderer_version='email_html_compact_v1'、renderer_sha256 非空且稳定
"""
from __future__ import annotations

import os
import re
import sys
import unittest

# 必须在 import bd_template 之前设置（TRACKING_PEPPER 在模块加载时读取）
os.environ.setdefault("BD_TRACKING_PEPPER", "test-pepper-for-unittest-only")

# 兼容两种运行方式：直接脚本（python tests/test_compact_renderer.py）或 -m unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bd_template import (
    RENDERER_SHA256,
    RENDERER_VERSION,
    TRACKING_BASE_URL,
    _TEMPLATE_SHA256,
    _compact_render,
    _compute_renderer_hash,
    apply_email_to_lead,
    get_email_for_lead,
    prepare_tracking_for_lead,
)

RETAIL_KEY = "retail_distributor_v5_locked"
CUSTOM_KEY = "custom_printing_production_v5_locked"
RETAIL_SHA = "ccb51505"
CUSTOM_SHA = "5893dbc9"

# tracking pixel 的 src 特征（与 PIXEL_HTML 的 URL 前缀一致）
_PIXEL_FEATURE = f"{TRACKING_BASE_URL}/o/"

# 禁用 CSS 属性：HTML 结构不得依赖 flexbox/绝对定位/固定高度
_FORBIDDEN_CSS = ("space-between", "margin-top:auto", "position:absolute", "position:fixed", "height:")


def _make_lead(store_name: str, store_type: str) -> dict:
    return {
        "id": 1,
        "store_name": store_name,
        "store_type": store_type,
        "email": "sales@example.com",
    }


class CompactRendererTests(unittest.TestCase):
    def setUp(self):
        # P7 secret 环境化后 TRACKING_PEPPER fail-closed；测试环境显式设置（仅测试用，非生产默认）
        os.environ.setdefault("BD_TRACKING_PEPPER", "test-pepper-for-unittest-only")
        # (标签, lead, template_key, 期望 SHA, 正文末句片段)
        self.leads = [
            ("retail", _make_lead("Grand Adventures Comics", "game_store"), RETAIL_KEY, RETAIL_SHA, "as well."),
            ("custom", _make_lead("The Crown Shop", "gift_shop"), CUSTOM_KEY, CUSTOM_SHA, "work."),
        ]

    def test_template_content_sha_unchanged(self):
        # 内容锁定约束：三个原始常量不变则 SHA 不变
        self.assertEqual(_TEMPLATE_SHA256[RETAIL_KEY], RETAIL_SHA)
        self.assertEqual(_TEMPLATE_SHA256[CUSTOM_KEY], CUSTOM_SHA)
        for _, lead, key, expected_sha, _tail in self.leads:
            data = get_email_for_lead(lead, template_key=key)
            self.assertEqual(data["template_sha256"], expected_sha)
            self.assertEqual(data["content_sha256"], expected_sha)
            self.assertEqual(data["content_sha256"], data["template_sha256"])

    def test_no_three_plus_newline_runs(self):
        for _, lead, key, _sha, _tail in self.leads:
            data = get_email_for_lead(lead, template_key=key)
            self.assertFalse(re.findall(r"\n{3,}", data["body_text"]))
            self.assertFalse(re.findall(r"\n{3,}", data["body_html"]))
            self.assertFalse(re.findall(r"\n{3,}", data["body_html_no_pixel"]))

    def test_one_blank_line_before_signature_and_unsub(self):
        for _, lead, key, _sha, body_tail in self.leads:
            data = get_email_for_lead(lead, template_key=key)
            text = data["body_text"]
            # 正文→署名：恰 1 空行
            self.assertIn(f"{body_tail}\n\nIan\nBusiness", text)
            # 署名→退订：恰 1 空行
            self.assertIn("roktandrazo.com\n\nIf this isn't relevant", text)
            # 无连续 4 空行（大空白根因回归）
            self.assertNotIn("\n\n\n\n", text)

    def test_pixel_count_at_most_one(self):
        for _, lead, key, _sha, _tail in self.leads:
            # 追踪关闭：0 个 pixel（<=1 满足）
            off = get_email_for_lead(lead, template_key=key)
            self.assertFalse(off["has_pixel"])
            self.assertLessEqual(off["body_html"].count(_PIXEL_FEATURE), 1)
            # 追踪开启：恰好 1 个 pixel，sender-copy 无 pixel
            tracking = prepare_tracking_for_lead(lead, "plan-test")
            on = get_email_for_lead(lead, template_key=key, tracking=tracking)
            self.assertTrue(on["has_pixel"])
            self.assertEqual(on["body_html"].count(_PIXEL_FEATURE), 1)
            self.assertEqual(on["body_html_no_pixel"].count(_PIXEL_FEATURE), 0)

    def test_no_forbidden_css_properties(self):
        for _, lead, key, _sha, _tail in self.leads:
            data = get_email_for_lead(lead, template_key=key)
            html = data["body_html"].lower()
            self.assertFalse(re.search(r"\bflex\b", html))  # 不误伤 flexible 等单词
            for css in _FORBIDDEN_CSS:
                self.assertNotIn(css, html)

    def test_renderer_metadata(self):
        self.assertEqual(RENDERER_VERSION, "email_html_compact_v1")
        self.assertTrue(RENDERER_SHA256)
        self.assertEqual(len(RENDERER_SHA256), 8)
        for _, lead, key, _sha, _tail in self.leads:
            data = get_email_for_lead(lead, template_key=key)
            self.assertEqual(data["renderer_version"], RENDERER_VERSION)
            self.assertEqual(data["renderer_sha256"], RENDERER_SHA256)

    def test_renderer_hash_stable(self):
        # 同一解释器内多次计算必须一致（渲染器实现变化时才应改变指纹）
        self.assertEqual(_compute_renderer_hash(), RENDERER_SHA256)
        self.assertEqual(_compute_renderer_hash(), _compute_renderer_hash())

    def test_compact_render_rejects_duplicate_pixels(self):
        html = f"<p>hi</p>\n<p><img src='{TRACKING_BASE_URL}/o/a.gif' /></p>"
        _text, out_html = _compact_render("hi\n\n\nIan", html)
        self.assertIn(TRACKING_BASE_URL, out_html)
        # 双 pixel 必须拒绝
        dup = html + f"<p><img src='{TRACKING_BASE_URL}/o/b.gif' /></p>"
        with self.assertRaises(ValueError):
            _compact_render("hi", dup)

    def test_apply_email_to_lead_propagates_metadata(self):
        lead = _make_lead("Grand Adventures Comics", "game_store")
        apply_email_to_lead(lead)
        self.assertEqual(lead["template_key"], RETAIL_KEY)
        self.assertEqual(lead["content_sha256"], RETAIL_SHA)
        self.assertEqual(lead["renderer_version"], RENDERER_VERSION)
        self.assertEqual(lead["renderer_sha256"], RENDERER_SHA256)


if __name__ == "__main__":
    unittest.main()
