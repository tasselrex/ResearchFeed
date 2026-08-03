#!/usr/bin/env python3
from __future__ import annotations

"""
Consciousness / NDE / OBE feed generator.

What this script does:
- Tries RSS/Atom discovery from each seed URL.
- Falls back to site-specific scraping for NDERF.
- Merges all items into feed.json.
- Deduplicates, tags, and keeps newest items first.
- Never fails just because one source is down.

No third-party dependencies.
"""

import html
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

OUT = Path("feed.json")
MAX_ITEMS = 500
FETCH_TIMEOUT = 25

# Add/remove seeds here. Facebook is intentionally omitted because a public RSS feed
# is not reliable there.
SEEDS = [
    {"label": "IANDS", "url": "https://www.iands.org/", "mode": "discover"},
    {"label": "NDERF", "url": "https://www.nderf.org/", "mode": "nderf"},
    {"label": "UVA DOPS", "url": "https://med.virginia.edu/perceptual-studies/", "mode": "discover"},
    {"label": "Horizon Research", "url": "http://www.horizonresearch.org/", "mode": "discover"},
    {"label": "Dr Penny Sartori", "url": "https://www.drpennysartori.com/", "mode": "discover"},
    {"label": "Dancing Past the Dark", "url": "https://dancingpastthedark.wordpress.com/", "mode": "discover"},
    {"label": "Melvin Morse", "url": "https://www.melvinmorsemd.com/", "mode": "discover"},
    {"label": "SelfConsciousMind", "url": "https://selfconsciousmind.com/", "mode": "discover"},
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; WonderFeed/2.0; +https://github.com/tasselrex)"
}


# -----------------------------
# text helpers
# -----------------------------

def clean(s: str | None) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", " ", s).strip()


def strip_html(s: str | None) -> str:
    if not s:
        return ""
    s = re.sub(r"<script[\s\S]*?</script>", " ", s, flags=re.I)
    s = re.sub(r"<style[\s\S]*?</style>", " ", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return clean(s)


def truncate(s: str, n: int = 180) -> str:
    s = clean(s)
    if len(s) <= n:
        return s
    return s[: max(0, n - 1)].rstrip() + "…"


def normalize_url(url: str) -> str:
    url = clean(url)
    if not url:
        return ""
    parsed = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))


def now_date() -> str:
    return datetime.now(timezone.utc).date().isoformat()


# -----------------------------
# networking
# -----------------------------

def fetch(url: str, timeout: int = FETCH_TIMEOUT) -> tuple[str, str]:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        content_type = resp.headers.get_content_type() or ""
        body = resp.read().decode("utf-8", errors="replace")
        return body, content_type


def resolve(base_url: str, href: str) -> str:
    return normalize_url(urllib.parse.urljoin(base_url, href))


# -----------------------------
# item shaping / tagging
# -----------------------------

def classify_tags(title: str, summary: str = "", source: str = "") -> list[str]:
    text = f"{title} {summary} {source}".lower()
    tags: list[str] = []

    def add(tag: str) -> None:
        if tag not in tags:
            tags.append(tag)

    if any(k in text for k in ["out-of-body", "out of body", "obe", "astral", "lucid dream"]):
        add("OBE")

    if any(k in text for k in ["near-death", "nde", "deathbed", "shared death", "after-death"]):
        add("NDE")

    if any(k in text for k in ["reincarnation", "past-life", "past life"]):
        add("Reincarnation")

    if any(k in text for k in ["psi", "medium", "mediumship", "survival", "after-death communication", "adc"]):
        add("Psi/Survival")

    if any(k in text for k in ["video", "podcast", "interview", "youtube", "talk"]):
        add("Video")

    if any(k in text for k in ["research", "study", "paper", "journal", "publication", "review"]):
        add("Research")

    if any(k in text for k in ["blog", "essay", "post", "article"]):
        add("Essay")

    if not tags:
        add("Consciousness")

    return tags


def make_item(
    title: str,
    summary: str,
    source: str,
    date: str,
    link: str,
    authors: str = "",
    tags: list[str] | None = None,
) -> dict:
    link = normalize_url(link)
    tags = tags[:] if tags else classify_tags(title, summary, source)
    return {
        "title": clean(title),
        "summary": truncate(summary, 180),
        "source": clean(source),
        "date": clean(date)[:10] or now_date(),
        "link": link,
        "authors": clean(authors),
        "tags": tags,
    }


# -----------------------------
# parsing RSS / Atom
# -----------------------------

def parse_atom(xml_text: str, source_label: str) -> list[dict]:
    ns = {"a": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(xml_text)
    items: list[dict] = []

    for entry in root.findall("a:entry", ns):
        title = clean(entry.findtext("a:title", default="", namespaces=ns))
        summary = truncate(strip_html(entry.findtext("a:summary", default="", namespaces=ns)), 180)
        published = clean(entry.findtext("a:published", default="", namespaces=ns))[:10]
        updated = clean(entry.findtext("a:updated", default="", namespaces=ns))[:10]

        link = ""
        for link_el in entry.findall("a:link", ns):
            href = link_el.attrib.get("href", "")
            rel = link_el.attrib.get("rel", "alternate")
            if href and rel == "alternate":
                link = href
                break
        if not link:
            link = clean(entry.findtext("a:id", default="", namespaces=ns))

        authors = [
            clean(author.findtext("a:name", default="", namespaces=ns))
            for author in entry.findall("a:author", ns)
        ]
        authors = ", ".join([a for a in authors if a][:3])

        items.append(
            make_item(
                title=title,
                summary=summary,
                source=source_label,
                date=published or updated or now_date(),
                link=link,
                authors=authors,
            )
        )

    return items


def parse_rss(xml_text: str, source_label: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    items: list[dict] = []

    channel = root.find("channel")
    if channel is None:
        return items

    for entry in channel.findall("item"):
        title = clean(entry.findtext("title", default=""))
        summary = truncate(strip_html(entry.findtext("description", default="")), 180)
        published = clean(entry.findtext("pubDate", default=""))[:10]
        updated = clean(entry.findtext("date", default=""))[:10]
        link = clean(entry.findtext("link", default="")) or clean(entry.findtext("guid", default=""))

        authors = [
            clean(entry.findtext("author", default="")),
            clean(entry.findtext("{http://purl.org/dc/elements/1.1/}creator", default="")),
        ]
        authors = ", ".join([a for a in authors if a][:3])

        items.append(
            make_item(
                title=title,
                summary=summary,
                source=source_label,
                date=published or updated or now_date(),
                link=link,
                authors=authors,
            )
        )

    return items


def parse_feed(xml_text: str, source_label: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    tag = root.tag.lower()
    if tag.endswith("feed"):
        return parse_atom(xml_text, source_label)
    if tag.endswith("rss") or tag.endswith("rdf"):
        return parse_rss(xml_text, source_label)

    try:
        items = parse_atom(xml_text, source_label)
        if items:
            return items
    except Exception:
        pass
    return parse_rss(xml_text, source_label)


# -----------------------------
# feed discovery
# -----------------------------

def looks_like_feed_url(url: str) -> bool:
    u = url.lower()
    return any(
        token in u
        for token in (
            "/feed",
            ".rss",
            ".atom",
            "/rss",
            "/atom",
            "format=feed",
            "type=rss",
            "type=atom",
        )
    )


def discover_feed_urls(page_url: str) -> list[str]:
    """Find RSS/Atom feed URLs from a page's HTML."""
    try:
        html_text, content_type = fetch(page_url)
    except Exception:
        return []

    if content_type and content_type not in {"text/html", "application/xhtml+xml"}:
        return []

    found: list[str] = []
    patterns = [
        r"<link[^>]+rel=[\"']alternate[\"'][^>]+type=[\"'](?:application/rss\+xml|application/atom\+xml|text/xml)[\"'][^>]+href=[\"']([^\"']+)[\"']",
        r"<link[^>]+type=[\"'](?:application/rss\+xml|application/atom\+xml|text/xml)[\"'][^>]+rel=[\"']alternate[\"'][^>]+href=[\"']([^\"']+)[\"']",
        r"href=[\"']([^\"']+(?:feed|rss|atom|xml)(?:\?[^\"']*)?)[\"']",
    ]

    for pat in patterns:
        for m in re.finditer(pat, html_text, flags=re.I):
            abs_url = resolve(page_url, m.group(1))
            if looks_like_feed_url(abs_url):
                found.append(abs_url)

    return dedupe_urls(found)


# -----------------------------
# generic HTML fallback
# -----------------------------

def page_title_from_html(html_text: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", html_text, flags=re.I | re.S)
    return strip_html(m.group(1)) if m else ""


def extract_page_cards(page_url: str, source_label: str, max_items: int = 20) -> list[dict]:
    """Fallback for sites that do not expose a feed."""
    html_text, _ = fetch(page_url)
    page_title = page_title_from_html(html_text) or source_label

    items: list[dict] = []
    seen: set[tuple[str, str]] = set()

    heading_pat = re.compile(
        r"<(h1|h2|h3|h4)[^>]*>\s*<a[^>]+href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>.*?</\1>",
        flags=re.I | re.S,
    )
    for _, href, title_html in heading_pat.findall(html_text):
        title = strip_html(title_html)
        if not title or len(title) < 6:
            continue
        link = resolve(page_url, href)
        key = (title.lower(), link)
        if key in seen:
            continue
        seen.add(key)
        items.append(
            make_item(
                title=title,
                summary=page_title,
                source=source_label,
                date=now_date(),
                link=link,
            )
        )
        if len(items) >= max_items:
            break

    if items:
        return items

    article_pat = re.compile(r"<article[^>]*>([\s\S]*?)</article>", flags=re.I)
    for article in article_pat.findall(html_text):
        m = re.search(r"<a[^>]+href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", article, flags=re.I | re.S)
        if not m:
            continue
        link = resolve(page_url, m.group(1))
        title = strip_html(m.group(2))
        if not title:
            continue
        snippet = truncate(strip_html(article), 180) or page_title
        key = (title.lower(), link)
        if key in seen:
            continue
        seen.add(key)
        items.append(
            make_item(
                title=title,
                summary=snippet,
                source=source_label,
                date=now_date(),
                link=link,
            )
        )
        if len(items) >= max_items:
            break

    return items


# -----------------------------
# NDERF-specific extraction
# -----------------------------

def extract_nderf_items() -> list[dict]:
    """Extract a small set of recent NDE/OBE stories from NDERF.

    NDERF does not provide a predictable public RSS feed, so this uses the archive
    pages and then the linked experience pages.
    """
    archive_list_url = "https://www.nderf.org/Archives/archivelist.htm"
    html_text, _ = fetch(archive_list_url)

    archive_urls: list[str] = []
    for href in re.findall(r"href=[\"']([^\"']+/Archives/[^\"']+?\.htm)[\"']", html_text, flags=re.I):
        archive_urls.append(resolve(archive_list_url, href))

    if not archive_urls:
        for href in re.findall(r"href=[\"']([^\"']+\.htm)[\"']", html_text, flags=re.I):
            abs_url = resolve(archive_list_url, href)
            if "/Archives/" in abs_url:
                archive_urls.append(abs_url)

    archive_urls = dedupe_urls(archive_urls)[:3]

    items: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for archive_url in archive_urls:
        try:
            archive_html, _ = fetch(archive_url)
        except Exception:
            continue

        exp_links: list[str] = []
        for href in re.findall(r"href=[\"']([^\"']+/Experiences/[^\"']+?\.html)[\"']", archive_html, flags=re.I):
            exp_links.append(resolve(archive_url, href))
        exp_links = dedupe_urls(exp_links)[:8]

        for exp_url in exp_links:
            try:
                exp_html, _ = fetch(exp_url)
            except Exception:
                continue

            item = parse_nderf_experience_page(exp_html, exp_url)
            if not item:
                continue

            key = (item["title"].lower(), item["link"])
            if key in seen:
                continue
            seen.add(key)
            items.append(item)

            if len(items) >= 16:
                return items

    return items


def parse_nderf_experience_page(html_text: str, page_url: str) -> dict | None:
    title = page_title_from_html(html_text)
    if not title:
        m = re.search(r"<h1[^>]*>(.*?)</h1>", html_text, flags=re.I | re.S)
        title = strip_html(m.group(1)) if m else ""
    if not title:
        return None

    text = strip_html(html_text)

    date = ""
    m_date = re.search(r"Date (?:NDE|OBE) Occurred:\s*([^\n\r<]+)", text, flags=re.I)
    if m_date:
        date = clean(m_date.group(1))[:10] or clean(m_date.group(1))

    summary = ""
    m_desc = re.search(
        r"Experience Description\s*(.*?)(?:Background Information:|Did you have a near-death experience\?|$)",
        text,
        flags=re.I | re.S,
    )
    if m_desc:
        summary = truncate(clean(m_desc.group(1)), 180)
    else:
        paras = [p for p in re.split(r"\s{2,}", text) if len(p.strip()) > 80]
        summary = truncate(paras[0], 180) if paras else truncate(text, 180)

    if not date:
        date = now_date()

    return make_item(
        title=title,
        summary=summary,
        source="NDERF",
        date=date,
        link=page_url,
        tags=classify_tags(title, summary, "NDERF"),
    )


# -----------------------------
# aggregation
# -----------------------------

def dedupe_urls(urls: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen = set()
    for url in urls:
        url = normalize_url(url)
        if not url or url in seen:
            continue
        seen.add(url)
        out.append(url)
    return out


def gather_from_seed(seed: dict) -> list[dict]:
    label = seed["label"]
    url = seed["url"]
    mode = seed.get("mode", "discover")

    if mode == "nderf":
        return extract_nderf_items()

    items: list[dict] = []

    feed_urls = discover_feed_urls(url)
    for feed_url in feed_urls[:4]:
        try:
            xml_text, _ = fetch(feed_url)
            items.extend(parse_feed(xml_text, label))
        except Exception:
            continue

    if items:
        return items

    try:
        return extract_page_cards(url, label, max_items=20)
    except Exception:
        return []


def main() -> None:
    all_items: list[dict] = []
    errors: list[str] = []
    source_counts: dict[str, int] = {}

    for seed in SEEDS:
        try:
            items = gather_from_seed(seed)
            all_items.extend(items)
            source_counts[seed["label"]] = len(items)
        except Exception as e:
            errors.append(f'{seed["label"]}: {e}')
            source_counts[seed["label"]] = 0

    seen = set()
    deduped: list[dict] = []
    for item in all_items:
        key = (item.get("title", "").strip().lower(), item.get("link", "").strip())
        if not key[0] and not key[1]:
            continue
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    deduped.sort(key=lambda x: (x.get("date", ""), x.get("title", "")), reverse=True)

    payload = {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "items": deduped[:MAX_ITEMS],
        "errors": errors,
        "sourceCounts": source_counts,
        "sourceTotal": len(SEEDS),
        "itemTotal": len(deduped),
    }

    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {OUT} with {len(payload['items'])} items")
    if errors:
        print("Errors:")
        for e in errors:
            print(" -", e)


if __name__ == "__main__":
    main()
