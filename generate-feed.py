#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

OUT = Path("feed.json")
MAX_ITEMS = 24

QUERIES = [
    ("arXiv · consciousness", 'all:consciousness OR all:"global workspace" OR all:"neural correlates of consciousness"'),
    ("arXiv · anesthesia", 'all:anesthesia OR all:anaesthesia OR all:"loss of consciousness"'),
    ("arXiv · philosophy of mind", 'all:"philosophy of mind" OR all:"integrated information" OR all:"machine consciousness"'),
    ("arXiv · meditation", 'all:meditation OR all:awareness OR all:attention OR all:"altered states"'),
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ConsciousnessFeed/1.0; +https://github.com/tasselrex/AIResearchFeed)"
}

def clean(s: str | None) -> str:
    if not s:
        return ""
    s = re.sub(r"\s+", " ", s)
    return s.strip()

def strip_html(s: str | None) -> str:
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", " ", s)
    s = clean(s)
    return (
        s.replace("&amp;", "&")
         .replace("&lt;", "<")
         .replace("&gt;", ">")
         .replace("&quot;", '"')
         .replace("&apos;", "'")
    )

def truncate(s: str, n: int = 180) -> str:
    s = clean(s)
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"

def fetch(url: str, timeout: int = 25) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")

def parse_atom(xml_text: str, source_label: str):
    ns = {"a": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(xml_text)
    items = []
    for entry in root.findall("a:entry", ns):
        title = clean(entry.findtext("a:title", default="", namespaces=ns))
        summary = truncate(strip_html(entry.findtext("a:summary", default="", namespaces=ns)), 180)
        published = clean(entry.findtext("a:published", default="", namespaces=ns))[:10]
        updated = clean(entry.findtext("a:updated", default="", namespaces=ns))[:10]

        link = ""
        for link_el in entry.findall("a:link", ns):
            if link_el.attrib.get("rel", "alternate") == "alternate" and link_el.attrib.get("href"):
                link = link_el.attrib["href"]
                break
        if not link:
            id_text = clean(entry.findtext("a:id", default="", namespaces=ns))
            link = id_text

        authors = [
            clean(author.findtext("a:name", default="", namespaces=ns))
            for author in entry.findall("a:author", ns)
        ]
        authors = ", ".join([a for a in authors if a][:3])

        items.append({
            "title": title,
            "summary": summary,
            "source": source_label,
            "date": published or updated or datetime.now(timezone.utc).date().isoformat(),
            "link": link,
            "authors": authors,
        })
    return items

def arxiv_url(query: str) -> str:
    base = "https://export.arxiv.org/api/query"
    params = {
        "search_query": query,
        "start": "0",
        "max_results": "10",
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    return base + "?" + urllib.parse.urlencode(params, safe=':" OR')

def main():
    all_items = []
    errors = []
    for label, query in QUERIES:
        try:
            xml_text = fetch(arxiv_url(query))
            items = parse_atom(xml_text, label)
            all_items.extend(items)
        except Exception as e:
            errors.append(f"{label}: {e}")

    dedup = []
    seen = set()
    for item in all_items:
        key = item["title"].lower()
        if key in seen:
            continue
        seen.add(key)
        dedup.append(item)

    dedup.sort(key=lambda x: x["date"], reverse=True)

    payload = {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "items": dedup[:MAX_ITEMS],
        "errors": errors,
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT} with {len(payload['items'])} items")

if __name__ == "__main__":
    main()
