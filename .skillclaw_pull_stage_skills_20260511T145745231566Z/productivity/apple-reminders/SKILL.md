---
name: apple-reminders
description: "Manage Apple Reminders via remindctl CLI (list, add, complete, delete). Use when user asks to add a reminder, list tasks, mark something done, or manage Apple Reminders from the terminal."
category: productivity
triggers: [list reminders, show reminders, add reminder, create reminder, remind me to, complete
    a reminder, delete reminder, mark reminder done, manage reminders, apple reminders,
  to-do]
anti_triggers: [calendar, apple notes, non-macOS, windows, linux]
quality_redlines: ["Prerequisite check: run `which remindctl` before any operation \u2014 if not found,\
    \ halt and report", List output is non-empty before reporting 'no reminders found',
  New reminder ID or confirmation shown after add, Completed/deleted reminder disappears
    or is marked done on list]
---

---
name: apple-reminders
description: >
  Manage Apple Reminders via remindctl CLI (list, add, complete, delete).
  Use when user asks to add a reminder, list tasks, mark something done,
  or manage Apple Reminders from the terminal.
version: 1.0.1
author: Hermes Agent
license: MIT
platforms: [macos]
metadata:
  sources: []
  hermes:
    tags: [Reminders, tasks, todo, macOS, Apple]
    related_skills: [apple-notes]
prerequisites:
  commands: [remindctl]
  env_vars: []
---

## Prerequisites

**Required:** `remindctl` CLI.

If `remindctl` is not installed, install it via Homebrew:
bash
brew install remindctl


If Homebrew is unavailable or the package is not found, check if an equivalent exists in the user's PATH or use AppleScript as a fallback (see below).

**Fallback (no remindctl):** Use AppleScript via `osascript` for basic Reminders operations:
bash
# Add a reminder
osascript -e 'tell application "Reminders" to make new reminder with properties {name:"Task title", body:"Description"}'

# List reminders
osascript -e 'tell application "Reminders" to name of every reminder'

# Complete a reminder by name
osascript -e 'tell application "Reminders" to set completed of (first reminder whose name is "Task title") to true'


## Core Commands

### List reminders
bash
remindctl list [--list "List Name"] [--due <date>] [--incomplete]


### Add a reminder
bash
remindctl add "Reminder title" [--list "List Name"] [--due <date>] [--notes "Description"]


### Complete a reminder
bash
remindctl complete <reminder-id>


### Delete a reminder
bash
remindctl delete <reminder-id>


## Notes

- Use `--list` to specify which Reminders list to target (defaults to the default list).
- Dates can be in natural language (e.g., "tomorrow", "next week") or ISO format (`YYYY-MM-DD`).
- If remindctl fails, fall back to the AppleScript commands above.

