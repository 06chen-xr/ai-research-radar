#!/usr/bin/env python3
"""Collect public blog entries without using an AI API.

Collection order: explicit/autodiscovered RSS or Atom, common feed paths,
then sitemap and a small number of article links from the source page.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse, parse_qsl, urlencode
from urllib.robotparser import RobotFileParser
import xml.etree.ElementTree as ET

import feedparser
import requests
from bs4 import BeautifulSoup

from source_policy import apply_source_policy, is_english_source, is_english_title, is_relevant_article

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SOURCES_PATH = DATA / "sources.json"
ARTICLES_PATH = DATA / "articles.json"
STATUS_PATH = DATA / "collector_status.json"
USER_AGENT = "QuantResearchRadarBot/0.1 (+https://github.com; polite public blog indexer)"
TIMEOUT = 8
MAX_FEED_ENTRIES = 30
MAX_SITEMAP_ARTICLES = 4
MAX_LINK_FALLBACK = 4
KEEP_DAYS = 365

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"})
_ROBOTS_CACHE = {}
_ROBOTS_TEXT_CACHE = {}
_ROBOTS_LOCK = threading.Lock()


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def date_only(value: str | None) -> str | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).date().isoformat()
    except (ValueError, TypeError):
        try:
            dt = parsedate_to_datetime(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).date().isoformat()
        except Exception:
            return None


def normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        return ""
    query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in {"ref", "source", "fbclid", "gclid"}]
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path, "", urlencode(query), ""))


def robots_allowed(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.path.lower().endswith("/robots.txt") or parsed.path.lower() == "robots.txt":
        return True
    origin = f"{parsed.scheme}://{parsed.netloc}"
    with _ROBOTS_LOCK:
        parser = _ROBOTS_CACHE.get(origin)
    if parser is None:
        parser = RobotFileParser()
        robots_url = origin + "/robots.txt"
        parser.set_url(robots_url)
        robots_text = ""
        try:
            response = session.get(robots_url, timeout=TIMEOUT, allow_redirects=True)
            if response.status_code in (401, 403):
                parser.parse(["User-agent: *", "Disallow: /"])
            elif response.status_code == 404:
                parser.parse([])
            elif response.status_code < 400:
                robots_text = response.text
                parser.parse(robots_text.splitlines())
            else:
                # A temporary robots.txt failure should not silently mark every source as blocked.
                parser.parse([])
        except requests.RequestException:
            parser.parse([])
        with _ROBOTS_LOCK:
            _ROBOTS_CACHE.setdefault(origin, parser)
            _ROBOTS_TEXT_CACHE.setdefault(origin, robots_text)
            parser = _ROBOTS_CACHE[origin]
    try:
        return parser.can_fetch(USER_AGENT, url)
    except Exception:
        return True


def fetch(url: str):
    if not robots_allowed(url):
        return None, "robots-disallowed"
    try:
        response = session.get(url, timeout=TIMEOUT, allow_redirects=True)
        if response.status_code >= 400:
            return None, f"HTTP {response.status_code}"
        return response, None
    except requests.RequestException as exc:
        return None, type(exc).__name__


def same_host(a: str, b: str) -> bool:
    try:
        host_a = urlparse(a).netloc.lower().removeprefix("www.")
        host_b = urlparse(b).netloc.lower().removeprefix("www.")
        return bool(host_a and host_b and (host_a == host_b or host_a.endswith("." + host_b) or host_b.endswith("." + host_a)))
    except Exception:
        return False


def article_record(source: dict, title: str, url: str, published_at: str | None, excerpt: str = "") -> dict | None:
    clean_url = normalize_url(url)
    clean_title = re.sub(r"\s+", " ", unescape(title or "")).strip()
    if not clean_url or not clean_title or len(clean_title) < 3:
        return None
    if not is_relevant_article(source, clean_title, excerpt):
        return None
    if clean_url.rstrip("/") == normalize_url(source["url"]).rstrip("/"):
        return None
    if clean_title.lower() in {"home", "homepage", "login", "sign in", "about", "contact", "privacy policy", "terms of service"}:
        return None
    pub = date_only(published_at)
    return {
        "id": hashlib.sha1(clean_url.encode("utf-8")).hexdigest()[:14],
        "title": clean_title[:300],
        "url": clean_url,
        "source_id": source["id"],
        "source_name": source["name"],
        "source_url": source["url"],
        "category": source["category"],
        "source_type": source["source_type"],
        "topics": source.get("topics", []),
        "tier": source.get("tier"),
        "source_quality": source.get("source_quality", "watchlist"),
        "language": source.get("language", "en"),
        "published_at": pub,
        "discovered_at": datetime.now(timezone.utc).date().isoformat(),
        # Publisher-provided excerpt only. No generated summary is produced.
        "excerpt": re.sub(r"\s+", " ", unescape(BeautifulSoup(excerpt or "", "html.parser").get_text(" "))).strip()[:500]
    }


def parse_feed(source: dict, feed_url: str) -> list[dict]:
    response, err = fetch(feed_url)
    if err or response is None:
        return []
    parsed = feedparser.parse(response.content)
    if not parsed.entries:
        return []
    found = []
    for entry in parsed.entries[:MAX_FEED_ENTRIES]:
        link = entry.get("link")
        title = entry.get("title", "")
        if not link:
            continue
        published = None
        for key in ("published_parsed", "updated_parsed", "created_parsed"):
            value = entry.get(key)
            if value:
                try:
                    published = datetime(*value[:6], tzinfo=timezone.utc).isoformat()
                    break
                except Exception:
                    pass
        if not published:
            published = entry.get("published") or entry.get("updated")
        record = article_record(source, title, urljoin(feed_url, link), published, entry.get("summary", ""))
        if record:
            found.append(record)
    return found


def discover_feed(source: dict, homepage_html: bytes | None = None) -> str | None:
    if source.get("feed_url"):
        return source["feed_url"]
    base = source["url"].rstrip("/")
    response = None
    if homepage_html is None:
        response, _ = fetch(source["url"])
        homepage_html = response.content if response is not None else None
    if homepage_html:
        soup = BeautifulSoup(homepage_html, "html.parser")
        for tag in soup.find_all("link", href=True):
            rel = " ".join(tag.get("rel", [])).lower()
            typ = (tag.get("type") or "").lower()
            if "alternate" in rel and ("rss" in typ or "atom" in typ or "xml" in typ):
                return urljoin(source["url"], tag["href"])
    parsed = urlparse(source["url"])
    origin = f"{parsed.scheme}://{parsed.netloc}"
    candidates = [base + "/feed.xml", base + "/rss.xml", origin + "/feed.xml"]
    for candidate in dict.fromkeys(candidates):
        response, _ = fetch(candidate)
        if response is None:
            continue
        ctype = response.headers.get("content-type", "").lower()
        if "xml" in ctype or response.text.lstrip().startswith(("<?xml", "<rss", "<feed")):
            parsed_feed = feedparser.parse(response.content)
            if parsed_feed.entries:
                return candidate
    return None


def parse_html_article(url: str, source: dict, fallback_title: str = "", sitemap_date: str | None = None) -> dict | None:
    response, _ = fetch(url)
    if response is None or "html" not in response.headers.get("content-type", "text/html").lower():
        return None
    soup = BeautifulSoup(response.text, "html.parser")
    title = ""
    for selector in [("meta", {"property": "og:title"}), ("meta", {"name": "twitter:title"})]:
        node = soup.find(*selector)
        if node and node.get("content"):
            title = node["content"].strip()
            break
    if not title and soup.title:
        title = soup.title.get_text(" ", strip=True)
    if not title:
        title = fallback_title
    published = None
    date_selectors = [
        ("meta", {"property": "article:published_time"}),
        ("meta", {"property": "og:published_time"}),
        ("meta", {"name": "date"}),
        ("meta", {"name": "publish-date"}),
        ("meta", {"name": "pubdate"}),
    ]
    for selector in date_selectors:
        node = soup.find(*selector)
        if node and node.get("content"):
            published = node["content"]
            break
    if not published:
        time_node = soup.find("time", attrs={"datetime": True})
        if time_node:
            published = time_node.get("datetime")
    if not published:
        for node in soup.find_all("script", attrs={"type": "application/ld+json"})[:5]:
            try:
                data = json.loads(node.string or node.get_text())
                candidates = data if isinstance(data, list) else [data]
                for obj in candidates:
                    if isinstance(obj, dict):
                        published = obj.get("datePublished") or obj.get("dateCreated") or obj.get("dateModified")
                        if published:
                            break
                if published:
                    break
            except Exception:
                continue
    if not published:
        published = sitemap_date
    description = ""
    for selector in [("meta", {"name": "description"}), ("meta", {"property": "og:description"})]:
        node = soup.find(*selector)
        if node and node.get("content"):
            description = node["content"]
            break
    return article_record(source, title, response.url, published, description)


def parse_sitemap(source: dict) -> list[dict]:
    parsed = urlparse(source["url"])
    origin = f"{parsed.scheme}://{parsed.netloc}"
    sitemap_urls = []
    robots_text = _ROBOTS_TEXT_CACHE.get(origin, "")
    for line in robots_text.splitlines():
        if line.lower().startswith("sitemap:"):
            sitemap_urls.append(line.split(":", 1)[1].strip())
    sitemap_urls.extend([origin + "/sitemap.xml", origin + "/sitemap_index.xml"])
    locs = []
    seen_maps = set()
    for sm_url in dict.fromkeys(sitemap_urls):
        if sm_url in seen_maps:
            continue
        seen_maps.add(sm_url)
        response, _ = fetch(sm_url)
        if response is None:
            continue
        try:
            root = ET.fromstring(response.content)
        except ET.ParseError:
            continue
        namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        if root.tag.endswith("sitemapindex"):
            child_maps = [x.text for x in root.findall(".//sm:sitemap/sm:loc", namespace) if x.text]
            for child in child_maps[:2]:
                child_resp, _ = fetch(child)
                if child_resp is None:
                    continue
                try:
                    child_root = ET.fromstring(child_resp.content)
                except ET.ParseError:
                    continue
                for item in child_root.findall(".//sm:url", namespace):
                    loc = item.findtext("sm:loc", default="", namespaces=namespace)
                    lastmod = item.findtext("sm:lastmod", default="", namespaces=namespace)
                    if loc and same_host(loc, source["url"]):
                        locs.append((loc, date_only(lastmod)))
            if locs:
                break
        else:
            for item in root.findall(".//sm:url", namespace):
                loc = item.findtext("sm:loc", default="", namespaces=namespace)
                lastmod = item.findtext("sm:lastmod", default="", namespaces=namespace)
                if loc and same_host(loc, source["url"]):
                    locs.append((loc, date_only(lastmod)))
            if locs:
                break
    if not locs:
        return []
    # Prefer recently changed pages; sitemap lastmod is a discovery hint, not always the publication date.
    cutoff = (datetime.now(timezone.utc).date() - timedelta(days=180)).isoformat()
    recent = [(u, d) for u, d in locs if d and d >= cutoff]
    candidates = recent if recent else locs[-MAX_SITEMAP_ARTICLES * 3:]
    candidates = candidates[-MAX_SITEMAP_ARTICLES:]
    results = []
    for url, lastmod in candidates:
        if normalize_url(url).rstrip("/") == normalize_url(source["url"]).rstrip("/"):
            continue
        record = parse_html_article(url, source, sitemap_date=lastmod)
        if record:
            results.append(record)
        time.sleep(0.15)
    return results


def parse_homepage_links(source: dict, homepage_html: bytes | None) -> list[dict]:
    if not homepage_html or source.get("source_type") == "official-site":
        return []
    soup = BeautifulSoup(homepage_html, "html.parser")
    candidates = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = normalize_url(urljoin(source["url"], a["href"]))
        text = a.get_text(" ", strip=True)
        if not href or not same_host(href, source["url"]):
            continue
        if href in seen or href.rstrip("/") == normalize_url(source["url"]).rstrip("/"):
            continue
        seen.add(href)
        path = urlparse(href).path.lower()
        if any(part in path for part in ("/tag/", "/category/", "/author/", "/page/", "/search", "/login", "/privacy", "/terms", "/about", "/contact", "/careers", "/jobs", "/events")):
            continue
        # Do not treat arbitrary navigation/project pages as articles. Fallback
        # links must resemble an article path or contain a date-like URL segment.
        article_path = re.search(r"/(blog|blogs|post|posts|article|articles|writing|notes|research|insights|news|engineering|publications)(/|$)", path)
        dated_path = re.search(r"/20\d{2}(/|$)", path)
        if not article_path and not dated_path:
            continue
        if len(text) < 12 or len(path.strip("/").split("/")) < 1:
            continue
        if text.lower() in {"read more", "learn more", "view all", "next", "previous"}:
            continue
        # Prefer deeper paths and descriptive anchor text.
        score = min(len(path.strip("/").split("/")), 4) * 10 + min(len(text), 100) / 100
        candidates.append((score, href, text))
    candidates.sort(reverse=True)
    results = []
    for _, url, title in candidates[:MAX_LINK_FALLBACK]:
        record = parse_html_article(url, source, fallback_title=title)
        if record:
            results.append(record)
        time.sleep(0.15)
    return results


def collect_one(source: dict) -> tuple[list[dict], dict]:
    status = {"source_id": source["id"], "source_name": source["name"], "checked_at": now_iso(), "method": "none", "articles_found": 0, "status": "no-content", "error": None}
    if not source.get("enabled", True):
        status["status"] = "disabled"
        return [], status
    homepage_response, homepage_error = fetch(source["url"])
    homepage_html = homepage_response.content if homepage_response is not None else None
    feed_url = discover_feed(source, homepage_html)
    if feed_url:
        articles = parse_feed(source, feed_url)
        if articles:
            status.update({"method": "feed", "articles_found": len(articles), "status": "ok", "feed_url": feed_url})
            return articles, status
    # Sitemap fallback is limited to sources likely to publish articles.
    if source.get("source_type") in {"official-blog", "research-blog", "research-index", "personal-blog", "personal-site", "newsletter", "podcast", "research-publication"}:
        articles = parse_sitemap(source)
        if articles:
            status.update({"method": "sitemap", "articles_found": len(articles), "status": "ok"})
            return articles, status
    articles = parse_homepage_links(source, homepage_html)
    if articles:
        status.update({"method": "homepage-links", "articles_found": len(articles), "status": "ok"})
    elif homepage_error == "robots-disallowed":
        status.update({"status": "robots-disallowed", "error": None})
    elif homepage_error:
        status.update({"status": "error", "error": homepage_error})
    elif not homepage_response:
        status.update({"status": "error", "error": "homepage-unavailable"})
    else:
        status.update({"status": "directory-only", "error": None})
    return articles, status


def load_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return fallback


def main() -> int:
    parser = argparse.ArgumentParser(description="Update the Research Radar article index without an AI API.")
    parser.add_argument("--limit", type=int, default=0, help="Only process the first N enabled sources (useful for testing).")
    parser.add_argument("--dry-run", action="store_true", help="Collect and report results without writing JSON files.")
    args = parser.parse_args()
    sources_payload = load_json(SOURCES_PATH, {"sources": []})
    all_sources = sources_payload.get("sources", [])
    policy_changed = apply_source_policy(all_sources)
    sources_payload["sources"] = all_sources
    if policy_changed and not args.dry_run:
        SOURCES_PATH.write_text(json.dumps(sources_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sources = [source for source in all_sources if source.get("enabled", True) and is_english_source(source)]
    if args.limit > 0:
        sources = sources[:args.limit]
    old_payload = load_json(ARTICLES_PATH, {"articles": []})
    existing = old_payload.get("articles", [])
    statuses = []
    collected = []
    print(f"Collecting from {len(sources)} sources (no AI API)...")
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(collect_one, source): source for source in sources if source.get("enabled", True)}
        for future in as_completed(futures):
            source = futures[future]
            try:
                articles, status = future.result()
            except Exception as exc:
                articles = []
                status = {"source_id": source["id"], "source_name": source["name"], "checked_at": now_iso(), "method": "none", "articles_found": 0, "status": "error", "error": type(exc).__name__}
            statuses.append(status)
            collected.extend(articles)
            print(f"[{status['status']}] {source['name']}: {status['articles_found']} ({status['method']})")

    # Merge only current approved English sources. This also removes old items
    # from paused sources and non-English titles from the existing index.
    source_by_id = {source["id"]: source for source in all_sources if source.get("enabled", True) and is_english_source(source)}
    merged = {}
    for item in existing + collected:
        source = source_by_id.get(item.get("source_id"))
        if source is None or not is_relevant_article(source, item.get("title", ""), item.get("excerpt", "")):
            continue
        url = normalize_url(item.get("url", ""))
        if not url:
            continue
        item["url"] = url
        item["language"] = "en"
        item["source_name"] = source.get("name", item.get("source_name", "Unknown source"))
        item["source_url"] = source.get("url", item.get("source_url", ""))
        item["category"] = source.get("category", item.get("category", "other"))
        item["source_type"] = source.get("source_type", item.get("source_type", "Source"))
        item["topics"] = source.get("topics", item.get("topics", []))
        item["tier"] = source.get("tier", item.get("tier"))
        item["source_quality"] = source.get("source_quality", item.get("source_quality", "watchlist"))
        previous = merged.get(url)
        if previous is None:
            merged[url] = item
        else:
            # Prefer a real publication date and a publisher-provided excerpt when available.
            if not previous.get("published_at") and item.get("published_at"):
                previous["published_at"] = item["published_at"]
            if not previous.get("excerpt") and item.get("excerpt"):
                previous["excerpt"] = item["excerpt"]
            if item.get("discovered_at") and item["discovered_at"] > previous.get("discovered_at", ""):
                previous["discovered_at"] = item["discovered_at"]
    cutoff = (datetime.now(timezone.utc).date() - timedelta(days=KEEP_DAYS)).isoformat()
    articles = [item for item in merged.values() if (item.get("published_at") or item.get("discovered_at") or "0000-00-00") >= cutoff]
    articles.sort(key=lambda x: (x.get("published_at") or x.get("discovered_at") or "0000-00-00", x.get("discovered_at") or ""), reverse=True)
    statuses.sort(key=lambda x: (x.get("status") != "ok", x.get("source_name", "").lower()))
    ok_count = sum(1 for s in statuses if s.get("status") == "ok")
    if args.dry_run:
        print(f"Dry run: {len(articles)} merged articles; {ok_count}/{len(statuses)} sources yielded content. No files written.")
        return 0
    DATA.mkdir(exist_ok=True)
    ARTICLES_PATH.write_text(json.dumps({"last_updated_at": now_iso(), "articles": articles}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    STATUS_PATH.write_text(json.dumps({
        "last_checked_at": now_iso(),
        "source_count": len(sources_payload.get("sources", [])),
        "checked_count": len(statuses),
        "sources_with_articles": ok_count,
        "article_count": len(articles),
        "note": "No AI-generated summaries. Strictly curated English sources and deterministic topic filters are applied; publisher-provided excerpts are used only as source metadata.",
        "sources": statuses
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Done: {len(articles)} stored articles; {ok_count}/{len(statuses)} sources yielded content.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
