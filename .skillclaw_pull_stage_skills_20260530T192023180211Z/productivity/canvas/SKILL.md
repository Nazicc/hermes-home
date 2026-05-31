---
name: canvas
description: "Canvas LMS integration — fetch enrolled courses and assignments using API token authentication. Use when: integrating with Canvas LMS to fetch courses, assignments, grades, or student data. NOT for: non-Canvas LMS, grade calculation, or attendance tracking."
category: productivity
---

# Canvas LMS — Course & Assignment Access

Read-only access to Canvas LMS for listing courses and assignments.

## Scripts

- `scripts/canvas_api.py` — Python CLI for Canvas API calls

## Setup

1. Log in to your Canvas instance in a browser
2. Go to **Account → Settings** (click your profile icon, then Settings)
3. Scroll to **Approved Integrations** and click **+ New Access Token**
4. Name the token (e.g., "Hermes Agent"), set an optional expiry, and click **Generate Token**
5. Copy the token and add to `~/.hermes/.env`:


CANVAS_API_TOKEN=your_token_here
CANVAS_BASE_URL=https://yourschool.instructure.com


The base URL is whatever appears in your browser when you're logged into Canvas (no trailing slash).

## Prerequisites

- `CANVAS_API_TOKEN`: Your Canvas API access token
- `CANVAS_BASE_URL`: Your Canvas instance base URL (e.g., `https://canvas.example.edu`)

## Usage

bash
CANVAS="python $HERMES_HOME/skills/productivity/canvas/scripts/canvas_api.py"

# List all active courses
$CANVAS list_courses --enrollment-state active

# List all courses (any state)
$CANVAS list_courses

# List assignments for a specific course
$CANVAS list_assignments 12345

# List assignments ordered by due date
$CANVAS list_assignments 12345 --order-by due_at


## Output Format

**list_courses** returns:

[{"id": 12345, "name": "Intro to CS", "course_code": "CS101", "workflow_state": "available", "start_at": "...", "end_at": "..."}]


**list_assignments** returns:

[{"id": 67890, "name": "Homework 1", "due_at": "2025-02-15T23:59:00Z", "points_possible": 100, "submission_types": ["online_upload"], "html_url": "...", "description": "...", "course_id": 12345}]


Note: Assignment descriptions are truncated to 500 characters. The `html_url` field links to the full assignment page in Canvas.

## API Reference

All requests require the `Authorization: Bearer <token>` header.

### Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/courses` | List enrolled courses |
| GET | `/api/v1/courses/:id/assignments` | Get assignments for a course |
| GET | `/api/v1/courses/:id/users` | List students in a course |
| GET | `/api/v1/courses/:id/enrollments` | Get enrollment info |
| GET | `/api/v1/courses/:id/grades` | Get grades for a course |
| GET | `/api/v1/users/:id/profile` | Get user profile |
| GET | `/api/v1/accounts/:id/users` | List users (admin) |

### curl Examples

bash
# List courses
curl -s -H "Authorization: Bearer $CANVAS_API_TOKEN" \
  "$CANVAS_BASE_URL/api/v1/courses?enrollment_state=active&per_page=10"

# List assignments for a course
curl -s -H "Authorization: Bearer $CANVAS_API_TOKEN" \
  "$CANVAS_BASE_URL/api/v1/courses/COURSE_ID/assignments?per_page=10&order_by=due_at"


## Rules

- This skill is **read-only** — it only fetches data, never modifies courses or assignments
- On first use, verify auth by running `$CANVAS list_courses` — if it fails with 401, guide the user through setup
- Canvas rate-limits to ~700 requests per 10 minutes; check `X-Rate-Lemaining` header if hitting limits

## Pagination

Canvas uses `Link` headers for pagination. Use `per_page=100` to reduce the number of requests. The Python script handles pagination automatically.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| 401 Unauthorized | Token invalid or expired — regenerate in Canvas Settings |
| 403 Forbidden | Token lacks permission for this course |
| Empty course list | Try `--enrollment-state active` or omit the flag to see all states |
| Wrong institution | Verify `CANVAS_BASE_URL` matches the URL in your browser |
| Timeout errors | Check network connectivity to your Canvas instance |
| Rate limit exceeded | Add delays between requests; check `X-Rate-Limit-Remaining` header |
