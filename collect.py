#!/usr/bin/env python3
"""
AI News Dashboard — Data Collector
Fetches AI news from Reddit, Hacker News, and Google Trends.
Outputs data/latest.json for the dashboard.

Usage: python collect.py
"""

import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

DASHBOARD_DIR = Path(__file__).parent
DATA_DIR = DASHBOARD_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

AI_SUBREDDITS = [
    "artificial",
    "MachineLearning",
    "singularity",
    "LocalLLaMA",
    "ChatGPT",
    "OpenAI",
    "StableDiffusion",
]

AI_KEYWORDS = [
    "ai", "artificial intelligence", "machine learning", "llm", "gpt", "claude",
    "gemini", "openai", "anthropic", "deepseek", "mistral", "llama", "diffusion",
    "transformer", "neural", "deep learning", "chatbot", "copilot", "agent",
    "fine-tune", "inference", "reasoning", "multimodal", "rag", "embedding",
    "hugging face", "nvidia", "gpu", "tpu", "benchmark", "agi", "alignment",
    "safety", "regulation", "open source", "model", "training", "hermes",
]


def fetch_json(url, timeout=15):
    """Fetch JSON from a URL."""
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"  ⚠ Failed to fetch {url}: {e}", file=sys.stderr)
        return None


def fetch_reddit(subreddit, limit=10):
    """Fetch top posts from a subreddit."""
    url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}&raw_json=1"
    data = fetch_json(url)
    if not data or "data" not in data:
        return []

    posts = []
    for child in data["data"]["children"]:
        p = child["data"]
        if p.get("stickied"):
            continue
        posts.append({
            "title": p.get("title", ""),
            "url": p.get("url", ""),
            "permalink": f"https://reddit.com{p.get('permalink', '')}",
            "upvotes": p.get("ups", 0),
            "comments": p.get("num_comments", 0),
            "source": f"r/{subreddit}",
            "date": datetime.fromtimestamp(p.get("created_utc", 0), tz=timezone.utc).strftime("%Y-%m-%d"),
            "selftext": (p.get("selftext", "") or "")[:300],
        })
    return posts


def fetch_hackernews(limit=15):
    """Fetch top HN stories and filter for AI-related ones."""
    data = fetch_json("https://hacker-news.firebaseio.com/v0/topstories.json")
    if not data:
        return []

    stories = []
    for story_id in data[:50]:  # Check top 50, filter for AI
        item = fetch_json(f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json")
        if not item:
            continue
        title = item.get("title", "")
        title_lower = title.lower()
        # Check if AI-related
        if any(kw in title_lower for kw in AI_KEYWORDS):
            stories.append({
                "title": title,
                "url": item.get("url", f"https://news.ycombinator.com/item?id={story_id}"),
                "upvotes": item.get("score", 0),
                "comments": item.get("descendants", 0),
                "source": "Hacker News",
                "date": datetime.fromtimestamp(item.get("time", 0), tz=timezone.utc).strftime("%Y-%m-%d"),
            })
        if len(stories) >= limit:
            break
    return stories


def fetch_google_trends():
    """Fetch trending AI topics from Google Trends RSS."""
    # Google Trends RSS for AI topic
    url = "https://trends.google.com/trending/rss?geo=US&category=5"  # Science/Tech
    try:
        req = urllib.request.Request(url, headers={"User-Agent": HEADERS["User-Agent"]})
        with urllib.request.urlopen(req, timeout=15) as resp:
            xml_data = resp.read().decode()
        # Simple XML parsing
        import xml.etree.ElementTree as ET
        root = ET.fromstring(xml_data)
        ns = {"ht": "https://trends.google.com/trending/rss"}
        trends = []
        for item in root.findall(".//item"):
            title = item.findtext("title", "")
            traffic = item.findtext("ht:approx_traffic", namespaces=ns, default="")
            link = item.findtext("link", "")
            title_lower = title.lower()
            if any(kw in title_lower for kw in AI_KEYWORDS):
                trends.append({
                    "title": title,
                    "url": link,
                    "source": "Google Trends",
                    "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    "tags": ["trending"],
                    "traffic": traffic,
                })
        return trends
    except Exception as e:
        print(f"  ⚠ Google Trends fetch failed: {e}", file=sys.stderr)
        return []


def classify_tags(story):
    """Auto-classify a story into tags based on keywords."""
    text = (story.get("title", "") + " " + story.get("selftext", "")).lower()
    tags = []
    tag_map = {
        "LLMs": ["llm", "gpt", "claude", "gemini", "mistral", "llama", "language model", "chatgpt"],
        "Vision": ["image", "vision", "stable diffusion", "midjourney", "dall-e", "flux", "video generation"],
        "Open Source": ["open source", "open-source", "hugging face", "github", "weights", "gguf"],
        "Research": ["paper", "arxiv", "benchmark", "study", "research", "findings"],
        "Agents": ["agent", "agentic", "autonomous", "hermes", "copilot", "assistant"],
        "Industry": ["startup", "funding", "acquisition", "ipo", "valuation", "revenue"],
        "Regulation": ["regulation", "safety", "alignment", "policy", "ethics", "bias"],
        "Hardware": ["gpu", "nvidia", "tpu", "chip", "hardware", "cuda"],
        "Tools": ["api", "sdk", "framework", "library", "tool", "platform"],
        "News": ["announce", "launch", "release", "update", "new", "introducing"],
    }
    for tag, keywords in tag_map.items():
        if any(kw in text for kw in keywords):
            tags.append(tag)
    return tags[:3] if tags else ["AI"]


def rank_and_select(all_stories, max_stories=10):
    """Rank stories by engagement and select top N."""
    # Sort by upvotes * 2 + comments (engagement score)
    for s in all_stories:
        s["_score"] = (s.get("upvotes", 0) or 0) * 2 + (s.get("comments", 0) or 0)
    all_stories.sort(key=lambda x: x["_score"], reverse=True)

    # Deduplicate by title similarity
    seen_titles = set()
    unique = []
    for s in all_stories:
        key = s["title"].lower()[:50]
        if key not in seen_titles:
            seen_titles.add(key)
            s["tags"] = classify_tags(s)
            unique.append(s)
    return unique[:max_stories]


def main():
    print("📡 AI News Dashboard — Data Collection")
    print("=" * 50)

    all_stories = []
    reddit_threads = 0
    articles_scanned = 0

    # 1. Fetch Reddit
    print("\n🔴 Fetching Reddit AI subreddits...")
    for sub in AI_SUBREDDITS:
        print(f"  → r/{sub}...")
        posts = fetch_reddit(sub, limit=8)
        reddit_threads += len(posts)
        all_stories.extend(posts)
        print(f"    Got {len(posts)} posts")

    articles_scanned += reddit_threads

    # 2. Fetch Hacker News
    print("\n🟠 Fetching Hacker News (AI-filtered)...")
    hn_stories = fetch_hackernews(limit=10)
    articles_scanned += 50  # We checked top 50
    all_stories.extend(hn_stories)
    print(f"  Got {len(hn_stories)} AI stories")

    # 3. Fetch Google Trends
    print("\n🟢 Fetching Google Trends...")
    trends = fetch_google_trends()
    articles_scanned += len(trends)
    all_stories.extend(trends)
    print(f"  Got {len(trends)} AI trends")

    # 4. Rank and select
    print("\n📊 Ranking and selecting top stories...")
    top_stories = rank_and_select(all_stories, max_stories=10)
    print(f"  Selected {len(top_stories)} stories")

    # 5. Write output
    output = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "stats": {
            "reddit_threads": reddit_threads,
            "articles_scanned": articles_scanned,
            "subreddits_scanned": len(AI_SUBREDDITS),
        },
        "stories": top_stories,
    }

    output_path = DATA_DIR / "latest.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Wrote {len(top_stories)} stories to {output_path}")
    print(f"   Reddit threads: {reddit_threads}")
    print(f"   Articles scanned: {articles_scanned}")
    return output


if __name__ == "__main__":
    main()
