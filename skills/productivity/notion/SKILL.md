---
name: notion
description: "Use when creating and managing Notion pages, databases, and blocks via the API. Search, create, update, and query Notion workspaces directly from terminal. NOT for: non-Notion workspaces, complex database queries, or when Notion app UI is more efficient."
category: productivity
---

## Purpose

Create, read, update, and query Notion pages, databases, and blocks programmatically via the official Notion API. Use when you need to automate content management in Notion, sync data between tools, build custom dashboards, batch-create pages from templates, or integrate Notion with other systems via curl.

## Why This Works

**1. Official REST API with Structured JSON.** Notion's API (https://api.notion.com/v1/) uses standardized JSON request/response schemas — pages become structured `page` objects with typed properties, databases support filtering/sorting queries, and blocks compose into rich documents. This makes it straightforward to build automation pipelines without reverse-engineering.

**2. The R-I-A-E (Read-Identify-Apply-Emplace) Pattern.** Notion databases require a specific workflow: you must first READ the database schema (to see property types and options), IDENTIFY which properties to use, then APPLY the correct API endpoint, and EMPLACE properly formatted JSON. This pattern prevents the most common source of API errors — wrong property types.

**3. Block-Based Document Construction.** Every Notion page is a tree of block objects (paragraphs, headings, lists, embeds). You construct pages by nesting blocks, which maps naturally to JSON trees. Master block composition and you can generate any page structure programmatically.

## Anti-Patterns

**Anti-Pattern 1: Guessing Property Types.** The most common Notion API error is using the wrong JSON structure for database properties. Always fetch a database's schema first before creating pages — property types (title, rich_text, select, multi_select, etc.) require specific JSON formats.

**Anti-Pattern 2: Hardcoding Integration Tokens.** Passing `secret_xxx` tokens directly in scripts exposes credentials in version control and is hard to rotate. Use environment variables (`NOTION_TOKEN`) or a secret manager.

**Anti-Pattern 3: Ignoring Pagination.** The Notion API paginates list responses at 100 items per call. Not handling `has_more` and `next_cursor` silently truncates results. Always implement the pagination loop.

## Examples

**Good:** Fetch a database schema to discover property types before writing data:
```bash
NOTION_TOKEN="your_integration_token"
DATABASE_ID="your_database_id"

curl -s "https://api.notion.com/v1/databases/$DATABASE_ID" \
  -H "Authorization: Bearer $NOTION_TOKEN" \
  -H "Notion-Version: 2022-06-28" \
  | jq '.properties | to_entries[] | {name: .key, type: .value.type}'
```
Returns something like: `{"name": "Name", "type": "title"}, {"name": "Status", "type": "select"}` — critical for knowing what JSON to send.

**Good:** Create a database page with correctly typed properties:
```bash
curl -s "https://api.notion.com/v1/pages" \
  -H "Authorization: Bearer $NOTION_TOKEN" \
  -H "Notion-Version: 2022-06-28" \
  -H "Content-Type: application/json" \
  -d '{
    "parent": { "database_id": "'$DATABASE_ID'" },
    "properties": {
      "Name": {
        "title": [{ "text": { "content": "My New Task" } }]
      },
      "Status": {
        "select": { "name": "In Progress" }
      },
      "Due Date": {
        "date": { "start": "2026-06-15" }
      },
      "Priority": {
        "select": { "name": "High" }
      }
    }
  }' | jq '.'
```

**Good:** Query a database with filters and pagination (complete example):
```bash
echo "[" > /tmp/results.json
has_more=true
next_cursor=""
while [ "$has_more" = "true" ]; do
  body='{"filter":{"property":"Status","select":{"equals":"In Progress"}}}'
  [ -n "$next_cursor" ] && body=$(echo "$body" | jq ". + {\"start_cursor\": \"$next_cursor\"}")
  resp=$(curl -s "https://api.notion.com/v1/databases/$DATABASE_ID/query" \
    -H "Authorization: Bearer $NOTION_TOKEN" \
    -H "Notion-Version: 2022-06-28" \
    -H "Content-Type: application/json" \
    -d "$body")
  echo "$resp" | jq '.results' | jq -c '.[]' >> /tmp/results.json
  has_more=$(echo "$resp" | jq -r '.has_more')
  next_cursor=$(echo "$resp" | jq -r '.next_cursor // ""')
done
echo "]" | jq -s 'add' /tmp/results.json > /tmp/all_results.json
echo "Total results: $(jq '. | length' /tmp/all_results.json)"
```

**Good:** Create a page with rich content (blocks):
```bash
curl -s "https://api.notion.com/v1/pages" \
  -H "Authorization: Bearer $NOTION_TOKEN" \
  -H "Notion-Version: 2022-06-28" \
  -H "Content-Type: application/json" \
  -d '{
    "parent": { "type": "page_id", "page_id": "'$PAGE_ID'" },
    "properties": { "title": { "title": [{ "text": { "content": "Report" } }] } },
    "children": [
      { "object": "block", "type": "heading_2", "heading_2": { "rich_text": [{ "text": { "content": "Summary" } }] } },
      { "object": "block", "type": "paragraph", "paragraph": { "rich_text": [{ "text": { "content": "Here is the report content." } }] } },
      { "object": "block", "type": "bulleted_list_item", "bulleted_list_item": { "rich_text": [{ "text": { "content": "Key finding 1" } }] } },
      { "object": "block", "type": "bulleted_list_item", "bulleted_list_item": { "rich_text": [{ "text": { "content": "Key finding 2" } }] } },
      { "object": "block", "type": "divider", "divider": {} },
      { "object": "block", "type": "callout", "callout": {
        "rich_text": [{ "text": { "content": "Action needed" } }],
        "icon": { "emoji": "⚠️" }
      } }
    ]
  }' | jq '.'
```

**Bad:** Creating a page with incorrect property types:
```bash
# WRONG — "Status" is a select type, not a string
curl -s "https://api.notion.com/v1/pages" \
  -H "Authorization: Bearer $NOTION_TOKEN" \
  -H "Notion-Version: 2022-06-28" \
  -H "Content-Type: application/json" \
  -d '{
    "parent": { "database_id": "'$DATABASE_ID'" },
    "properties": {
      "Name": { "title": [{ "text": { "content": "Task" } }] },
      "Status": "In Progress"  ###### WRONG — select needs { "select": { "name": "..." } }
    }
  }'

# RIGHT — property types must match the database schema
curl -s "https://api.notion.com/v1/pages" \
  -H "Authorization: Bearer $NOTION_TOKEN" \
  -H "Notion-Version: 2022-06-28" \
  -H "Content-Type: application/json" \
  -d '{
    "parent": { "database_id": "'$DATABASE_ID'" },
    "properties": {
      "Name": { "title": [{ "text": { "content": "Task" } }] },
      "Status": { "select": { "name": "In Progress" } }
    }
  }'
```

## Property Types Quick Reference

| Property Type | JSON Structure |
|---------------|----------------|
| title | `{"title": [{"text": {"content": "..."}}]}` |
| rich_text | `{"rich_text": [{"text": {"content": "..."}}]}` |
| select | `{"select": {"name": "..."}}` |
| multi_select | `{"multi_select": [{"name": "..."}]}` |
| date | `{"date": {"start": "2026-01-01", "end": null}}` |
| number | `{"number": 42}` |
| checkbox | `{"checkbox": true}` |
| email | `{"email": "user@example.com"}` |
| phone | `{"phone_number": "+1234567890"}` |
| url | `{"url": "https://example.com"}` |
| relation | `{"relation": [{"id": "page-id"}]}` |
| created_time | *(read-only, auto-set)* |
| last_edited_time | *(read-only, auto-updated)* |

## Common Block Types

| Block Type | Key Field |
|------------|-----------|
| paragraph | `paragraph.rich_text` |
| heading_1/2/3 | `heading_1.rich_text` (etc.) |
| bulleted_list_item | `bulleted_list_item.rich_text` |
| numbered_list_item | `numbered_list_item.rich_text` |
| to_do | `to_do.rich_text` + `to_do.checked` |
| toggle | `toggle.rich_text` |
| callout | `callout.rich_text` + `callout.icon` |
| divider | `divider: {}` |
| code | `code.rich_text` + `code.language` |
| image | `image.external.url` or `image.type` |
| embed | `embed.url` |
| bookmark | `bookmark.url` |
| quote | `quote.rich_text` |

## When NOT to Use

- **When the Notion app UI is faster** — for one-off note creation, manual entry is quicker than API calls
- **For non-Notion workspaces** — this skill covers Notion API only, not Airtable, Coda, or other tools
- **Complex relational database queries** — Notion's API has limited join/aggregation capabilities; use a real database instead
- **Real-time collaboration** — Notion API has rate limits (3 requests per second); use Webhooks or the native app for live sync
- **Importing massive data volumes** — Notion API has a 100-item pagination limit and no bulk import endpoint; break into batches
- **When you need rich text formatting beyond bold/italic** — Notion API supports basic annotations only; for complex layouts, use the Notion app directly

## Cross-References

- **google-workspace** (skills/integration/google-workspace/SKILL.md): Alternative document management and automation via Google APIs
- **obsidian** (skills/note-taking/obsidian/SKILL.md): Local-first note-taking alternative that pairs well with version control
- **siyuan** (skills/siyuan/SKILL.md): Self-hosted knowledge base alternative with local API access
- **scrapling** (skills/optional-skills/scrapling/SKILL.md): Web scraping to programmatically populate Notion databases with external data
