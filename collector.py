#!/usr/bin/env python3
"""
AI News Dashboard — Collector (cron edition)
============================================
Collects the latest AI news (last ~24-72h) using the unified search wrapper
(scripts/unified_search.py -> DuckDuckGo/Firecrawl) for breadth, plus the
time-filtered Hacker News (Algolia) feed for genuine 24h freshness.

Produces structured data with: title, url, summary, thumbnail, source,
date, upvotes, comments, tags.

Writes:
  - data.json        (top-level task artifact)
  - data/latest.json (consumed by index.html / GitHub Pages)

Usage: python3.11 collector.py
"""
import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse
import urllib.error
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = Path(__file__).parent
DATA_DIR = BASE / "data"
DATA_DIR.mkdir(exist_ok=True)
SCRIPTS = Path.home() / "scripts"
UNIFIED = SCRIPTS / "unified_search.py"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")

NOW = datetime.now(timezone.utc)
CUTOFF = NOW - timedelta(hours=72)  # generous window for web results
HN_CUTOFF = NOW - timedelta(hours=24)

# ---------------------------------------------------------------- helpers
def log(*a):
    print(f"[{datetime.now().strftime('%H:%M:%S')}]", *a, file=sys.stderr, flush=True)

def get_json(url, timeout=25, headers=None):
    h = {"User-Agent": UA, "Accept": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode()), None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"

def domain_of(url):
    try:
        m = re.match(r"https?://([^/]+)/?", url or "")
        return m.group(1).lower().replace("www.", "") if m else ""
    except Exception:
        return ""

def source_name(url, fallback="Web"):
    d = domain_of(url)
    if not d:
        return fallback
    # friendly name from domain
    known = {
        "techcrunch.com": "TechCrunch", "theverge.com": "The Verge",
        "arstechnica.com": "Ars Technica", "wired.com": "Wired",
        "reuters.com": "Reuters", "apnews.com": "AP News",
        "bloomberg.com": "Bloomberg", "cnbc.com": "CNBC",
        "venturebeat.com": "VentureBeat", "zdnet.com": "ZDNet",
        "artificialintelligence-news.com": "AI News", "openai.com": "OpenAI",
        "anthropic.com": "Anthropic", "deepmind.google": "Google DeepMind",
        "blog.google": "Google", "mistral.ai": "Mistral", "huggingface.co": "Hugging Face",
        "nvidia.com": "NVIDIA", "microsoft.com": "Microsoft", "meta.com": "Meta",
        "arxiv.org": "arXiv", "techradar.com": "TechRadar", "engadget.com": "Engadget",
        "theregister.com": "The Register", "silicon.co.uk": "Silicon UK",
        "tomshardware.com": "Tom's Hardware", "decrypt.co": "Decrypt",
        "cointelegraph.com": "Cointelegraph", "aibase.com": "AIBase",
        "marktechpost.com": "MarkTechPost", "syncedreview.com": "Synced",
        "analyticsindiamag.com": "Analytics India", "venturebeat.com": "VentureBeat",
    }
    return known.get(d, d.split(".")[0].title())

def classify_tags(story):
    text = (story.get("title", "") + " " + story.get("summary", "")).lower()
    tags = []
    tag_map = {
        "LLMs": ["llm", "gpt", "claude", "gemini", "mistral", "llama", "language model", "chatgpt", "gpt-", "model"],
        "Vision": ["image", "vision", "diffusion", "midjourney", "dall-e", "flux", "video generation", "sora"],
        "Open Source": ["open source", "open-source", "hugging face", "github", "weights", "gguf", "weights"],
        "Research": ["paper", "arxiv", "benchmark", "study", "research", "findings", "training"],
        "Agents": ["agent", "agentic", "autonomous", "copilot", "assistant", "workflow"],
        "Industry": ["startup", "funding", "acquisition", "ipo", "valuation", "revenue", "raise", "launch", "releases", "unveils", "announces"],
        "Regulation": ["regulation", "safety", "alignment", "policy", "ethics", "ban", "law", "eu ai", "executive order"],
        "Hardware": ["gpu", "nvidia", "tpu", "chip", "hardware", "cuda", "datacenter", "data center"],
        "Tools": ["api", "sdk", "framework", "library", "tool", "platform", "app"],
    }
    for tag, kws in tag_map.items():
        if any(kw in text for kw in kws):
            tags.append(tag)
    return tags[:3] if tags else ["AI"]

# ---------------------------------------------------------------- 1) unified search
QUERIES = [
    "OpenAI latest announcement",
    "Anthropic Claude news",
    "Google DeepMind Gemini release",
    "new AI model released",
    "AI regulation policy news",
    "NVIDIA AI chip data center",
    "open source LLM release",
    "AI agent framework launch",
]

# landing-page / non-article patterns to drop
JUNK = re.compile(
    r"(/category/|/tag/|/topics/|reddit\.com/r/|/search|/about|"
    r"artificialintelligence-news\.com/?$|techcrunch\.com/?$|reuters\.com/?$|"
    r"news\.ycombinator\.com|/jobs|/careers|/pricing|wikipedia\.org)",
    re.I)

def run_unified(query, limit=8):
    try:
        out = subprocess.run(
            [sys.executable, str(UNIFIED), "search", query, str(limit)],
            capture_output=True, text=True, timeout=120)
        if out.returncode != 0:
            log(f"  unified err [{query}]: rc={out.returncode} {out.stderr.strip()[:120]}")
            return []
        data = json.loads(out.stdout)
        items = (data.get("data") or {}).get("web") or []
        log(f"  unified [{query}] -> {len(items)} raw")
        return items
    except Exception as e:
        log(f"  unified exc [{query}]: {e}")
        return []

def collect_unified():
    results = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(run_unified, q): q for q in QUERIES}
        for f in as_completed(futs):
            results.extend(f.result())
    stories = []
    seen = set()
    for it in results:
        url = (it.get("url") or "").strip()
        title = (it.get("title") or "").strip()
        if not url or not title:
            continue
        if JUNK.search(url):
            continue
        key = title.lower()[:60]
        if key in seen:
            continue
        seen.add(key)
        pt = it.get("published_time")
        # parse date if present
        date_str = NOW.strftime("%Y-%m-%d")
        try:
            if pt:
                dt = datetime.fromisoformat(str(pt).replace("Z", "+00:00"))
                date_str = dt.strftime("%Y-%m-%d")
        except Exception:
            pass
        stories.append({
            "title": title,
            "url": url,
            "summary": (it.get("description") or "").strip(),
            "source": source_name(url),
            "date": date_str,
            "upvotes": 0,
            "comments": 0,
            "tags": [],
            "_recency": 1,  # web, recency unknown
        })
    log(f"unified total unique: {len(stories)}")
    return stories

# ---------------------------------------------------------------- 2) HN Algolia (24h)
HN_QUERIES = ["AI", "artificial intelligence", "LLM", "machine learning",
              "OpenAI", "Anthropic", "Gemini", "GPT", "Claude", "deep learning"]

def collect_hn():
    cutoff_i = int(HN_CUTOFF.timestamp())
    seen = set()
    out = []
    for q in HN_QUERIES:
        url = (f"https://hn.algolia.com/api/v1/search?tags=story"
               f"&query={urllib.parse.quote(q)}"
               f"&numericFilters=created_at_i>{cutoff_i}&hitsPerPage=12")
        data, err = get_json(url)
        if err:
            log(f"  HN err ({q}): {err}")
            continue
        for h in (data or {}).get("hits", []):
            oid = h.get("objectID")
            created = h.get("created_at_i") or 0
            if created < cutoff_i:
                continue
            if oid in seen:
                continue
            seen.add(oid)
            date_str = datetime.fromtimestamp(created, tz=timezone.utc).strftime("%Y-%m-%d")
            out.append({
                "title": h.get("title") or "",
                "url": h.get("url") or f"https://news.ycombinator.com/item?id={oid}",
                "summary": "",
                "source": "Hacker News",
                "date": date_str,
                "upvotes": h.get("points") or 0,
                "comments": h.get("num_comments") or 0,
                "tags": [],
                "hn_url": f"https://news.ycombinator.com/item?id={oid}",
                "_recency": 2,
            })
    out.sort(key=lambda x: x["upvotes"], reverse=True)
    log(f"HN total unique (24h): {len(out)}")
    return out

# ---------------------------------------------------------------- thumbnails
OG = re.compile(r'<meta[^>]+>', re.I)
def grab_thumb(url):
    if not url or not url.startswith("http"):
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
        with urllib.request.urlopen(req, timeout=12) as r:
            raw = r.read(60000).decode("utf-8", "ignore")
        for m in re.finditer(r'<meta[^>]+>', raw, re.I):
            tag = m.group(0)
            if re.search(r'(property|name)\s*=\s*["\'](og:image|twitter:image|og:image:secure_url)', tag, re.I):
                cm = re.search(r'content\s*=\s*["\']([^"\']+)', tag, re.I)
                if cm:
                    img = cm.group(1).strip()
                    if img.startswith("//"):
                        img = "https:" + img
                    if img.startswith("http"):
                        return img
        return None
    except Exception:
        return None

# ---------------------------------------------------------------- merge + rank
def normalize_url(u):
    u = (u or "").split("?")[0].split("#")[0].rstrip("/").lower()
    return u

def main():
    log("=== Collecting via unified search wrapper ===")
    unified = collect_unified()
    log("=== Collecting HN 24h feed ===")
    hn = collect_hn()

    merged = {}
    # add HN first (fresh + ranked)
    for s in hn:
        key = normalize_url(s["url"])
        merged[key] = s
    # add unified, skip dup urls
    for s in unified:
        key = normalize_url(s["url"])
        if key in merged:
            # enrich summary if missing
            if not merged[key].get("summary") and s.get("summary"):
                merged[key]["summary"] = s["summary"]
            continue
        merged[key] = s

    stories = list(merged.values())
    for s in stories:
        if not s.get("summary"):
            s["summary"] = f"{s['source']} coverage: {s['title']}"
        s["tags"] = classify_tags(s)

    # score: engagement + recency
    for s in stories:
        eng = (s.get("upvotes", 0) or 0) * 2 + (s.get("comments", 0) or 0)
        rec = s.get("_recency", 1)
        s["_score"] = eng + rec * 5

    stories.sort(key=lambda x: x["_score"], reverse=True)
    top = stories[:15]

    # thumbnails (best effort) for selected
    log("=== Fetching thumbnails (best effort) ===")
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(grab_thumb, s["url"]): s for s in top}
        for f in as_completed(futs):
            try:
                futs[f]["thumbnail"] = f.result()
            except Exception:
                futs[f]["thumbnail"] = None

    # final structured records
    records = []
    for s in top:
        records.append({
            "title": s["title"],
            "url": s["url"],
            "summary": s["summary"],
            "thumbnail": s.get("thumbnail"),
            "source": s["source"],
            "date": s["date"],
            "upvotes": s.get("upvotes", 0),
            "comments": s.get("comments", 0),
            "tags": s["tags"],
            "hn_url": s.get("hn_url"),
        })

    output = {
        "generated_at": NOW.strftime("%Y-%m-%d %H:%M UTC"),
        "stats": {
            "reddit_threads": 0,
            "articles_scanned": len(stories),
            "subreddits_scanned": 0,
            "sources": {
                "unified_search": len(unified),
                "hacker_news_24h": len(hn),
            },
        },
        "stories": records,
    }

    # write data.json (task artifact)
    data_json = BASE / "data.json"
    with open(data_json, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    # write data/latest.json (dashboard)
    latest = DATA_DIR / "latest.json"
    with open(latest, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    log(f"Wrote {len(records)} stories -> {data_json.name} and data/latest.json")
    print(json.dumps({"stories": len(records), "sources": output["stats"]["sources"]},
                     ensure_ascii=False))

if __name__ == "__main__":
    main()
