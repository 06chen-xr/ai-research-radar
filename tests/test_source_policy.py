import unittest
from scripts.source_policy import (
    APPROVED_SOURCE_IDS,
    apply_source_policy,
    is_english_title,
    is_relevant_article,
)


class SourcePolicyTests(unittest.TestCase):
    def test_english_gate(self):
        self.assertTrue(is_english_title("Unsolicited Opinions on AGI, RSI and Financial Markets"))
        self.assertFalse(is_english_title("AI前沿研究观察"))

    def test_atlas_style_essay_is_relevant(self):
        source = {"id": "atlas-wang", "language": "en", "name": "Atlas Wang", "category": "ai-researcher"}
        self.assertTrue(is_relevant_article(source, "Unsolicited Opinions on AGI, RSI and Financial Markets"))

    def test_jane_street_feature_engineering_is_relevant(self):
        source = {"id": "jane-street", "language": "en", "name": "Jane Street", "category": "quant-firm"}
        self.assertTrue(is_relevant_article(source, "Flex Model: an event-driven feature engineering system"))

    def test_generic_company_pr_is_filtered(self):
        source = {"id": "openai-blog", "language": "en", "name": "OpenAI Research", "category": "ai-company"}
        self.assertFalse(is_relevant_article(source, "Announcing our new partnership"))
        self.assertTrue(is_relevant_article(source, "Introducing a new reasoning benchmark for frontier models"))

    def test_upstream_source_does_not_auto_enable(self):
        sources = [{"id": "unreviewed", "name": "Random Blog", "url": "https://example.com", "language": "en", "enabled": True, "review_status": "approved", "source_index": "joeseesun/ai-blog-res"}]
        apply_source_policy(sources)
        self.assertFalse(sources[0]["enabled"])
        self.assertEqual(sources[0]["review_status"], "pending")

    def test_curated_sources_are_enabled(self):
        sources = [{"id": sid, "name": sid, "language": "en", "enabled": True, "review_status": "approved"} for sid in APPROVED_SOURCE_IDS]
        apply_source_policy(sources)
        self.assertTrue(all(s["enabled"] and s["review_status"] == "approved" for s in sources))


if __name__ == "__main__":
    unittest.main()
