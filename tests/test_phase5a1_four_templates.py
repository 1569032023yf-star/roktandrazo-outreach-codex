"""Offline four-template routing, evidence, FSP content and MIME acceptance tests."""
from email import message_from_string
from unittest.mock import patch
import unittest

from test_phase5a_v6 import policy, lead
import v6_outreach as v
import v6_bestseller_evidence as e


def evidence():
    return {'source_sha256': e.ORIGINAL_SHA256, 'capture_date': '2026-09-18',
        'capture_date_verified': True, 'capture_date_reference': 'FIXTURE ONLY',
        'platform': 'TikTok Shop', 'platform_verified': True, 'platform_reference': 'FIXTURE ONLY',
        'category': 'Jigsaw Puzzles', 'rank': 1, 'product_identity_verified': True,
        'product_identity_reference': 'FIXTURE ONLY'}


class FourTemplateTests(unittest.TestCase):
    def setUp(self):
        self.p = policy()
        self.d = lead(self.p, email='info@example.invalid')
        self.p['tiktok_ranking_evidence'] = evidence()
        self.review = self.p['reviewed_leads']['1']
        self.review.update(tiktok_product_relevance_verified=True,
            tiktok_product_relevance_url='https://example.invalid/puzzles',
            tiktok_product_relevance_reference='FIXTURE ONLY')

    def test_four_registry_entries_and_locks(self):
        import bd_template
        self.assertEqual(len(v.TEMPLATES), 4)
        for key in v.TEMPLATES:
            self.assertEqual(v.canonical_hash(key), v.LOCKED_SHA256[key])
            self.assertEqual(bd_template._TEMPLATE_REGISTRY[key]['status'], 'ACTIVE_LOCKED')
        self.assertNotIn('DDP', v.TEMPLATES[v.RETAIL][1])
        self.assertNotIn('low minimum', v.TEMPLATES[v.RETAIL][1])
        self.assertNotIn('samples', v.TEMPLATES[v.RETAIL][1])

    def test_relevant_info_retail_prefers_tiktok(self):
        self.assertEqual(v.route(self.d, self.p), v.TIKTOK)

    def test_missing_relevance_or_evidence_falls_back(self):
        self.review['tiktok_product_relevance_verified'] = False
        self.assertEqual(v.route(self.d, self.p), v.RETAIL)
        self.review['tiktok_product_relevance_verified'] = True
        self.p['tiktok_ranking_evidence']['capture_date_verified'] = False
        self.assertEqual(v.route(self.d, self.p), v.RETAIL)

    def test_brand_info_not_referral_or_tiktok(self):
        self.review['business_type'] = 'puzzle_brand'
        self.assertEqual(v.route(self.d, self.p), v.CUSTOM)
        self.review.update(business_type='unknown', business_type_verified=False)
        self.assertEqual(v.route(self.d, self.p), v.REFERRAL)

    def test_override_cannot_bypass_evidence(self):
        self.d['template_override'] = v.TIKTOK
        self.review['approved_template_override'] = v.TIKTOK
        self.review['tiktok_product_relevance_verified'] = False
        with self.assertRaisesRegex(ValueError, 'RELEVANCE'):
            v.render(self.d, self.p)

    def test_date_and_original_hash_frozen_into_both_versions(self):
        item = v.render(self.d, self.p)
        self.assertIn('2026-09-18', item['body_text'])
        self.assertIn('Historical category ranking only', item['body_text'])
        self.assertIn('2026-09-18', item['body_html'])
        self.assertIn('cid:' + e.CID, item['body_html'])
        self.assertNotRegex(item['body_html'], r'https?://|width="1"')
        self.assertEqual(v.validate_message(item, self.d, self.p), item)
        self.p['tiktok_ranking_evidence']['capture_date'] = '2026-09-19'
        with self.assertRaisesRegex(ValueError, 'FROZEN_CONTENT'):
            v.validate_message(item, self.d, self.p)

    def test_new_four_template_qa_gate_required(self):
        import send_resumption as s
        self.p['evidence']['v6_three_template_test'] = self.p['evidence'].pop('v6_four_template_test')
        with self.assertRaisesRegex(ValueError, 'v6_four_template_test'):
            s.require_ready(self.p)

    def test_candidate_internal_is_pending_no_image_no_postal(self):
        p = {'internal_test_only': True, 'controlled_test_recipients': ['qa@example.invalid'],
            'test_ownership_reference': 'FIXTURE ONLY'}
        item = v.render_internal_test(v.TIKTOK, 'qa@example.invalid', p)
        self.assertIn('RANKING CLAIM PENDING VERIFICATION', item['body_text'])
        self.assertNotIn('<img', item['body_html'])
        self.assertNotIn('Business mailing address:', item['body_text'])

    def test_cid_mime_uses_original_bytes_no_tracking(self):
        import bd_sender
        item = v.render(self.d, self.p)
        with patch.object(bd_sender, 'get_sender_info', return_value={'name':'QA','email':'sender@example.invalid'}):
            msg = bd_sender._build_email('qa@example.invalid', item['subject'], item['body_text'], item['body_html'])
        e.attach_verified_cid(msg, item['body_html'], self.p['tiktok_ranking_evidence'])
        parsed = message_from_string(msg.as_string())
        parts = list(parsed.walk())
        image = [part for part in parts if part.get_content_type() == 'image/png']
        self.assertEqual(len(image), 1)
        self.assertEqual(image[0].get_payload(decode=True), e.ASSET.read_bytes())
        self.assertEqual(image[0]['Content-ID'], '<' + e.CID + '>')
        self.assertEqual(image[0].get_content_disposition(), 'inline')
        self.assertTrue(any(part.get_content_type() == 'text/plain' for part in parts))
        self.assertEqual(parsed['Reply-To'], 'sender@example.invalid')
        with self.assertRaisesRegex(ValueError, 'DATE_UNVERIFIED'):
            e.attach_verified_cid(msg, item['body_html'], dict(evidence(), capture_date_verified=False))

    def test_attachments_and_unapproved_inline_content_blocked(self):
        item = v.render(self.d, self.p)
        for field in ('attachments', 'inline_images', 'pixel_tracking'):
            with self.assertRaisesRegex(ValueError, 'FORBIDDEN'):
                v.validate_message(dict(item, **{field: ['unexpected']}), self.d, self.p)


if __name__ == '__main__':
    unittest.main()
