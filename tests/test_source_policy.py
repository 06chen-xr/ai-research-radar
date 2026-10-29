import unittest
from scripts.source_policy import (
    APPROVED_SOURCE_IDS,
    apply_source_policy,
    article_title_key,
    article_url_state,
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

    def test_quant_award_and_notice_pr_is_filtered(self):
        source = {"id": "xtx-markets", "language": "en", "name": "XTX Markets", "category": "quant-firm"}
        self.assertFalse(is_relevant_article(source, "Two Sigma Tops Hedge Fund Ranking"))
        self.assertFalse(is_relevant_article(source, "Notice regarding electronic trading platform changes"))
        self.assertTrue(is_relevant_article(source, "Flex Model: an event-driven feature engineering system"))

    def test_site_root_and_section_pages_are_not_articles(self):
        self.assertEqual(article_url_state("https://www.optiver.com/"), "non-article")
        self.assertEqual(article_url_state("https://www.xtxmarkets.com/philanthropy/"), "non-article")
        self.assertEqual(article_url_state("https://www.anthropic.com/threat-intelligence"), "unclear")
        self.assertEqual(article_url_state("https://mila.quebec/en/directory/isabeau-premont-schwarz"), "non-article")
        self.assertEqual(article_url_state("https://mila.quebec/fr/annuaire/isabeau-premont-schwarz"), "non-article")
        self.assertEqual(article_url_state("https://example.com/tag/agents/"), "non-article")
        self.assertEqual(article_url_state("https://eugeneyan.com/writing/"), "non-article")
        self.assertEqual(article_url_state("https://example.com/index.html"), "non-article")
        self.assertEqual(article_url_state("https://www.xtxmarkets.com/news/2026-trading-update/"), "article")

    def test_article_paths_stay_collectable(self):
        self.assertEqual(article_url_state("https://blog.janestreet.com/flex-model/"), "unclear")
        self.assertEqual(article_url_state("https://openai.com/index/retell-ai"), "article")
        self.assertEqual(article_url_state("https://simonwillison.net/2026/Oct/28/github-octoverse/"), "article")
        self.assertEqual(article_url_state("https://example.com/blog/2025-04-12-post/"), "article")

    def test_title_key_collapses_locale_duplicates(self):
        self.assertEqual(
            article_title_key("Isabeau Prémont-Schwarz | Mila"),
            article_title_key("isabeau prémonT-schwarz  |  mila"),
        )
        self.assertNotEqual(article_title_key("How Agents Decide"), article_title_key("A World Model of Life"))

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
