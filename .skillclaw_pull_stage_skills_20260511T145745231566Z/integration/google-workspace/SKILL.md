---
name: google-workspace
description: "Use when integrating with Gmail, Calendar, Drive, Contacts, Sheets, and Docs via Hermes-managed OAuth2. Prefers Google Workspace CLI (gws) for broader API coverage, falls back to Python client libraries. NOT for: non-Google services, programmatic ad buying, or when native Google apps are more efficient."
category: integration
---

# Google Workspace Integration

This skill provides comprehensive integration with Google's productivity suite through Hermes-managed OAuth2 authentication.

## Capabilities

- **Gmail**: Read, send, archive, and manage email
- **Calendar**: Create, read, update, and delete calendar events
- **Drive**: Upload, download, and manage files in Google Drive
- **Contacts**: Access and manage Google Contacts
- **Sheets**: Read and write to Google Spreadsheets
- **Docs**: Create and edit Google Documents

## Authentication

Uses Hermes-managed OAuth2. The skill automatically handles token refresh and credential management.

## API Preference

1. **Google Workspace CLI (gws)**: Preferred when available — provides broadest API coverage
2. **Python client libraries**: Fallback option for additional functionality

## Usage Examples

bash
# List recent emails
python -m googleworkspace.gmail list --max-results 10

# Create calendar event
gws calendar create --title "Team Meeting" --start 2024-01-15T10:00:00

# Upload file to Drive
gws drive upload --file ./document.pdf --folder backup-folder


## Configuration

Set OAuth credentials via Hermes environment variables:
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`

The skill will automatically locate and use credentials from `~/.hermes/config.yaml`.
