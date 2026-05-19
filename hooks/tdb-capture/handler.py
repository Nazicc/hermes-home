"""TDB-AM Capture Hook — fire-and-forget POST to TDB-AM /capture on every agent turn.

Sends the user message and agent response to the TDB-AM sidecar for
short-term memory compression. Runs async — never blocks the gateway.

Skips captures when:
- Message is too short (<10 chars — likely 'hi' or 'ok')
- Response is empty (tool-only turn, no final response yet)
- TDB-AM is unreachable (logged, not retried — fire-and-forget)
"""

import asyncio
import logging
from urllib.request import Request, urlopen
from urllib.error import URLError
import json

logger = logging.getLogger("hooks.tdb-capture")

TDB_URL = "http://localhost:8420/capture"
MIN_MESSAGE_LENGTH = 10


def _post_capture(payload: dict) -> None:
    """Synchronous POST to TDB-AM. Runs in executor thread."""
    try:
        data = json.dumps(payload).encode("utf-8")
        req = Request(TDB_URL, data=data, headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(req, timeout=5) as resp:
            if resp.status != 200:
                logger.debug("TDB capture: HTTP %d", resp.status)
    except URLError as e:
        logger.debug("TDB capture unreachable: %s", e)
    except Exception as e:
        logger.debug("TDB capture error: %s", e)


async def handle(event_type: str, context: dict) -> None:
    """Capture agent turn to TDB-AM."""
    user_msg = (context.get("message") or "").strip()
    response = (context.get("response") or "").strip()

    # Skip trivial turns
    if len(user_msg) < MIN_MESSAGE_LENGTH and len(response) < MIN_MESSAGE_LENGTH:
        return

    session_key = _safe_session_key(context)

    payload = {
        "session_key": session_key,
        "user_content": user_msg[:8000],
        "assistant_content": response[:8000],
        "user_id": context.get("user_id", ""),
        "session_id": context.get("session_id", ""),
    }

    # Fire and forget — run in thread so we don't block the event loop
    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, _post_capture, payload)


def _safe_session_key(context: dict) -> str:
    """Build a stable session key from platform + user_id."""
    platform = context.get("platform", "unknown")
    user_id = context.get("user_id", "anon")
    # Sanitize for filesystem safety
    safe_platform = "".join(c if c.isalnum() or c in "-_" else "_" for c in platform)
    safe_user = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(user_id))
    return f"{safe_platform}-{safe_user}"
