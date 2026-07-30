#!/usr/bin/env node
/**
 * Generates feed.json for a consciousness studies feed.
 * Sources: arXiv API (official Atom feed format).
 *
 * No external dependencies required.
 */

const fs = require("fs/promises");

const OUT_FILE = "feed.json";
const MAX_ITEMS = 24;

// Tune these queries as needed.
const SEARCHES = [
  {
    source: "arXiv · consciousness",
    query: 'all:consciousness OR all:"neural correlates of consciousness" OR all:"global workspace"'
  },
  {
    source: "arXiv · anesthesia",
    query: 'all:anesthesia OR all:anaesthesia OR all:"loss of consciousness"'
  },
  {
    source: "arXiv · meditation",
    query: 'all:meditation OR all:awareness OR all:attention OR all:"altered states"'
  },
  {
    source: "arXiv · philosophy of mind",
    query: 'all:"integrated information" OR all:"phi" OR all:"philosophy of mind" OR all:"machine consciousness"'
  }
];

function escapeXml(s = "") {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

function stripTags(s = "") {
  return String(s).replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
}

function htmlToText(s = "") {
  return stripTags(s)
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'");
}

function truncate(s, n) {
  const text = String(s || "").trim();
  if (text.length <= n) return text;
  return text.slice(0, Math.max(0, n - 1)).trimEnd() + "…";
}

function parseArxivFeed(xml, sourceLabel) {
  const entries = [];
  const entryMatches = xml.match(/<entry>[\s\S]*?<\/entry>/g) || [];

  for (const entry of entryMatches) {
    const get = (tag) => {
      const m = entry.match(new RegExp(`<${tag}>([\\s\\S]*?)<\\/${tag}>`));
      return m ? htmlToText(m[1]) : "";
    };

    const title = get("title").replace(/\s+/g, " ").trim();
    const summary = get("summary").replace(/\s+/g, " ").trim();
    const published = get("published").slice(0, 10);
    const updated = get("updated").slice(0, 10);

    const idMatch = entry.match(/<id>([\s\S]*?)<\/id>/);
    const linkMatch = entry.match(/<link[^>]*rel="alternate"[^>]*href="([^"]+)"/) || entry.match(/<id>([\s\S]*?)<\/id>/);

    const authors = [...entry.matchAll(/<author>[\s\S]*?<name>([\s\S]*?)<\/name>[\s\S]*?<\/author>/g)]
      .map(m => htmlToText(m[1]))
      .filter(Boolean)
      .slice(0, 3)
      .join(", ");

    entries.push({
      title,
      summary: truncate(summary, 180),
      source: sourceLabel,
      date: published || updated || new Date().toISOString().slice(0, 10),
      link: linkMatch ? htmlToText(linkMatch[1] || linkMatch[0]) : (idMatch ? htmlToText(idMatch[1]) : "https://arxiv.org/"),
      authors
    });
  }

  return entries;
}

async function fetchWithTimeout(url, timeoutMs = 20000) {
  const controller = new AbortController();
  const t = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      signal: controller.signal,
      headers: {
        "User-Agent": "Mozilla/5.0 (compatible; ConsciousnessFeed/1.0; +https://github.com/tasselrex/AIResearchFeed)"
      }
    });
    if (!res.ok) throw new Error(`HTTP ${res.status} ${res.statusText}`);
    return await res.text();
  } finally {
    clearTimeout(t);
  }
}

async function gather() {
  const all = [];
  for (const s of SEARCHES) {
    const url = new URL("https://export.arxiv.org/api/query");
    url.searchParams.set("search_query", s.query);
    url.searchParams.set("start", "0");
    url.searchParams.set("max_results", "8");
    url.searchParams.set("sortBy", "submittedDate");
    url.searchParams.set("sortOrder", "descending");

    try {
      const xml = await fetchWithTimeout(url.toString());
      const items = parseArxivFeed(xml, s.source);
      all.push(...items);
    } catch (err) {
      console.error(`Failed to fetch ${s.source}:`, err.message);
    }
  }

  // Deduplicate by title and keep the newest, most relevant ones.
  const seen = new Set();
  const deduped = [];
  for (const item of all) {
    const key = item.title.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    deduped.push(item);
  }

  // Prefer newer items; keep stable order within same date.
  deduped.sort((a, b) => String(b.date).localeCompare(String(a.date)));

  const payload = {
    updatedAt: new Date().toISOString(),
    items: deduped.slice(0, MAX_ITEMS)
  };

  await fs.writeFile(OUT_FILE, JSON.stringify(payload, null, 2) + "\n", "utf8");
  console.log(`Wrote ${OUT_FILE} with ${payload.items.length} items`);
}

gather().catch(err => {
  console.error(err);
  process.exit(1);
});
