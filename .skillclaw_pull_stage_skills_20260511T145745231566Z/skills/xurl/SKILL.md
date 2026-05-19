---
name: xurl
description: "Use when interacting with X/Twitter via xurl, the official X API CLI. Post, reply, quote, search, manage timelines, mentions, likes, reposts, bookmarks, follows, DMs, media upload, and raw v2 endpoint access. NOT for: non-Twitter social media, scheduled posting, or when Twitter/X UI is more efficient."
category: skills
---

---
name: xurl
description: Use when interacting with X/Twitter via xurl, the official X API CLI. Post, reply, quote, search, manage timelines, mentions, likes, reposts, bookmarks, follows, DMs, media upload, and raw v2 endpoint access. NOT for: non-Twitter social media, scheduled posting, or when Twitter/X UI is more efficient.
---

## Setup

Requires `xurl` CLI and X API credentials in environment:
bash
export X_API_KEY="your_api_key"
export X_API_SECRET="your_api_secret"
export X_ACCESS_TOKEN="your_access_token"
export X_ACCESS_SECRET="your_access_secret"


## Tools (xurl exposes these X API v2 resources)

| Resource   | Methods                          |
|-----------|----------------------------------|
| tweets    | create, search, show, delete     |
| users     | show, by-username                |
| timelines | home, user                      |
| likes     | create, remove                   |
| bookmarks | list, add, remove               |
| following | follow, unfollow                 |
| lists     | list, add-remove-member         |
| dms       | send, events-list               |
| media     | upload                           |

## Usage Examples

**Post a tweet:**
bash
xurl tweet create --text "Hello from xurl"
# Output: {"id": "1234567890", "text": "Hello from xurl", ...}


**Search tweets:**
bash
xurl tweet search --query "hermes agent" --max-results 10


**Reply to a tweet:**
bash
xurl tweet create --text "Great post!" --reply-to 1234567890


**Send a DM:**
bash
xurl dm send --recipient-id 9876543210 --text "Hello!"


**Upload media:**
bash
xurl media upload --path /path/to/image.jpg
# Returns media_id for use in tweet create --media-ids


## Raw API Access

Use `--raw` flag with any command to see the underlying API request:
bash
xurl timeline home --raw
xurl tweet show 1234567890 --raw


## Output Format

- Default: formatted text
- Use `--json` for raw JSON output (recommended for parsing)
- Use `--raw` to see the full HTTP request before execution

## Common Issues

- **401 Unauthorized**: Check API credentials are correctly set in environment
- **403 Forbidden**: App may lack required permissions (DM access requires elevated access)
- **Rate limiting**: X API v2 has per-endpoint rate limits; use `--dry-run` to validate without consuming quota
