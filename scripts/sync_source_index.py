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

from source_policy import apply_source_policy, has_non_latin_script, normalize_category

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


def allowed_source_section(section: str) -> bool:
    """Parse only substantive blog/research source sections, not tools or courses."""
    value = (section or "").strip().lower()
    return any(term in value for term in (
        "个人技术博客", "公司官方博客", "学术机构博客", "ai安全与对齐", "ai 安全与对齐"
    ))


def infer_section_category(section: str) -> str:
    s = section.lower()
    if "个人技术博客" in s:
        return "ai-researcher"
    if "公司官方博客" in s:
        return "ai-company"
    if "学术机构博客" in s:
        return "ai-academic"
    if "开源工具与平台" in s or "视频教程资源" in s:
        return "ai-engineering"
    if "ai安全与对齐" in s:
        return "ai-community"
    return "ai-community"


def infer_source_type(category: str) -> str:
    return {
        "ai-researcher": "personal-blog",
        "ai-company": "official-blog",
        "ai-academic": "research-blog",
        "ai-community": "community",
        "ai-engineering": "official-blog",
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
    if not allowed_source_section(section):
        return None
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
    legacy_category = infer_section_category(section)
    source_type = infer_source_type(legacy_category)
    category = normalize_category(legacy_category)
    # Main tables put the public blog title in column 2; compact link lists use column 1.
    if url_cell_index >= 2 and len(cells) > 1 and cells[1].strip():
        name = cells[1].strip()
    else:
        name = cells[0].strip()
    if not name or name in {"---", "作者", "公司", "机构"}:
        return None
    # English-only registry: do not infer language from the Chinese commentary
    # columns in the upstream index. Filter based on the actual source label.
    if has_non_latin_script(name):
        return None
    parsed_url = urlparse(url)
    host = parsed_url.netloc.lower().removeprefix("www.")
    blocked_hosts = {
        "moonshot.cn", "minimaxi.com", "zhipuai.cn", "shlab.org.cn",
        "deepseek.com", "developer.aliyun.com", "ai.tencent.com", "ai.baidu.com",
        "sensetime.com", "megvii.com", "modelbest.cn", "zhipu-ai.feishu.cn",
    }
    if any(host == blocked or host.endswith("." + blocked) for blocked in blocked_hosts):
        return None
    # Company and academic sections must point to an actual content area, not a
    # corporate home page. Personal blogs may legitimately live at the root.
    content_path = re.search(r"/(blog|blogs|news|insights|research|publications|engineering|tech|articles|posts|updates|writing|notes)(/|$)", parsed_url.path.lower())
    if section in {"三、公司官方博客", "四、学术机构博客"} and not content_path and host not in {"distill.pub", "alignmentforum.org", "blog.ml.cmu.edu"}:
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
        "source_type": source_type,
        "topics": topics,
        "language": "en",
        "description": (description or "Listed in the upstream AI blog resource index.")[:300],
        "tier": None,
        "enabled": False,
        "review_status": "pending",
        "source_quality": "watchlist",
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
        if "|" not in line or line.startswith("<!--") or not allowed_source_section(section):
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
    policy_changed = apply_source_policy(current)
    by_url = {normalize_url(item.get("url", "")): item for item in current if normalize_url(item.get("url", ""))}
    added = 0
    marked = 0
    for item in upstream:
        key = normalize_url(item["url"])
        if key in by_url:
            # Preserve the provenance and approval state of manually curated sources.
            existing = by_url[key]
            if not existing.get("source_index"):
                existing["source_index"] = "joeseesun/ai-blog-res"
                marked += 1
            continue
        current.append(item)
        by_url[key] = item
        added += 1
    policy_changed = apply_source_policy(current) or policy_changed
    if added or marked or policy_changed:
        payload["sources"] = current
        payload["source_index"] = "https://github.com/joeseesun/ai-blog-res/blob/main/AI%E5%8D%9A%E5%AE%A2%E8%B5%84%E6%BA%90-%E5%AE%8C%E6%95%B4%E7%B4%A2%E5%BC%95.md"
        payload["updated_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        payload["note"] = "Strict curated allowlist. Upstream personal-blog, official-blog, academic, and AI-safety candidates remain pending until manually approved; generic tool/course sections are not ingested."
        SOURCES_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    active_count = sum(1 for item in current if item.get("enabled") and item.get("language") == "en")
    pending_count = sum(1 for item in current if item.get("review_status") == "pending")
    print(f"Curated upstream candidates parsed: {len(upstream)}; added {added} pending candidates; provenance marked {marked}; active English sources {active_count}; pending review {pending_count}; total registry {len(current)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
