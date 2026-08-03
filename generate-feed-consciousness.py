#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

OUT = Path("feed.json")
MAX_ITEMS = 150

# Replace these URLs with the current IANDS RSS/Atom feed URLs you want to follow.
SOURCES = [
    (
        "IANDS · Journal of Near-Death Studies",
        "https://www.iands.org/research0/research/publications/journal-of-near-death-studies.feed?type=rss",
    ),
    (
        "IANDS · NDE Research",
        "https://research.iands.org/component/weblinks/category/142-nde-research.feed?type=rss",
    ),
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; IANDSFeed/1.0; +https://github.com/tasselrex/consciousness)"
}


def clean(s: str | None) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", " ", s).strip()


def strip_html(s: str | None) -> str:
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", " ", s)
    return (
        clean(s)
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&apos;", "'")
    )


def truncate(s: str, n: int = 180) -> str:
    s = clean(s)
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def fetch(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_atom(root, source_label):
    ns = {"a": "http://www.w3.org/2005/Atom"}
    items = []

    for entry in root.findall("a:entry", ns):
        title = clean(entry.findtext("a:title", default="", namespaces=ns))
        summary = truncate(
            strip_html(entry.findtext("a:summary", default="", namespaces=ns))
        )

        published = clean(
            entry.findtext("a:published", default="", namespaces=ns)
        )[:10]

        updated = clean(
            entry.findtext("a:updated", default="", namespaces=ns)
        )[:10]

        link = ""
        for l in entry.findall("a:link", ns):
            if l.attrib.get("href"):
                link = l.attrib["href"]
                break

        if not link:
            link = clean(entry.findtext("a:id", default="", namespaces=ns))

        authors = ", ".join(
            clean(a.findtext("a:name", default="", namespaces=ns))
            for a in entry.findall("a:author", ns)
        )

        items.append(
            {
                "title": title,
                "summary": summary,
                "source": source_label,
                "date": published
                or updated
                or datetime.now(timezone.utc).date().isoformat(),
                "link": link,
                "authors": authors,
            }
        )

    return items


def parse_rss(root, source_label):
    items = []

    channel = root.find("channel")
    if channel is None:
        return items

    for item in channel.findall("item"):
        title = clean(item.findtext("title"))
        summary = truncate(strip_html(item.findtext("description")))
        date = clean(item.findtext("pubDate"))[:10]
        link = clean(item.findtext("link"))

        items.append(
            {
                "title": title,
                "summary": summary,
                "source": source_label,
                "date": date
                or datetime.now(timezone.utc).date().isoformat(),
                "link": link,
                "authors": "",
            }
        )

    return items


def parse_feed(xml_text: str, source_label: str):
    root = ET.fromstring(xml_text)

    if root.tag.endswith("feed"):
        return parse_atom(root, source_label)

    return parse_rss(root, source_label)


def main():
    all_items = []
    errors = []

    for label, url in SOURCES:
        try:
            xml = fetch(url)
            all_items.extend(parse_feed(xml, label))
        except Exception as e:
            errors.append(f"{label}: {e}")

    seen = set()
    dedup = []

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

    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"Wrote {OUT} with {len(payload['items'])} items")

    if errors:
        print("\nErrors:")
        for e in errors:
            print(" -", e)


if __name__ == "__main__":
    main()
