#!/usr/bin/env python3
"""Sync newly listed public resources from the upstream AI blog index.

This is deterministic Markdown parsing only; no AI model or API is used.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

import requests

ROOT = Path(__file__).resolve().parents[1]
SOURCES_PATH = ROOT / "data" / "sources.json"
INDEX_URL = "https://raw.githubusercontent.com/joeseesun/ai-blog-res/main/AI%E5%8D%9A%E5%AE%A2%E8%B5%84%E6%BA%90-%E5%AE%8C%E6%95%B4%E7%B4%A2%E5%BC%95.md"
USER_AGENT = "QuantResearchRadarBot/0.1 (+public-source-index; no AI API)"


def normalize_url(url: str) -> str:
    p = urlparse(url.strip())
    if p.scheme not in ("http", "https") or not p.netloc:
        return ""
    query = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in {"ref", "fbclid", "gclid"}]
    return urlunparse((p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/"), "", urlencode(query), ""))


def cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text or ""))


def slug(text: str) -> str:
    text = (text or "").lower()
    value = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return value[:34] or "source"


def infer_section_category(section: str) -> str:
    s = section.lower()
    if any(x in s for x in ("学术机构博客", "学术机构", "mila", "berkeley", "stanford", "mit csail", "cmu")):
        return "ai-academic"
    if any(x in s for x in ("个人技术博客", "openai系", "anthropic系", "google/deepmind系", "meta/fair系", "mistral ai系", "深度学习先驱", "独立/跨机构")):
        return "ai-researcher"
    if any(x in s for x in ("中国ai研究者与团队博客", "公司官方博客", "国际公司官方博客", "中国ai团队")):
        return "ai-company"
    if any(x in s for x in ("特殊主题资源", "ai安全与对齐", "开源工具与平台", "中文ai社区", "视频教程资源")):
        return "ai-community"
    return "ai-community"


def infer_source_type(category: str) -> str:
    return {
        "ai-researcher": "personal-blog",
        "ai-company": "official-blog",
        "ai-academic": "research-blog",
        "ai-community": "community",
    }.get(category, "community")


def extract_url(cell: str) -> str | None:
    match = re.search(r"https?://[^\s|<>\])]+", cell)
    if not match:
        return None
    url = match.group(0).rstrip(".,;:!?}")
    # Markdown link syntax may leave punctuation around a URL.
    if "†" in url:
        url = url.split("†", 1)[0]
    normalized = normalize_url(url)
    return normalized or None


def row_to_source(cells: list[str], section: str) -> dict | None:
    if len(cells) < 2 or not any(cells):
        return None
    if all(not c.strip(" :-") for c in cells):
        return None
    if cells[0].lower() in {"作者", "作者/团队", "作者/团队", "公司", "机构", "资源", "团队/机构", "团队/机构", "学习目标", "角色", "内容风格", "活跃度", "地区/背景"}:
        return None
    url = None
    url_cell_index = -1
    for i, cell in enumerate(cells):
        candidate = extract_url(cell)
        if candidate:
            url = candidate
            url_cell_index = i
            break
    if not url:
        return None
    category = infer_section_category(section)
    # Main tables put the public blog title in column 2; compact link lists use column 1.
    if url_cell_index >= 2 and len(cells) > 1 and cells[1].strip():
        name = cells[1].strip()
    else:
        name = cells[0].strip()
    if not name or name in {"---", "作者", "公司", "机构"}:
        return None

    description_parts = []
    topics_text = ""
    section_l = section.lower()
    if url_cell_index >= 2 and len(cells) > 4:
        if category == "ai-researcher":
            description_parts = [cells[3], cells[4]]
            topics_text = cells[4] + " " + (cells[7] if len(cells) > 7 else "")
        elif category == "ai-company":
            description_parts = [cells[3], cells[6] if len(cells) > 6 else ""]
            topics_text = cells[3] + " " + (cells[6] if len(cells) > 6 else "")
        elif category == "ai-academic":
            description_parts = [cells[3], cells[6] if len(cells) > 6 else ""]
            topics_text = cells[3] + " " + (cells[6] if len(cells) > 6 else "")
    elif len(cells) > url_cell_index + 1:
        description_parts = [cells[url_cell_index + 1]]
        topics_text = cells[url_cell_index + 1]
    description = " · ".join(re.sub(r"\s+", " ", x).strip() for x in description_parts if x and x.strip())
    topics = []
    for item in re.split(r"[、，,;/；|]+", topics_text):
        item = item.strip()
        if item and len(item) <= 40 and item not in topics:
            topics.append(item)
        if len(topics) >= 8:
            break
    host_slug = slug(urlparse(url).netloc.replace("www.", ""))
    source_id = f"idx-{host_slug}-{hashlib.sha1(url.encode('utf-8')).hexdigest()[:7]}"
    return {
        "id": source_id,
        "name": name[:140],
        "url": url,
        "category": category,
        "source_type": infer_source_type(category),
        "topics": topics,
        "language": "zh" if cjk(name + " " + description) else "en",
        "description": (description or "Listed in the upstream AI blog resource index.")[:300],
        "tier": None,
        "enabled": True,
        "feed_url": None,
        "source_index": "joeseesun/ai-blog-res"
    }


def parse_index(markdown: str) -> list[dict]:
    section = ""
    result = []
    seen = set()
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if line.startswith("#"):
            section = line.lstrip("# ").strip()
            continue
        if "|" not in line or line.startswith("<!--"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        item = row_to_source(cells, section)
        if item and normalize_url(item["url"]) not in seen:
            seen.add(normalize_url(item["url"]))
            result.append(item)
    return result


def main() -> int:
    try:
        response = requests.get(INDEX_URL, timeout=20, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
        markdown = response.text
    except requests.RequestException as exc:
        print(f"Warning: upstream index unavailable ({type(exc).__name__}); keeping existing source registry.")
        return 0
    upstream = parse_index(markdown)
    if not upstream:
        print("Warning: no source rows parsed from upstream index; keeping existing source registry.")
        return 0
    try:
        payload = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        payload = {"sources": []}
    current = payload.get("sources", [])
    by_url = {normalize_url(item.get("url", "")): item for item in current if normalize_url(item.get("url", ""))}
    added = 0
    marked = 0
    for item in upstream:
        key = normalize_url(item["url"])
        if key in by_url:
            existing = by_url[key]
            if existing.get("source_index") != "joeseesun/ai-blog-res":
                existing["source_index"] = "joeseesun/ai-blog-res"
                marked += 1
            continue
        current.append(item)
        by_url[key] = item
        added += 1
    if added or marked:
        payload["sources"] = current
        payload["source_index"] = "https://github.com/joeseesun/ai-blog-res/blob/main/AI%E5%8D%9A%E5%AE%A2%E8%B5%84%E6%BA%90-%E5%AE%8C%E6%95%B4%E7%B4%A2%E5%BC%95.md"
        payload["updated_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        payload["note"] = "Source registry syncs newly listed resources from the upstream AI blog index and preserves manually curated quant/interview sources."
        SOURCES_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Upstream index rows parsed: {len(upstream)}; added {added}; provenance marked {marked}; total sources {len(current)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
