#!/usr/bin/env python3
"""
Daily Anthropic & Claude Blog Learner
=====================================
Scrapes new articles from anthropic.com/engineering and claude.com/blog,
filters for agent-related content, extracts key insights,
and saves structured output for cronjob processing.

Focus areas: agent architecture, context engineering, tool use, 
multi-agent, managed agents, harness design, evals, coding agents.

Output: JSON with article list + summaries for cronjob to process.
"""

import json
import re
import sys
import time
import hashlib
import urllib.request
import urllib.error
from html.parser import HTMLParser
from datetime import datetime, timezone
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────
SOURCES = {
    "anthropic_engineering": {
        "url": "https://www.anthropic.com/engineering",
        "base": "https://www.anthropic.com",
        "type": "engineering",
    },
    "claude_blog_agents": {
        "url": "https://claude.com/blog/category/agents",
        "base": "https://claude.com",
        "type": "blog_agents",
    },
    "claude_blog_code": {
        "url": "https://claude.com/blog/category/claude-code",
        "base": "https://claude.com",
        "type": "blog_claude_code",
    },
}

# Agent-relevant keywords (case-insensitive matching)
AGENT_KEYWORDS = [
    "agent", "agents", "multi-agent", "agentic", "tool use", "tool-use",
    "context engineering", "context window", "tool selection", "tool search",
    "managed agents", "harness", "coding agent", "mcp", "model context protocol",
    "parallel agent", "subagent", "sub-agent", "delegate", "orchestrat",
    "autonomous", "long-running", "sandbox", "permission", "skill",
    "memory", "recall", "retrieval", "rag", "compaction", "compression",
]

# State file to track already-processed articles
STATE_FILE = Path.home() / ".hermes" / "scripts" / ".anthropic-learner-state.json"

# Output file for the cronjob prompt to read
OUTPUT_FILE = Path.home() / ".hermes" / "scripts" / ".anthropic-learner-output.json"


class LinkExtractor(HTMLParser):
    """Extract (href, text) pairs from HTML, filtering by pattern."""
    def __init__(self, base_url=""):
        super().__init__()
        self.links = []
        self._base = base_url
        self._current_href = None
        self._current_text = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for k, v in attrs:
                if k == "href":
                    self._current_href = v
                    self._current_text = []

    def handle_data(self, data):
        if self._current_href is not None:
            self._current_text.append(data.strip())

    def handle_endtag(self, tag):
        if tag == "a" and self._current_href is not None:
            text = " ".join(self._current_text).strip()
            href = self._current_href
            if href and not href.startswith("#") and not href.startswith("javascript"):
                if href.startswith("/"):
                    href = self._base + href
                self.links.append((href, text))
            self._current_href = None
            self._current_text = []


class ArticleExtractor(HTMLParser):
    """Extract main text content from an article page."""
    def __init__(self):
        super().__init__()
        self.in_article = False
        self.in_script = False
        self.in_style = False
        self.text_parts = []
        self._depth = 0

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag in ("script", "style", "nav", "header", "footer"):
            self.in_script = True
        if tag == "article" or attrs_dict.get("role") == "main":
            self.in_article = True
        if self.in_article:
            self._depth += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "nav", "header", "footer"):
            self.in_script = False
        if tag == "article":
            self.in_article = False
        if self.in_article and self._depth > 0:
            self._depth -= 1

    def handle_data(self, data):
        if not self.in_script and self.in_article:
            text = data.strip()
            if text:
                self.text_parts.append(text)

    def get_text(self, max_chars=8000):
        full = "\n".join(self.text_parts)
        if len(full) > max_chars:
            return full[:max_chars] + "\n...[truncated for learning extraction]"
        return full


def fetch_url(url, timeout=20):
    """Fetch URL content with basic error handling."""
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        print(f"WARN: Failed to fetch {url}: {e}", file=sys.stderr)
        return None


def extract_links(html, base_url=""):
    """Extract all links from HTML."""
    parser = LinkExtractor(base_url)
    try:
        parser.feed(html)
    except Exception:
        pass
    return parser.links


def is_agent_related(text):
    """Check if text contains agent-relevant keywords."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in AGENT_KEYWORDS)


def article_id(url):
    """Generate a stable ID from URL."""
    return hashlib.md5(url.encode()).hexdigest()[:12]


def load_state():
    """Load previously processed article IDs."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"processed": [], "last_run": None}


def save_state(state):
    """Save processed article IDs."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    # Keep only last 500 processed IDs
    state["processed"] = state["processed"][-500:]
    STATE_FILE.write_text(json.dumps(state, indent=2))


def main():
    state = load_state()
    processed_ids = set(state.get("processed", []))
    new_articles = []

    for source_name, source_cfg in SOURCES.items():
        print(f"Fetching {source_name}: {source_cfg['url']}")
        html = fetch_url(source_cfg["url"])
        if not html:
            continue

        links = extract_links(html, source_cfg["base"])
        print(f"  Found {len(links)} links")

        for href, text in links:
            # Filter: only article-like URLs
            if not href or len(text) < 10:
                continue
            # Skip non-article URLs
            skip_patterns = ["/jobs", "/contact", "/login", "/pricing",
                           "/legal", "/privacy", "/terms", "/careers",
                           "#", "javascript:", "mailto:"]
            if any(p in href.lower() for p in skip_patterns):
                continue
            # Must be from same domain
            if source_cfg["base"] not in href and not href.startswith(source_cfg["base"]):
                continue

            aid = article_id(href)
            if aid in processed_ids:
                continue

            # Check if agent-related
            if not is_agent_related(text):
                # Still process if it's from the agents/claude-code category pages
                if source_cfg["type"] not in ("blog_agents", "blog_claude_code"):
                    continue

            print(f"  New article: {text[:60]}... -> {href}")
            new_articles.append({
                "id": aid,
                "url": href,
                "title": text[:200],
                "source": source_name,
                "source_type": source_cfg["type"],
                "agent_related": is_agent_related(text),
            })
            processed_ids.add(aid)

    # Fetch and extract content for agent-related new articles (limit 5 per run)
    agent_articles = [a for a in new_articles if a["agent_related"]][:5]
    
    for article in agent_articles:
        print(f"Extracting: {article['title'][:60]}")
        html = fetch_url(article["url"])
        if not html:
            article["content_preview"] = "[Failed to fetch content]"
            continue
        
        extractor = ArticleExtractor()
        try:
            extractor.feed(html)
            content = extractor.get_text(max_chars=6000)
        except Exception as e:
            content = f"[Extraction error: {e}]"
        
        article["content_preview"] = content

    # Save state
    state["processed"] = list(processed_ids)
    save_state(state)

    # Write output for cronjob prompt
    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_new": len(new_articles),
        "agent_related_new": len(agent_articles),
        "articles": new_articles,
        "agent_articles_with_content": agent_articles,
    }
    
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    
    # Print summary for cronjob
    print(f"\n=== Daily Anthropic Learner Summary ===")
    print(f"Total new articles found: {len(new_articles)}")
    print(f"Agent-related (with content): {len(agent_articles)}")
    for a in agent_articles:
        print(f"  - [{a['source_type']}] {a['title'][:80]}")
        print(f"    URL: {a['url']}")
        if a.get("content_preview"):
            preview = a["content_preview"][:200].replace("\n", " ")
            print(f"    Preview: {preview}...")
    print(f"Output: {OUTPUT_FILE}")
    
    # Also print the JSON for easy parsing
    print(f"\n---JSON_OUTPUT---")
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
