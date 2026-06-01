---
name: imessage
description: "Send and receive iMessages/SMS via the imsg CLI on macOS. Use when you need to send a notification, alert, or message from the terminal — for monitoring, automation, or personal communication. NOT for bulk messaging (no spamming), NOT for sending to unknown recipients, NOT for programmatic SMS gateways."
category: apple
triggers:
  - imessage
  - send message
  - imsg
  - Apple iMessage
  - SMS via macOS
  - text notification
anti_triggers:
  - bulk SMS
  - spam
  - marketing
  - programmatic SMS gateway
  - WhatsApp
  - WeChat
---

## Why This Works

**Direct macOS-native messaging** — imsg gives you programmatic access to Apple's iMessage service from the command line. No API keys, no webhooks, no third-party services. If you're on a Mac and signed into iMessage, you already have all the infrastructure needed.

**Incoming message awareness** — Unlike push-only notification services (Slack webhooks, email-to-SMS), imsg supports read and reply workflows. Your scripts can check for replies, read conversation history, and respond contextually. This enables interactive automation patterns that one-way notification systems can't do.

**Single command, zero setup** — `imsg send "contact" "message"` is all it takes. No SDK installation, no authentication configuration, no rate limit management. The Apple ID authentication is already handled by macOS's iMessage subsystem.

**Deterministic delivery** — iMessages are delivered through Apple's push notification infrastructure. Unlike email (which can land in spam), SMS (which depends on carrier routing), or third-party APIs (which may have downtime), iMessage delivery is consistent and reliable on Apple devices.

## Prerequisites

- macOS with the `imsg` command-line tool installed
- Apple ID configured for iMessage (checked in System Settings → Apple ID → iMessage)
- Active internet connection (iMessage requires Apple's servers)
- For SMS: connected iPhone with Text Message Forwarding enabled

## Usage

### Send a message

```bash
# To a phone number (international format: +country area number)
imsg send "+1234567890" "Hello, this is a test message"

# To an email address (iMessage-to-email)
imsg send "contact@email.com" "Message via iMessage"

# To a contact in your address book
imsg send "John Doe" "Meeting at 3pm"
```

### Read messages

```bash
# List recent conversations
imsg list

# Read messages from a specific contact
imsg read "+1234567890"

# Check unread messages
imsg unread

# Reply to a conversation
imsg reply "+1234567890" "Got it, thanks!"
```

### In automation

```bash
# Send a notification when a long-running task completes
long_running_command && \
  imsg send "+1234567890" "✅ Task completed successfully in $(date +%H:%M)"

# Alert on error
long_running_command || \
  imsg send "+1234567890" "❌ Task failed at $(date +%H:%M) — exit code $?"
```

## When NOT to Use This Skill

- **Bulk messaging** — iMessage is not designed for mass communication. Apple has rate limits and anti-spam protections. Use email (SMTP) or a messaging API for newsletters.
- **Unknown recipients** — Only message people who expect to hear from you. Unsolicited iMessages are a violation of Apple's terms.
- **Production alerting at scale** — For production monitoring at scale, use PagerDuty, OpsGenie, or Slack webhooks. imsg is for personal/team automation.
- **Cross-platform messaging** — iMessage only works on Apple devices. For Android/Windows users, use SMS, WhatsApp, or Telegram.
- **Non-Apple automation** — If you're not on macOS, imsg doesn't exist. Use alternative messaging APIs.
- **Marketing or commercial use** — Apple's terms prohibit using iMessage for commercial messaging without recipient consent.

## Examples

### Good: Personal automation notification

**Scenario**: You have a long-running ML training script and want to be notified when it finishes.

```bash
python3 train_model.py && \
  imsg send "+1234567890" "✅ Training complete — model accuracy: $(tail -1 logs/accuracy.csv)"
```

**Why this works**: The notification is personal, expected (the recipient knows the training runs), and uses a conditional (`&&`) so it only fires on success.

---

### Good: Cron job health check

**Scenario**: A daily backup script should notify you on failure only.

```bash
#!/bin/bash
if ! rsync -avz /data/ backup@server:/backups/; then
  imsg send "+1234567890" "❌ Backup failed at $(date): rsync exited with code $?"
  exit 1
fi
# Silent on success — no notification noise
```

**Why this works**: Only notifies on failure. Silence means success. This avoids alert fatigue.

---

### Good: Interactive reminder with reply

**Scenario**: Ask a question and wait for a reply to trigger the next step.

```bash
imsg send "+1234567890" "Deploy to production? Reply Y to proceed."
sleep 300
REPLY=$(imsg read "+1234567890" | tail -1)
if echo "$REPLY" | grep -qi "^y"; then
  ./deploy.sh
  imsg send "+1234567890" "🚀 Deployment started."
else
  imsg send "+1234567890" "⏸️ Deployment cancelled."
fi
```

**Why this works**: Uses imsg's read capability for interactive decision-making via iMessage, useful when you're away from the terminal.

---

### Bad: Spamming notifications

```bash
while true; do
  imsg send "+1234567890" "Server health check: OK — $(date)"
  sleep 60
done
```

**Bad**: Sends notification every minute. The recipient will be annoyed and either mute or block you. Never send frequent notifications unless explicitly requested.

---

### Bad: Sending to unknown numbers

```bash
# Scraping numbers from a website and messaging them
for number in $(curl https://example.com/contacts | grep -oE '[0-9]{10}'); do
  imsg send "+1$number" "Hi! I found your number online..."
done
```

**Bad**: Unsolicited messaging violates Apple's terms of service and may result in your Apple ID being banned. Only message people who have consented to receive messages from you.

## Anti-Patterns

1. **Silent notification noise** — Notifying on every success creates alert fatigue. Only notify on failure or significant milestones. "Silence means success" is a better pattern.
2. **Hardcoded phone numbers** — Embedding phone numbers in scripts makes them fragile and unshareable. Use environment variables: `$ALERT_PHONE`.
3. **No rate limiting** — Sending messages in a tight loop can trigger Apple's anti-spam protections and get your Apple ID temporarily blocked. Add `sleep 1` between messages.
4. **Sending unsolicited messages** — Scraping numbers from the web and messaging them violates Apple's ToS and is unethical. Only message consenting recipients.
5. **Failing silently** — A script that tries to send an iMessage and fails (network down, imsg not installed) without logging the failure loses the alert. Check `$?` after imsg calls.
6. **Assuming delivery** — iMessage shows "Delivered" but that only means Apple's servers accepted it. The recipient may have notifications silenced, be in Do Not Disturb, or have blocked you.
7. **Phone number format inconsistency** — Using `+1 (234) 567-8900`, `1234567890`, or `+12345678900` inconsistently breaks send/reply. Always use E.164 format: `+[country][area][number]`.
8. **Sending sensitive data via iMessage** — iMessage is encrypted in transit but stored on Apple's servers. Don't send passwords, API keys, or PII via automated iMessage scripts.

## Troubleshooting

### "imsg: command not found"

Install imsg: `brew install imsg` or check if it's in a non-standard PATH. The imsg CLI is a third-party tool, not built into macOS.

### Message not sending

- Check internet connectivity: `ping apple.com`
- Verify Apple ID is signed into iMessage: System Settings → Apple ID → iMessage
- Check if recipient is reachable: try sending manually from Messages.app
- For SMS: ensure Text Message Forwarding is enabled on iPhone

### "Rate limited" error

Apple temporarily blocks accounts that send too many messages. Pause for 15-30 minutes and reduce sending frequency.

### Delivery not confirmed

iMessage delivery status is best-effort. The recipient may have notifications off, be offline, or have blocked your Apple ID. If critical, use a delivery-confirmed channel (SMS, phone call API).

## Cross-References

- **imsg** (skills/imsg/SKILL.md) — The imsg CLI tool used for sending iMessages
- **cronjob** (skills/cronjob/SKILL.md) — Schedule periodic iMessage notifications from cron
- **apple-reminders** (skills/productivity/apple-reminders/SKILL.md) — Send iMessage reminders via remindctl CLI integration
- **apple-notes** (skills/apple-notes/SKILL.md) — Share note content via iMessage automation
- **notion** (skills/productivity/notion/SKILL.md) — Trigger iMessage notifications from Notion database changes
- **hermes-cron-security-reports** (skills/productivity/hermes-cron-security-reports/SKILL.md) — Security report delivery pattern (alternative notification channel)
- **website-monitoring** (skills/website-monitoring/SKILL.md) — Send iMessage alerts on website downtime
