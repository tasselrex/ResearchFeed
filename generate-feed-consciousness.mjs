#!/usr/bin/env node
/**

Generates feed.json for an IANDS consciousness / NDE feed.
Sources: IANDS RSS/Atom feeds.


No external dependencies required.
*/

const fs = require("fs/promises");

const OUT_FILE = "feed.json";
const MAX_ITEMS = 24;

// Official/current IANDS feeds found on the IANDS sites.
const SOURCES = [
{
source: "IANDS · Journal of Near-Death Studies",
url: "https://www.iands.org/research0/research/publications/journal-of-near-death-studies.feed?type=rss",
},
{
source: "IANDS · NDE research links",
url: "https://research.iands.org/component/weblinks/category/142-nde-research.feed?type=rss",
},
];

function stripTags(s = "") {
return String(s).replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
}

function htmlToText(s = "") {
return stripTags(s)
.replace(/&/g, "&")
.replace(/</g, "<")
.replace(/>/g, ">")
.replace(/"/g, '"')
.replace(/'/g, "'");
}

function truncate(s, n) {
const text = String(s || "").trim();
if (text.length <= n) return text;
return text.slice(0, Math.max(0, n - 1)).trimEnd() + "…";
}

function fetchWithTimeout(url, timeoutMs = 20000) {
const controller = new AbortController();
const t = setTimeout(() => controller.abort(), timeoutMs);

return fetch(url, {
signal: controller.signal,
headers: {
"User-Agent":
"Mozilla/5.0 (compatible; IANDSFeed/1.0; +https://github.com/tasselrex/consciousness)",
},
})
.then((res) => {
if (!res.ok) throw new Error(HTTP ${res.status} ${res.statusText});
return res.text();
})
.finally(() => clearTimeout(t));
}

function parseAtom(xml, sourceLabel) {
const entries = [];
const entryMatches = xml.match(/<entry\b[\s\S]*?</entry>/g) || [];

for (const entry of entryMatches) {
const get = (tag) => {
const m = entry.match(new RegExp(<${tag}>([\\s\\S]*?)<\\/${tag}>, "i"));
return m ? htmlToText(m[1]) : "";
};

const title = get("title");
const summary = truncate(get("summary"), 180);
const published = get("published").slice(0, 100);
const updated = get("updated").slice(0, 100);

const linkMatch =
  entry.match(/<link[^>]*rel="alternate"[^>]*href="([^"]+)"/i) ||
  entry.match(/<id>([\s\S]*?)<\/id>/i);

const authors = [...entry.matchAll(/<author>[\s\S]*?<name>([\s\S]*?)<\/name>[\s\S]*?<\/author>/gi)]
  .map((m) => htmlToText(m[1]))
  .filter(Boolean)
  .slice(0, 3)
  .join(", ");

entries.push({
  title,
  summary,
  source: sourceLabel,
  date: published || updated || new Date().toISOString().slice(0, 10),
  link: linkMatch ? htmlToText(linkMatch[1] || linkMatch[0]) : "https://www.iands.org/",
  authors,
});

}

return entries;
}

function parseRss(xml, sourceLabel) {
const entries = [];
const itemMatches = xml.match(/<item\b[\s\S]*?</item>/g) || [];

for (const item of itemMatches) {
const get = (tag) => {
const m = item.match(new RegExp(<${tag}>([\\s\\S]*?)<\\/${tag}>, "i"));
return m ? htmlToText(m[1]) : "";
};

const title = get("title");
const summary = truncate(get("description"), 180);
const published = get("pubDate").slice(0, 10);
const updated = get("date").slice(0, 10);
const link = get("link") || get("guid") || "https://www.iands.org/";

const authors = [get("author"), get("dc:creator")].filter(Boolean).slice(0, 3).join(", ");

entries.push({
  title,
  summary,
  source: sourceLabel,
  date: published || updated || new Date().toISOString().slice(0, 10),
  link,
  authors,
});

}

return entries;
}

function parseFeed(xml, sourceLabel) {
const head = xml.slice(0, 1200).toLowerCase();
if (head.includes("<feed")) return parseAtom(xml, sourceLabel);
if (head.includes("<rss") || head.includes("<rdf")) return parseRss(xml, sourceLabel);

try {
const atom = parseAtom(xml, sourceLabel);
if (atom.length) return atom;
} catch (_) {}

return parseRss(xml, sourceLabel);
}

async function gather() {
const all = [];
const errors = [];

for (const s of SOURCES) {
try {
const xml = await fetchWithTimeout(s.url);
const items = parseFeed(xml, s.source);
all.push(...items);
} catch (err) {
errors.push(${s.source}: ${err.message});
}
}

const seen = new Set();
const deduped = [];
for (const item of all) {
const key = (item.title || "").toLowerCase().trim();
if (!key || seen.has(key)) continue;
seen.add(key);
deduped.push(item);
}

deduped.sort((a, b) => String(b.date).localeCompare(String(a.date)));

const payload = {
updatedAt: new Date().toISOString(),
items: deduped.slice(0, MAX_ITEMS),
errors,
};

await fs.writeFile(OUT_FILE, JSON.stringify(payload, null, 2) + "\n", "utf8");
console.log(Wrote ${OUT_FILE} with ${payload.items.length} items);
if (errors.length) console.log("Errors:", errors);
}

gather().catch((err) => {
console.error(err);
process.exit(1);
});
