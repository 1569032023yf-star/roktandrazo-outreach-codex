"""Offline evidence gate tests; all positive attestations below are fixtures only."""
from datetime import date
from pathlib import Path
import tempfile
import unittest

import v6_bestseller_evidence as e
import v6_outreach as v


class BestsellerEvidenceTests(unittest.TestCase):
    def fixture(self):
        return {'source_sha256': e.ORIGINAL_SHA256, 'capture_date_verified': True,
            'capture_date_reference': 'FIXTURE: not real capture evidence',
            'capture_date': '2026-09-18', 'platform': 'TikTok Shop',
            'category': 'Jigsaw Puzzles', 'rank': 1, 'product_identity_verified': True,
            'product_identity_reference': 'FIXTURE: not a real listing identity'}

    def test_original_is_byte_exact_and_lightweight(self):
        result = e.inspect_original()
        self.assertEqual(result['sha256'], e.ORIGINAL_SHA256)
        self.assertEqual(result['bytes'], 116989)
        self.assertGreater(result['width'], 100)
        self.assertGreater(result['height'], 100)

    def test_changed_image_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'altered.png'
            target.write_bytes(e.ASSET.read_bytes() + b'changed')
            with self.assertRaisesRegex(ValueError, 'BYTES_CHANGED'):
                e.inspect_original(target)

    def test_actual_receipt_is_not_approved_evidence(self):
        receipt = e.load_receipt()
        self.assertIsNone(receipt['capture_date'])
        self.assertFalse(receipt['approved_english_copy_received'])
        with self.assertRaisesRegex(ValueError, 'DATE_UNVERIFIED'):
            e.require_capture_evidence(receipt)
        self.assertNotIn(e.TEMPLATE_KEY, v.TEMPLATES)

    def test_date_source_and_product_all_required(self):
        for field, value, error in [('source_sha256', '0'*64, 'SOURCE_MISMATCH'),
            ('capture_date', '2026-10-20', 'IN_FUTURE'),
            ('capture_date', 'not a date', 'DATE_INVALID'),
            ('capture_date_reference', '', 'DATE_UNVERIFIED'),
            ('product_identity_reference', '', 'IDENTITY_UNVERIFIED')]:
            with self.subTest(field=field):
                record = self.fixture()
                record[field] = value
                with self.assertRaisesRegex(ValueError, error):
                    e.require_capture_evidence(record, today=date(2026, 10, 19))

    def test_scope_cannot_expand_to_platform_wide_or_current_rank(self):
        for field, value in [('platform', 'TikTok'), ('category', 'All categories'),
                             ('rank', 2), ('rank', True)]:
            record = self.fixture()
            record[field] = value
            with self.assertRaisesRegex(ValueError, 'SCOPE_MISMATCH'):
                e.require_capture_evidence(record)
        self.assertEqual(e.require_capture_evidence(self.fixture()), '2026-09-18')

    def test_retail_type_and_explicit_relevance_required(self):
        review = {'identity_verified': True, 'business_type_verified': True,
            'business_type': 'toy_store', 'product_fit_verified': True,
            'tiktok_product_relevance_verified': True,
            'tiktok_product_relevance_url': 'https://example.invalid/puzzles',
            'tiktok_product_relevance_reference': 'FIXTURE ONLY'}
        self.assertTrue(e.relevant_review(review))
        for field, value in [('business_type', 'gift_shop'), ('business_type', 'brand_owner'),
            ('tiktok_product_relevance_reference', ''), ('tiktok_product_relevance_verified', False),
            ('tiktok_product_relevance_url', 'http://example.invalid'), ('identity_verified', False)]:
            candidate = dict(review, **{field: value})
            self.assertFalse(e.relevant_review(candidate))


if __name__ == '__main__':
    unittest.main()
