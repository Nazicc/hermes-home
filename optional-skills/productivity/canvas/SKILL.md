---
name: canvas
description: Canvas LMS integration — fetch enrolled courses and assignments using API token authentication. For: listing active courses, retrieving assignments with due dates, checking course rosters, and exporting grade data. NOT for: creating/editing courses, submitting assignments, managing users, or real-time Canvas notifications.
version: 1.0.0
author: community
license: MIT
prerequisites:
  env_vars: [CANVAS_API_TOKEN, CANVAS_BASE_URL]
metadata:
  hermes:
    tags: [Canvas, LMS, Education, Courses, Assignments]
---

# Canvas LMS — Course & Assignment Access

Read-only access to Canvas LMS for listing courses and assignments via the Canvas REST API.

## Why This Works

**Concept 1: API-Token-Based Authentication with Scoped Access.** Canvas access tokens are generated per-user from Account → Settings → Approved Integrations. Each token inherits the user's existing permissions — it can only access courses the user is enrolled in. This means a single API token can safely query across all active enrollments without per-course OAuth flows, while the `?enrollment_state=` filter narrows results client-side.

**Concept 2: Pagination-Aware API Design with Link Headers.** The Canvas API uses HTTP Link headers for pagination (`rel="next"`, `rel="last"`). A naive single-request fetch only returns the first page (default 10 items). The Python script in this skill handles pagination automatically via `requests` + Link-header parsing, so you always get the complete course or assignment list without manual page iteration.

## Setup

1. Log in to your Canvas instance in a browser
2. Go to **Account → Settings** (click your profile icon, then Settings)
3. Scroll to **Approved Integrations** and click **+ New Access Token**
4. Name the token (e.g., "Hermes Agent"), set an optional expiry, and click **Generate Token**
5. Copy the token and add to `~/.hermes/.env`:

```
CANVAS_API_TOKEN=your_token_here
CANVAS_BASE_URL=https://yourschool.instructure.com
```

The base URL is whatever appears in your browser when you're logged into Canvas (no trailing slash).

## Scripts

- `scripts/canvas_api.py` — Python CLI for Canvas API calls

## Usage

```bash
CANVAS="python $HERMES_HOME/skills/productivity/canvas/scripts/canvas_api.py"

# List all active courses
$CANVAS list_courses --enrollment-state active

# List all courses (any state)
$CANVAS list_courses

# List assignments for a specific course
$CANVAS list_assignments 12345

# List assignments ordered by due date
$CANVAS list_assignments 12345 --order-by due_at
```

## Examples

**Good: Weekly assignment digest.** Fetch all active courses, then for each course collect `list_assignments 12345 --order-by due_at`. Filter to assignments due in the next 7 days by parsing `due_at` timestamps. Compile a summary table with course name, assignment name, due date, and points possible. No manual Canvas navigation needed.

**Good: Course enrollment audit.** Run `list_courses` without `--enrollment-state` to see all courses including concluded/past ones. Cross-reference against a list of expected courses for the semester. Any course with `workflow_state: "completed"` that should still be active flags a potential enrollment issue.

## Output Format

**list_courses** returns:
```json
[{"id": 12345, "name": "Intro to CS", "course_code": "CS101", "workflow_state": "available", "start_at": "...", "end_at": "..."}]
```

**list_assignments** returns:
```json
[{"id": 67890, "name": "Homework 1", "due_at": "2025-02-15T23:59:00Z", "points_possible": 100, "submission_types": ["online_upload"], "html_url": "...", "description": "...", "course_id": 12345}]
```

Note: Assignment descriptions are truncated to 500 characters. The `html_url` field links to the full assignment page in Canvas.

## API Reference (curl)

```bash
# List courses
curl -s -H "Authorization: Bearer $CANVAS_API_TOKEN" \
  "$CANVAS_BASE_URL/api/v1/courses?enrollment_state=active&per_page=10"

# List assignments for a course
curl -s -H "Authorization: Bearer $CANVAS_API_TOKEN" \
  "$CANVAS_BASE_URL/api/v1/courses/COURSE_ID/assignments?per_page=10&order_by=due_at"
```

Canvas uses `Link` headers for pagination. The Python script handles pagination automatically.

## Anti-Patterns

**Anti-Pattern 1: Forgetting per_page limits.** Without specifying `?per_page=100`, Canvas defaults to 10 results per page. If you write a script that calls the API directly (not using the Python wrapper), you'll get incomplete data unless you implement Link-header pagination. The Python script handles this; raw curl calls do not.

**Anti-Pattern 2: Leaking the API token in commands or logs.** Passing `-H "Authorization: Bearer $CANVAS_API_TOKEN"` in a command line may leak the token into shell history or process listings. Use the `.env` file and scripts instead, or prefix your curl command with a space (bash ignores leading-space commands from history by default).

## When NOT to Use

- **Creating or modifying courses**: This skill is read-only. Use the Canvas web interface or the full Canvas API with write scopes.
- **Submitting assignments**: This skill does not support `/api/v1/courses/:id/assignments/:id/submissions`. Use the Canvas web UI or a dedicated assignment submission tool.
- **Real-time notifications**: Canvas webhooks or polling the API for changes is better handled by dedicated monitoring tools.
- **Instructure-provisioned APIs outside Canvas**: This skill targets Canvas LMS only. For other Instructure products, check their respective API docs.

## Rules

- This skill is **read-only** — it only fetches data, never modifies courses or assignments
- On first use, verify auth by running `$CANVAS list_courses` — if it fails with 401, guide the user through setup
- Canvas rate-limits to ~700 requests per 10 minutes; check `X-Rate-Limit-Remaining` header if hitting limits

## Troubleshooting

| Problem | Fix |
|---------|-----|
| 401 Unauthorized | Token invalid or expired — regenerate in Canvas Settings |
| 403 Forbidden | Token lacks permission for this course |
| Empty course list | Try `--enrollment-state active` or omit the flag to see all states |
| Wrong institution | Verify `CANVAS_BASE_URL` matches the URL in your browser |
| Timeout errors | Check network connectivity to your Canvas instance |

## Cross-References

- **obsidian**: Local-first note-taking alternative to Canvas's built-in tools
- **research-paper-writing**: Complements Canvas by handling academic paper creation workflows
- **deerflow-commander**: For deep research on academic topics from Canvas courses
