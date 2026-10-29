#!/usr/bin/env python3
"""Deterministic source curation and article relevance filters; no AI API."""
from __future__ import annotations
import re
import unicodedata
from urllib.parse import urlparse

# Small, intentionally curated default set. This is a reading-list policy, not
# a ranking of researchers or firms. New upstream sources stay pending.
APPROVED_SOURCE_IDS = {
    # Independent researchers and high-signal practitioner writing
    "lilian-weng", "jason-wei", "andrej-karpathy",
    "neel-nanda", "nelson-elhage", "chip-huyen", "eugene-yan",
    "tim-dettmers", "francois-chollet", "simon-willison", "hamel-husain",
    "swyx", "jan-leike", "gwern", "import-ai", "interconnects",
    "one-useful-thing", "ai-snake-oil",
    # Long-form AI interviews and engineering conversations
    "dwarkesh", "latent-space", "cognitive-revolution",
    # Frontier labs: research and engineering, not generic corporate news
    "openai-blog", "openai-developer", "anthropic-blog", "anthropic-engineering",
    "deepmind-blog", "google-research", "meta-ai", "huggingface", "qwen",
    # Research institutes and independent evaluation groups
    "bair", "cmu-ml", "mila", "epoch-ai", "metr", "apollo-research", "ai2",
    # Quant firm sources with actual insight/research/technology sections
    "jane-street", "xtx-markets", "citadel-securities", "two-sigma",
    "optiver", "imc", "sig", "drw", "man-group", "aqr",
    # Focused quantitative interviews
    "alpha-exchange", "flirting-with-models", "top-traders-unplugged",
}

# Quality labels are editorial monitoring tiers, not objective measures of truth.
CORE_SOURCE_IDS = {
    "lilian-weng", "andrej-karpathy", "francois-chollet", "simon-willison",
    "gwern", "import-ai", "interconnects", "ai-snake-oil", "one-useful-thing",
    "epoch-ai", "metr", "apollo-research", "openai-blog", "anthropic-blog",
    "anthropic-engineering", "deepmind-blog", "jane-street", "xtx-markets",
    "two-sigma", "man-group", "aqr", "dwarkesh", "latent-space",
    "alpha-exchange", "flirting-with-models",
}
SOURCE_QUALITY = {sid: ("core" if sid in CORE_SOURCE_IDS else "selected") for sid in APPROVED_SOURCE_IDS}

# The Qwen blog is English even though the original index row had Chinese notes.
LANGUAGE_OVERRIDES = {"qwen": "en"}

NON_LATIN_SCRIPT_RE = re.compile(
    r"[\u3400-\u4dbf\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af"
    r"\u0400-\u052f\u0590-\u05ff\u0600-\u06ff\u0e00-\u0e7f"
    r"\u0900-\u097f\u0980-\u09ff\u0a00-\u0a7f\u0b00-\u0b7f"
    r"\u0c00-\u0c7f\u0d00-\u0d7f]"
)

AI_TOPIC_RE = re.compile(
    r"\b(?:ai|artificial intelligence|agi|artificial general intelligence|rsi|"
    r"recursive self[- ]improvement|llms?|large language models?|language models?|"
    r"foundation models?|generative ai|deep learning|machine learning|neural networks?|"
    r"transformers?|reasoning|inference|fine[- ]tuning|alignment|interpretability|"
    r"prompt(?:ing)?|context engineering|agents?|agentic|harness(?:es)?|coding agents?|"
    r"ai coding|evals?|evaluations?|benchmarks?|reinforcement learning|rlhf|scaling laws?|"
    r"model weights|open[- ]weight|open source models?|tool use|mcp|model context protocol|"
    r"research automation|auto[- ]research|research workflows?|feature engineering|event[- ]driven|"
    r"research infrastructure|market data|distributed systems|distributed file systems?|intelligence explosion|"
    r"world models?|diffusion models?|multimodal|tokenization|synthetic data|distillation|"
    r"test[- ]time compute|constitutional ai|chain[- ]of[- ]thought|software engineering|"
    r"developer tools|coding workflows?|claude|gpt[- ]?\d|gemini|deepmind|anthropic|openai|"
    r"llama|qwen|mistral|hugging face|frontier models?|model behavior|model capabilities?|"
    r"agentic engineering|autonomous research|self[- ]improv(?:ement|ing)|model training|"
    r"training data|inference optimization|ai safety|alignment research|language model agents?)\b",
    re.IGNORECASE,
)

QUANT_TOPIC_RE = re.compile(
    r"\b(?:quant(?:itative)?|algorithmic trading|systematic investing|systematic trading|"
    r"market microstructure|order book|order flow|execution|market making|financial markets?|"
    r"hedge funds?|alpha research|factor investing|trading signals?|portfolio construction|"
    r"risk premia|futures|derivatives|options market|liquidity|price discovery|market impact|"
    r"high[- ]frequency|hft|statistical arbitrage|backtesting|factor research|quant research|"
    r"investment research|trading strategies|electronic trading|volatility|cross[- ]asset|"
    r"systematic strategies|financial data|trading technology)\b",
    re.IGNORECASE,
)

# Company feeds often mix research with recruiting, partnerships, events and PR.
LOW_SIGNAL_ANNOUNCEMENT_RE = re.compile(
    r"^(?:introducing|announcing|meet |now available|available now|launching|"
    r"we(?:'|’)re launching|new partnership|partnering with|customer story|"
    r"case study:|join us|register for|webinar:|event recap|careers at|"
    r"we are hiring|funding announcement|series [a-f]\b|press release:|"
    r"(?:general |public |media |important |customer )?notice\b|"
    r"(?:press|media) release\b)",
    re.IGNORECASE,
)
# Award, ranking and league-table announcements are PR rather than research.
LOW_SIGNAL_PR_RE = re.compile(
    r"\b(?:tops?|topped|wins?|won|ranked|award(?:ed|s)?|celebrates?|honou?r(?:ed|s)?)\b"
    r".{0,40}\b(?:ranking|rankings|award|awards|index|league table|poll|survey|list)\b",
    re.IGNORECASE,
)

# Navigation, directory and profile paths are never article pages, even when a
# sitemap lists them with a fresh lastmod date.
NON_ARTICLE_PATH_SEGMENTS = {
    "about", "about-us", "annuaire", "author", "authors", "careers", "category",
    "categories", "contact", "cookie", "cookies", "directory", "events", "faq",
    "faculty", "jobs", "leadership", "login", "members", "people", "person",
    "philanthropy", "press", "privacy", "privacy-policy", "search", "signin",
    "sign-in", "sitemap", "sponsorship", "sponsorships", "staff", "subscribe",
    "subscription", "tag", "tags", "team", "terms", "terms-of-service",
    "ventures",
}
# Dated slugs are the usual shape of a single-segment article URL.
SINGLE_SEGMENT_DATE_RE = re.compile(r"(?:^|[-_])(?:19|20)\d{2}(?:[-_]|$)")
PAGE_EXTENSION_RE = re.compile(r"\.(?:html?|php|aspx?|jsp)$")
ENGLISH_LOCALE_RE = re.compile(r"/(?:en|en-us|en-gb)(?:/|$)")


def article_url_state(url: str) -> str:
    """Classify a URL as 'non-article', 'article', or 'unclear'.

    'unclear' covers single-segment paths such as /flex-model-notes/, which are
    common article URLs on personal blogs and quant sites but are also how some
    sites expose section landing pages. Callers with HTML available must resolve
    'unclear' with page metadata; callers without HTML should keep the record.
    """
    parsed = urlparse(url or "")
    segments = [segment for segment in parsed.path.lower().strip("/").split("/") if segment]
    if not segments:
        return "non-article"
    if any(segment in NON_ARTICLE_PATH_SEGMENTS for segment in segments):
        return "non-article"
    last = PAGE_EXTENSION_RE.sub("", segments[-1])
    if last in NON_ARTICLE_PATH_SEGMENTS:
        return "non-article"
    if len(segments) == 1:
        return "article" if SINGLE_SEGMENT_DATE_RE.search(last) else "unclear"
    return "article"


def is_article_url(url: str) -> bool:
    """True unless the URL is clearly a site root, section index or profile page."""
    return article_url_state(url) != "non-article"


def article_title_key(title: str | None) -> str:
    """Normalized title used to collapse locale duplicates of the same page."""
    value = unicodedata.normalize("NFKC", title or "").casefold()
    value = re.sub(r"[^0-9a-z\u00c0-\u024f]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


TECHNICAL_ANNOUNCEMENT_RE = re.compile(
    r"\b(?:research|technical report|benchmark|evaluation|architecture|training|inference|"
    r"reasoning|safety|system card|model card|engineering|agent|coding|performance|"
    r"capabilities|open weights|weights|dataset|paper|researchers|scientific|"
    r"interpretability|alignment|red[- ]team|reproducib|latency|compiler|kernel|market structure|"
    r"market making|quant research|execution|trading systems|market data|liquidity|systematic|portfolio)\b",
    re.IGNORECASE,
)


def has_non_latin_script(text: str | None) -> bool:
    return bool(NON_LATIN_SCRIPT_RE.search(text or ""))


def is_english_title(title: str | None) -> bool:
    """Conservative script-based language gate; accented Latin letters are fine."""
    value = (title or "").strip()
    if not value or has_non_latin_script(value):
        return False
    letters = [ch for ch in value if ch.isalpha()]
    if not letters:
        return False
    latin_letters = sum("LATIN" in unicodedata.name(ch, "") for ch in letters)
    return latin_letters / len(letters) >= 0.80


def is_english_source(source: dict) -> bool:
    language = LANGUAGE_OVERRIDES.get(source.get("id"), source.get("language", "en"))
    return language == "en" and not has_non_latin_script(source.get("name", ""))


def is_relevant_article(source: dict, title: str | None, excerpt: str | None = "") -> bool:
    """Topic gate using only publisher title/excerpt; deliberately no LLM calls."""
    clean_title = (title or "").strip()
    if not is_english_title(clean_title) or not is_english_source(source):
        return False
    text = f"{clean_title} {excerpt or ''}"[:5000]
    category = source.get("category", "")
    if category == "quant-firm":
        # Quant-firm engineering posts (e.g. storage/ML infrastructure) can be
        # relevant even when the title does not mention trading explicitly.
        if not (QUANT_TOPIC_RE.search(text) or AI_TOPIC_RE.search(text)):
            return False
    elif category == "interviews":
        if not (AI_TOPIC_RE.search(text) or QUANT_TOPIC_RE.search(text)):
            return False
    else:
        if not AI_TOPIC_RE.search(text):
            return False

    # Avoid generic company PR unless the title/excerpt contains technical substance.
    if category in {"ai-company", "ai-engineering", "quant-firm"}:
        if (LOW_SIGNAL_ANNOUNCEMENT_RE.search(clean_title) or LOW_SIGNAL_PR_RE.search(clean_title)) \
                and not TECHNICAL_ANNOUNCEMENT_RE.search(text):
            return False
    return True


def apply_source_policy(sources: list[dict]) -> bool:
    """Enforce a strict allowlist; upstream discoveries never auto-enable.

    Manual sources must explicitly use source_index='manual' or 'user-added'.
    A curated source can be intentionally paused with enabled=false and
    review_status='paused'. Sources outside the allowlist become not-curated.
    """
    changed = False
    for source in sources:
        before = (source.get("language"), source.get("enabled"), source.get("review_status"), source.get("source_quality"))
        sid = source.get("id", "")
        if sid in LANGUAGE_OVERRIDES:
            source["language"] = LANGUAGE_OVERRIDES[sid]
        english = is_english_source(source)
        source_index = source.get("source_index")
        was_enabled = source.get("enabled", True) is not False
        status = source.get("review_status", "")

        if not english:
            source["enabled"] = False
            source["review_status"] = "language-filtered"
        elif sid in APPROVED_SOURCE_IDS:
            if not was_enabled and status in {"paused", "manual-paused"}:
                source["enabled"] = False
                source["review_status"] = "paused"
            else:
                source["enabled"] = True
                source["review_status"] = "approved"
        elif source_index in {"manual", "user-added"}:
            if was_enabled:
                source["enabled"] = True
                source["review_status"] = "approved"
            else:
                source["enabled"] = False
                source["review_status"] = "paused"
        else:
            source["enabled"] = False
            source["review_status"] = "pending" if source_index == "joeseesun/ai-blog-res" else "not-curated"

        source["source_quality"] = SOURCE_QUALITY.get(sid, "watchlist")
        after = (source.get("language"), source.get("enabled"), source.get("review_status"), source.get("source_quality"))
        if before != after:
            changed = True
    return changed
