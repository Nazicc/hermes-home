---
name: coze-studio-api-debugging
description: "Debug coze-studio (localhost:8888) workflow integration — PAT vs session auth, API endpoint mismatches, and MySQL inspection when the API returns 'not found'"
category: general
---

# coze-studio API Debugging

## Environment
- coze-studio running at `http://localhost:8888` (Docker)
- MySQL: host=coze-mysql, port=3306, db=opencoze, user=coze, password=coze123
  - Credentials stored in `/Users/can/coze-studio/docker/.env` — macOS SIP/privacy protection may redact them to `***` when read from outside the container
  - Fallback: check `MYSQL_PASSWORD` default in `docker/docker-compose.yml` — default is `coze123`
  - Alternative: inspect container env directly: `docker exec coze-mysql printenv MYSQL_PASSWORD`
- Redis: host=coze-redis, port=6379
- PAT auth: Bearer token via `Authorization: Bearer <PAT>` header

## Key Distinction: workflow_run vs chatflow

coze-studio has two workflow types with different API endpoints — **the most common source of "not found" errors**:

| mode | Type | Endpoint | Auth | Body Fields |
|------|------|----------|------|-------------|
| 0 | Workflow (blocking) | `POST /v1/workflow/run` | PAT | `workflow_id`, `parameters` |
| 3 | ChatFlow (streaming) | `POST /v1/workflows/chat` | PAT | `workflow_id`, `query` |

> ⚠️ Using a chatflow ID (mode=3) with `/v1/workflow/run` returns "not found". Using a workflow ID (mode=0) with `/v1/workflows/chat` also returns "not found".

## API Endpoints

### Works with PAT (Bearer token)

bash
# Workflow execution (mode=0)
POST http://localhost:8888/v1/workflow/run
Body: {"workflow_id": "<id>", "parameters": {"<input_key>": "<value>"}, "is_delete_process": false}

# ChatFlow execution (mode=3)
POST http://localhost:8888/v1/workflows/chat
Body: {"workflow_id": "<id>", "query": "<input>", "stream": false}


### Does NOT work with PAT

bash
GET http://localhost:8888/v1/workflows  # List endpoint — requires session cookie, not PAT


> ❌ **Not `/v1/workflows` for execution**: The list endpoint requires session-based auth.

## MySQL Debugging (Authoritative Source)

When the API returns "not found", query MySQL directly to determine if the workflow exists:

bash
# Connect to coze-studio MySQL container
docker exec coze-mysql mysql -ucoze -pcoze123 opencoze


### Key Tables

**`workflow_meta`** — Master record
- `mode`: 0=Workflow, 3=ChatFlow
- `status`: 0=Not published, 1=Published, 3=Archived/deleted (check `DESC workflow_meta;` for full enum)
- `latest_version`: points to latest `workflow_version.id` (NULL if never published)

**`workflow_version`** — Published versions (canvas JSON, input/output params)
- Fields: id, workflow_id, version, version_description, canvas, input_params, output_params, creator_id, status, create_time, update_time

**`workflow_draft`** — Draft versions (join via `workflow_id` to `workflow_meta.id`)

### Useful Queries

sql
-- List all workflows with mode and status
SELECT id, name, status, mode, latest_version FROM workflow_meta;

-- Check workflow by ID
SELECT id, name, status, mode, latest_version FROM workflow_meta WHERE id = <workflow_id>;

-- Check workflow by name pattern
SELECT id, name, status, mode, latest_version FROM workflow_meta WHERE name LIKE '%keyword%';

-- Check workflow versions
SELECT id, workflow_id, version, status FROM workflow_version LIMIT 5;

-- Describe table schema
DESC workflow_meta;
DESC workflow_version;


### MySQL Quick Reference

bash
# List all tables
docker exec coze-mysql mysql -ucoze -pcoze123 opencoze -e "SHOW TABLES;"

# Check workflow_meta
docker exec coze-mysql mysql -ucoze -pcoze123 opencoze -e "SELECT id, name, status, mode, latest_version FROM workflow_meta;"

# Describe a table schema
docker exec coze-mysql mysql -ucoze -pcoze123 opencoze -e "DESC <table_name>;"


## Debugging "Workflow Not Found"


1. **Try the other endpoint** — if `POST /v1/workflow/run` fails, try `POST /v1/workflows/chat` (and vice versa)
2. **Query MySQL directly** — check if the workflow ID exists in `workflow_meta.id`
3. **If ID doesn't exist in DB**: workflow may belong to a different coze-studio deployment (cloud vs self-hosted), or hasn't been saved/published to this instance
4. **If ID exists in DB but API says not found**: verify:
   - The correct endpoint is used (workflow vs chatflow by mode)
   - The workflow has a `latest_version` (published version exists)
   - The workflow status is `1` (published), not `0` (draft) or `3` (archived)

## Root Causes Observed

- **Wrong endpoint**: Using `/v1/workflow/run` for mode=3 workflows, or `/v1/workflows/chat` for mode=0 workflows
- **Workflow in wrong deployment**: ID from cloud coze-studio or different local instance
- **Unpublished workflow**: `status != 1` or `latest_version` is NULL
- **Missing PAT**: token not included in request body or wrong Authorization header
- **Confusing list endpoint with execution**: `/v1/workflows` is for listing, not running
- **Not a workflow ID**: The ID could be a conversation ID, agent ID, or app ID from a different entity type
- **Wrong deployment instance**: Check if workflow exists in local `workflow_meta` table
