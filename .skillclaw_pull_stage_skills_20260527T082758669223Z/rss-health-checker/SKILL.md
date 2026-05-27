---
name: rss-health-checker
description: "Check RSS/Atom feed health without feedparser — uses httpx + xml.etree (stdlib). Detects WAF/JS challenges (AliCloud, Cloudflare) returning HTTP 200 + HTML, classifies 7 statuses, handles CDATA content, runs concurrent checks. Use when: cronjob RSS sources fail, replacing feedparser, pre-flight health gate for aggregator scripts. NOT for: general web scraping, parsing full article content."
category: general
---

# RSS Health Checker

Check RSS/Atom feed health using only `httpx` + Python stdlib `xml.etree.ElementTree`. No external dependencies required.

## Environment Constraints

- **Available**: `httpx`, `yaml`, Python stdlib (`xml.etree.ElementTree`, `re`, `asyncio`)
- **NOT available**: `feedparser`, `lxml`, `requests`
- Use `httpx.AsyncClient` for async HTTP, `xml.etree.ElementTree` for XML parsing

> **feedparser 不可用**: `hermes-agent` venv 中未安装 `feedparser`，必须用 `httpx` + `xml.etree.ElementTree` 替代。依赖它会导致 cronjob 失败。

## HTTP Request Configuration

python
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/rss+xml, application/atom+xml, application/xml, text/xml, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}


> **关键**: 必须使用完整的 Chrome UA。RSS 源常见反爬，Server 端根据 UA 判断是否返回真实 Feed。

## Core Parsing Utilities

python
import re
import xml.etree.ElementTree as ET

CDATA_RE = re.compile(r'<!\[CDATA\[(.*?)\]\]>', re.DOTALL)

def strip_cdata(text: str) -> str:
    """xml.etree does NOT auto-strip CDATA sections — must clean manually."""
    return CDATA_RE.sub(r'\1', text, flags=re.DOTALL) or text

def safe_text(el: ET.Element | None) -> str:
    """Extract text from element, handling CDATA wrapping."""
    if el is None:
        return ''
    raw = (el.text or '').strip()
    return strip_cdata(raw)


> **关键**: `xml.etree.ElementTree` 不会自动剥离 `<![CDATA[...]]>`，必须 regex 处理。

## WAF Detection (Critical)

Alibaba Cloud WAF (and similar) returns **HTTP 200 + content-type: text/html** for blocked requests — this is NOT a valid RSS feed. Always check `content-type` header before parsing.

python
def is_waf_block(resp_text: str, content_type: str, status_code: int) -> bool:
    """Alibaba Cloud WAF fingerprint: HTTP 200 + text/html = JS challenge page."""
    if status_code == 200 and content_type.startswith('text/html'):
        return True
    # Generic WAF signatures
    waf_signatures = ['jsluid', 'alicdn', '__cf_chl_jschl', 'challenges.cloudflare']
    return any(sig in resp_text for sig in waf_signatures)


> **最常见错误**: 看到 HTTP 200 就认为「正常」，但 WAF 返回 200 + HTML 页面。
> 阿里云 WAF 特征: `jsluid` cookie 存在 + `<title>安全验证</title>` + JS challenge 脚本。

**Rule**: HTTP 200 + `text/html` = blocked (not `parse_error`, not `healthy`).

## Status Classification (7 states)

| Status | Condition |
|--------|-----------|
| `healthy` | HTTP 200 + valid XML + has entries |
| `degraded` | Valid RSS but feed length < 500 bytes (likely truncated) |
| `waf_blocked` | HTTP 200 + `text/html` OR WAF signature detected |
| `http_error` | Non-200 HTTP response (4xx/5xx) |
| `timeout` | Request timeout (> 10s) |
| `unreachable` | Connection error, DNS failure |
| `parse_error` | HTTP 200 + correct content-type but invalid XML structure |
| `empty` | Valid XML but no `<item>` or `<entry>` elements |
| `redirect_loop` | Redirect loop (follow_redirects exceeds limit) |

## Implementation

python
import asyncio
import httpx
import xml.etree.ElementTree as ET
from typing import TypedDict, Literal

class FeedStatus(TypedDict):
    url: str
    status: Literal['healthy', 'degraded', 'waf_blocked', 'http_error', 'timeout', 'unreachable', 'parse_error', 'empty', 'redirect_loop']
    count: int | None
    title: str | None
    last_updated: str | None
    sample: str | None
    code: int | None

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/rss+xml, application/atom+xml, application/xml, text/xml, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}

def find_feed_items(root: ET.Element) -> list[ET.Element]:
    """Find items/entries in RSS 2.0 or Atom feed using flexible XPath."""
    # Try direct children first
    items = root.findall('.//item') or root.findall('.//entry')
    if items:
        return items
    # Try nested structure (RSS channel)
    items = root.findall('.//channel/item') or root.findall('.//feed/entry')
    return items

def parse_feed_xml(xml_bytes: bytes) -> dict:
    """Parse RSS 2.0 or Atom feed, return metadata dict."""
    root = ET.fromstring(xml_bytes)
    tag = root.tag.lower()

    if "rss" in tag:
        channel = root.find("channel")
        title = safe_text(channel.find("title")) if channel is not None else ""
        items = find_feed_items(channel) if channel is not None else []
        updated = safe_text(channel.find("lastBuildDate")) if channel is not None else ""
        feed_type = "rss"
    elif "feed" in tag:  # Atom
        title = safe_text(root.find("title"))
        items = find_feed_items(root)
        updated = safe_text(root.find("updated"))
        feed_type = "atom"
    else:
        return {"title": "", "entry_count": 0, "last_updated": "", "feed_type": "unknown", "error": "Unknown feed format"}

    return {
        "title": title,
        "entry_count": len(items),
        "last_updated": updated,
        "feed_type": feed_type,
        "error": None
    }

async def check_feed(url: str, timeout: float = 10.0) -> FeedStatus:
    """Check health of a single RSS/Atom feed."""
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout,
            headers=HEADERS
        ) as client:
            response = await client.get(url)
    except httpx.TimeoutException:
        return {"url": url, "status": "timeout", "count": None, "title": None, "last_updated": None, "sample": None, "code": None}
    except httpx.RedirectError:
        return {"url": url, "status": "redirect_loop", "count": None, "title": None, "last_updated": None, "sample": "Too many redirects", "code": None}
    except Exception as e:
        return {"url": url, "status": "unreachable", "count": None, "title": None, "last_updated": None, "sample": str(e)[:200], "code": None}

    content_type = response.headers.get("content-type", "").lower()

    # WAF detection: 200 + HTML content-type = blocked
    if is_waf_block(response.text, content_type, response.status_code):
        return {
            "url": url, "status": "waf_blocked",
            "count": None, "title": None, "last_updated": None,
            "sample": response.text[:200], "code": 200
        }

    # HTTP error
    if response.status_code >= 400:
        return {
            "url": url, "status": "http_error",
            "count": None, "title": None, "last_updated": None,
            "sample": response.text[:500], "code": response.status_code
        }

    # Parse XML
    try:
        data = parse_feed_xml(response.content)
    except ET.ParseError:
        return {
            "url": url, "status": "parse_error",
            "count": None, "title": None, "last_updated": None,
            "sample": response.text[:200], "code": 200
        }

    if data.get("error"):
        return {
            "url": url, "status": "parse_error",
            "count": 0, "title": None, "last_updated": None,
            "sample": data["error"], "code": 200
        }

    entry_count = data.get("entry_count", 0)

    # Empty feed: valid XML but no items
    if entry_count == 0:
        return {
            "url": url, "status": "empty",
            "count": 0, "title": data.get("title"),
            "last_updated": data.get("last_updated"),
            "sample": None, "code": 200
        }

    # Degraded: feed < 500 bytes (likely truncated)
    if len(response.content) < 500:
        return {
            "url": url, "status": "degraded",
            "count": entry_count, "title": data.get("title"),
            "last_updated": data.get("last_updated"),
            "sample": None, "code": 200
        }

    return {
        "url": url, "status": "healthy",
        "count": entry_count, "title": data.get("title"),
        "last_updated": data.get("last_updated"),
        "sample": None, "code": 200
    }

async def check_all_feeds(
    feeds: dict[str, str],
    concurrency: int = 5
) -> list[FeedStatus]:
    """Check multiple feeds concurrently with semaphore limit."""
    sem = asyncio.Semaphore(concurrency)

    async def limited(name: str, url: str) -> FeedStatus:
        async with sem:
            return await check_feed(url)

    return await asyncio.gather(*[
        limited(name, url) for name, url in feeds.items()
    ])


## Usage Examples

### Basic Usage

python
FEEDS = {
    "freebuf": "https://www.freebuf.com/feed",
    "嘶嗒": "https://www.4hou.com/feed",
    "先知": "https://xz.aliyun.com/feed",
    "安全客": "https://www.anquanke.com/feed/rss.xml",
    "SecWiki": "https://www.sec-wiki.com/feed",
    "NESE": "https://nese.steelmind.io/feed",
}

async def main():
    results = await check_all_feeds(FEEDS)
    for r in results:
        print(f"[{r['status']:12}] {r['url']}")
    
    unhealthy = [r for r in results if r["status"] != "healthy"]
    if unhealthy:
        print(f"\n{len(unhealthy)} unhealthy feed(s)")

if __name__ == "__main__":
    asyncio.run(main())


### Cronjob Health Gate

python
async def health_gate():
    results = await check_all_feeds(FEEDS)
    failures = [r for r in results if r["status"] not in ("healthy", "degraded")]
    if failures:
        print("Health check failed:")
        for f in failures:
            print(f"  - {f['url']}: {f['status']}")
        return False
    return True


## Known Feed Sources

### Known Healthy Feeds (for validation)

| Source | URL | Notes |
|--------|-----|-------|
| BBC Tech | https://feeds.bbci.co.uk/news/technology/rss.xml | Stable reference feed |
| The Register | https://www.theregister.com/headlines.rss | Stable reference feed |
| Schneier on Security | https://www.schneier.com/feed/atom/ | Stable reference feed |

If these return `parse_error`, check Python version or xml.etree environment.

### Known WAF-Blocked Sources

| Source | WAF Type |
|--------|----------|
| freebuf.com | 阿里云 WAF (`jsluid` cookie) |
| solidot.org | Intermittent 403 |
| thehackernews.com | Cloudflare JS Challenge |

> 遇到 WAF block 时，建议从 Feed 列表中移除该源，或记录为 degraded 而非 failure。

## Testing Notes

python
test_cases = [
    ("rss_healthy", RSS_2_0_XML, 200, "text/xml", "healthy"),
    ("atom_healthy", ATOM_XML, 200, "application/atom+xml", "healthy"),
    ("http_404", "Not Found", 404, "text/html", "http_error"),
    ("waf_blocked_is_not_parse_error", WAF_HTML_CHALLENGE, 200, "text/html", "waf_blocked"),
    ("parse_error", "<not xml>not valid xml</not>", 200, "text/xml", "parse_error"),
    ("empty_feed", EMPTY_RSS, 200, "text/xml", "empty"),
    ("timeout", None, None, None, "timeout"),
]


> **Note**: WAF test fixture must contain actual WAF HTML content (e.g., `var a=eval(...)` or `<title>安全验证</title>`), not just arbitrary HTML, otherwise content-type checking cannot be properly validated.

## Use Cases

- **Cronjob Prerun**: 在抓取安全资讯前，先检查所有 RSS 源状态，跳过不可用源
- **批量源验证**: 一次检查 10+ 个 RSS 源，输出表格
- **持续监控**: 定期检查，记录源健康趋势（健康率下降 → 触发告警）
- **Feed Parsing in hermes-agent**: Replace feedparser dependency in venv
