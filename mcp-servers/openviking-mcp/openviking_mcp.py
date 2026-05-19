#!/usr/bin/env python3
"""
OpenViking MCP Server — wraps the OpenViking REST API as FastMCP tools for Hermes Agent.

Exposes 6 tools:
  viking_search      — semantic search over knowledge base
  viking_read        — read content at viking:// URI (abstract/overview/full)
  viking_browse      — browse the knowledge store like a filesystem
  viking_remember    — store a fact in OpenViking
  viking_add_resource - add a remote URL or local file/directory
  memory_recall      — unified layered memory retrieval (L2 + Hindsight + L3)

Environment variables (from ~/.hermes/.env):
  OPENVIKING_ENDPOINT  — Server URL (default: http://127.0.0.1:1933)
  OPENVIKING_API_KEY   — API key
  OPENVIKING_ACCOUNT   — Tenant account (default: default)
  OPENVIKING_USER      — Tenant user (default: default)
  OPENVIKING_AGENT     — Tenant agent (default: hermes)
  HINDSIGHT_URL        — Hindsight REST API URL (for memory_recall)
  HINDSIGHT_BANK       — Hindsight bank name (default: hermes-agent)
"""

from __future__ import annotations

import json
import logging
import mimetypes
import os
import sqlite3
import tempfile
import uuid
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from urllib.request import url2pathname

from mcp.server.fastmcp import FastMCP

# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("openviking_mcp")

# ── Load ~/.hermes/.env (delegated to Hermes via env config) ───────────────

# ── Constants ──────────────────────────────────────────────────────────────
_DEFAULT_ENDPOINT = "http://127.0.0.1:1933"
_TIMEOUT = 30.0
_REMOTE_RESOURCE_PREFIXES = ("http://", "https://", "git@", "ssh://", "git://")
_HINDSIGHT_URL = os.environ.get("HINDSIGHT_URL", "http://localhost:8989")
_HINDSIGHT_BANK = os.environ.get("HINDSIGHT_BANK", "hermes-agent")
_HINDSIGHT_MIN_MSG_LEN = int(os.environ.get("HINDSIGHT_MIN_MSG_LEN", "50"))

# ── FastMCP server ─────────────────────────────────────────────────────────
mcp = FastMCP("openviking-mcp")


# ── Helpers ────────────────────────────────────────────────────────────────
def _get_httpx():
    try:
        import httpx
        return httpx
    except ImportError:
        return None


def _lazy_httpx():
    """Import httpx on demand (for Hindsight calls in memory_recall)."""
    return _get_httpx()


def _zip_directory(dir_path: Path) -> Path:
    zip_path = Path(tempfile.gettempdir()) / f"openviking_upload_{uuid.uuid4().hex}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for file_path in dir_path.rglob("*"):
            if file_path.is_file():
                arcname = str(file_path.relative_to(dir_path)).replace("\\", "/")
                zipf.write(file_path, arcname=arcname)
    return zip_path


def _is_windows_absolute_path(value: str) -> bool:
    return (
        len(value) >= 3
        and value[0].isalpha()
        and value[1] == ":"
        and value[2] in ("/", "\\")
    )


def _is_remote_resource_source(value: str) -> bool:
    return value.startswith(_REMOTE_RESOURCE_PREFIXES)


def _is_local_path_reference(value: str) -> bool:
    if not value or "\n" in value or "\r" in value:
        return False
    if _is_remote_resource_source(value):
        return False
    if _is_windows_absolute_path(value):
        return True
    return (
        value.startswith(("/", "./", "../", "~/", ".\\", "..\\", "~\\"))
        or "/" in value
        or "\\" in value
    )


def _path_from_file_uri(uri: str) -> Path | str:
    parsed = urlparse(uri)
    if parsed.netloc not in ("", "localhost"):
        return f"Unsupported non-local file URI: {uri}"
    return Path(url2pathname(parsed.path)).expanduser()


# ── OpenViking REST client ─────────────────────────────────────────────────
class _VikingClient:
    """Thin HTTP client for the OpenViking REST API."""

    def __init__(self, endpoint: str, api_key: str = "",
                 account: str = "", user: str = "", agent: str = ""):
        self._endpoint = endpoint.rstrip("/")
        self._api_key = api_key
        self._account = account or os.environ.get("OPENVIKING_ACCOUNT", "default")
        self._user = user or os.environ.get("OPENVIKING_USER", "default")
        self._agent = agent or os.environ.get("OPENVIKING_AGENT", "hermes")
        self._httpx = _get_httpx()
        if self._httpx is None:
            raise ImportError("httpx is required for OpenViking: pip install httpx")

    def _headers(self) -> dict:
        h = {
            "Content-Type": "application/json",
            "X-OpenViking-Agent": self._agent,
        }
        if self._account:
            h["X-OpenViking-Account"] = self._account
        if self._user:
            h["X-OpenViking-User"] = self._user
        if self._api_key:
            h["X-API-Key"] = self._api_key
            h["Authorization"] = "Bearer " + self._api_key
        return h

    def _url(self, path: str) -> str:
        return f"{self._endpoint}{path}"

    def _multipart_headers(self) -> dict:
        headers = self._headers()
        headers.pop("Content-Type", None)
        return headers

    def _parse_response(self, resp) -> dict:
        try:
            data = resp.json()
        except Exception:
            data = None
        if resp.status_code >= 400:
            if isinstance(data, dict):
                error = data.get("error")
                if isinstance(error, dict):
                    code = error.get("code", "HTTP_ERROR")
                    message = error.get("message", resp.text)
                    raise RuntimeError(f"{code}: {message}")
                if data.get("status") == "error":
                    raise RuntimeError(str(data))
            resp.raise_for_status()
        if isinstance(data, dict) and data.get("status") == "error":
            error = data.get("error")
            if isinstance(error, dict):
                code = error.get("code", "OPENVIKING_ERROR")
                message = error.get("message", "")
                raise RuntimeError(f"{code}: {message}")
            raise RuntimeError(str(data))
        if data is None:
            return {}
        return data

    def get(self, path: str, **kwargs) -> dict:
        resp = self._httpx.get(
            self._url(path), headers=self._headers(), timeout=_TIMEOUT, **kwargs
        )
        return self._parse_response(resp)

    def post(self, path: str, payload: dict = None, **kwargs) -> dict:
        resp = self._httpx.post(
            self._url(path), json=payload or {}, headers=self._headers(),
            timeout=_TIMEOUT, **kwargs
        )
        return self._parse_response(resp)

    def upload_temp_file(self, file_path: Path) -> str:
        mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        with file_path.open("rb") as f:
            resp = self._httpx.post(
                self._url("/api/v1/resources/temp_upload"),
                files={"file": (file_path.name, f, mime_type)},
                headers=self._multipart_headers(),
                timeout=_TIMEOUT,
            )
        data = self._parse_response(resp)
        result = data.get("result", {})
        temp_file_id = result.get("temp_file_id", "")
        if not temp_file_id:
            raise RuntimeError("OpenViking temp upload did not return temp_file_id")
        return temp_file_id

    def health(self) -> bool:
        try:
            resp = self._httpx.get(
                self._url("/health"), headers=self._headers(), timeout=3.0
            )
            return resp.status_code == 200
        except Exception:
            return False


# ── Client singleton (lazily initialized) ──────────────────────────────────
_client: Optional[_VikingClient] = None


def _get_client() -> _VikingClient:
    global _client
    if _client is None:
        endpoint = os.environ.get("OPENVIKING_ENDPOINT", _DEFAULT_ENDPOINT)
        api_key = os.environ.get("OPENVIKING_API_KEY", "")
        account = os.environ.get("OPENVIKING_ACCOUNT", "default")
        user = os.environ.get("OPENVIKING_USER", "default")
        agent = os.environ.get("OPENVIKING_AGENT", "hermes")
        _client = _VikingClient(endpoint, api_key, account=account, user=user, agent=agent)
    return _client


# ── Helper: error response ─────────────────────────────────────────────────
def _tool_error(msg: str) -> str:
    return json.dumps({"status": "error", "message": msg})


# ── Tool implementations ───────────────────────────────────────────────────

@mcp.tool()
def viking_search(
    query: str,
    mode: str = "auto",
    scope: str = "",
    limit: int = 10,
) -> str:
    """Semantic search over the OpenViking knowledge base.
    Returns ranked results with viking:// URIs for deeper reading.
    Use mode='deep' for complex queries that need reasoning across
    multiple sources, 'fast' for simple lookups.
    """
    client = _get_client()
    if not query:
        return _tool_error("query is required")

    payload: Dict[str, Any] = {"query": query}
    if mode != "auto":
        payload["mode"] = mode
    if scope:
        payload["target_uri"] = scope
    payload["top_k"] = limit

    resp = client.post("/api/v1/search/find", payload)
    result = resp.get("result", {})

    scored_entries = []
    for ctx_type in ("memories", "resources", "skills"):
        items = result.get(ctx_type, [])
        for item in items:
            raw_score = item.get("score")
            sort_score = raw_score if raw_score is not None else 0.0
            entry = {
                "uri": item.get("uri", ""),
                "type": ctx_type.rstrip("s"),
                "score": round(raw_score, 3) if raw_score is not None else 0.0,
                "abstract": item.get("abstract", ""),
            }
            if item.get("relations"):
                entry["related"] = [r.get("uri") for r in item["relations"][:3]]
            scored_entries.append((sort_score, entry))

    scored_entries.sort(key=lambda x: x[0], reverse=True)
    formatted = [entry for _, entry in scored_entries]

    return json.dumps({
        "results": formatted,
        "total": result.get("total", len(formatted)),
    }, ensure_ascii=False)


@mcp.tool()
def viking_read(
    uri: str,
    level: str = "overview",
) -> str:
    """Read content at a viking:// URI. Three detail levels:
      abstract — ~100 token summary (L0)
      overview — ~2k token key points (L1)
      full — complete content (L2)
    Start with abstract/overview, only use full when you need details.
    """
    client = _get_client()
    if not uri:
        return _tool_error("uri is required")

    summary_level = level in ("abstract", "overview")

    def _normalize_summary_uri(u: str) -> str:
        if not u:
            return u
        for suffix in ("/.abstract.md", "/.overview.md", "/.read.md", "/.full.md"):
            if u.endswith(suffix):
                return u[: -len(suffix)] or "viking://"
        return u

    resolved_uri = _normalize_summary_uri(uri) if summary_level else uri
    used_fallback = False

    if summary_level and resolved_uri == uri:
        try:
            stat_resp = client.get("/api/v1/fs/stat", params={"uri": uri})
            stat_result = stat_resp.get("result", {})
            if isinstance(stat_result, dict):
                is_dir = (
                    stat_result.get("isDir")
                    or stat_result.get("is_dir")
                    or stat_result.get("type") == "dir"
                )
                if is_dir is False:
                    resolved_uri = uri
                    used_fallback = True
        except Exception:
            pass

    endpoint = "/api/v1/content/read"
    if not used_fallback:
        if level == "abstract":
            endpoint = "/api/v1/content/abstract"
        elif level == "overview":
            endpoint = "/api/v1/content/overview"

    try:
        resp = client.get(endpoint, params={"uri": resolved_uri})
    except Exception:
        if not summary_level or resolved_uri != uri or used_fallback:
            raise
        resp = client.get("/api/v1/content/read", params={"uri": uri})
        used_fallback = True

    result = resp.get("result", {})
    if isinstance(result, str):
        content = result
    elif isinstance(result, dict):
        content = result.get("content", "") or result.get("text", "")
    else:
        content = ""

    max_len = 8000
    if level == "overview":
        max_len = 4000
    elif level == "abstract":
        max_len = 1200

    if len(content) > max_len:
        content = content[:max_len] + "\n\n[... truncated, use a more specific URI or full level]"

    payload = {
        "uri": uri,
        "resolved_uri": resolved_uri,
        "level": level,
        "content": content,
    }
    if used_fallback:
        payload["fallback"] = "content/read"

    return json.dumps(payload, ensure_ascii=False)


@mcp.tool()
def viking_browse(
    action: str = "list",
    path: str = "viking://",
) -> str:
    """Browse the OpenViking knowledge store like a filesystem.
      list — show directory contents
      tree — show hierarchy
      stat — show metadata for a URI
    """
    client = _get_client()

    endpoint_map = {
        "tree": "/api/v1/fs/tree",
        "list": "/api/v1/fs/ls",
        "stat": "/api/v1/fs/stat",
    }
    endpoint = endpoint_map.get(action, "/api/v1/fs/ls")
    resp = client.get(endpoint, params={"uri": path})
    result = resp.get("result", {})

    if action in ("list", "tree"):
        raw_entries = result
        if isinstance(result, dict):
            raw_entries = (
                result.get("entries")
                or result.get("items")
                or result.get("children")
                or []
            )
        if isinstance(raw_entries, list):
            entries = []
            for e in raw_entries[:50]:
                uri = e.get("uri", "")
                name = (
                    e.get("rel_path")
                    or e.get("name")
                    or (uri.rsplit("/", 1)[-1] if uri else "")
                )
                is_dir = bool(
                    e.get("isDir") or e.get("is_dir") or e.get("type") == "dir"
                )
                entries.append({
                    "name": name,
                    "uri": uri,
                    "type": "dir" if is_dir else "file",
                    "abstract": e.get("abstract", ""),
                })
            return json.dumps({"path": path, "entries": entries}, ensure_ascii=False)

    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
def viking_remember(
    content: str,
    category: str = "",
) -> str:
    """Explicitly store a fact or memory in the OpenViking knowledge base.
    Use for important information the agent should remember long-term.
    The system automatically categorizes and indexes the memory.
    """
    if not content:
        return _tool_error("content is required")

    text = f"[Remember] {content}"
    if category:
        text = f"[Remember — {category}] {content}"

    # OpenViking auto-extracts memories on session commit from messages.
    # We use a fixed session "mcp-remember" as a scratch session.
    _get_client().post("/api/v1/sessions/mcp-remember/messages", {
        "role": "user",
        "parts": [{"type": "text", "text": text}],
    })
    # Trigger commit so extraction happens immediately
    try:
        _get_client().post("/api/v1/sessions/mcp-remember/commit")
    except Exception:
        pass

    return json.dumps({
        "status": "stored",
        "message": "Memory recorded and indexed.",
    })


@mcp.tool()
def viking_add_resource(
    url: str,
    reason: str = "",
    to: str = "",
    parent: str = "",
    instruction: str = "",
    wait: bool = False,
    timeout: float = 0.0,
) -> str:
    """Add a remote URL or local file/directory to the OpenViking knowledge base.
    Remote resources must be public http(s), git, or ssh URLs.
    Local files are uploaded first using OpenViking temp_upload.
    The system automatically parses, indexes, and generates summaries.
    """
    client = _get_client()
    if not url:
        return _tool_error("url is required")

    if to and parent:
        return _tool_error("Cannot specify both 'to' and 'parent'")

    payload: Dict[str, Any] = {}
    if reason:
        payload["reason"] = reason
    if to:
        payload["to"] = to
    if parent:
        payload["parent"] = parent
    if instruction:
        payload["instruction"] = instruction
    if wait:
        payload["wait"] = True
    if timeout > 0:
        payload["timeout"] = timeout

    parsed_url = urlparse(url)
    if _is_remote_resource_source(url):
        source_path = None
    elif parsed_url.scheme == "file":
        source_path = _path_from_file_uri(url)
        if isinstance(source_path, str):
            return _tool_error(source_path)
    elif parsed_url.scheme and not _is_windows_absolute_path(url):
        source_path = None
    else:
        source_path = Path(url).expanduser()

    cleanup_path: Optional[Path] = None
    try:
        if source_path is not None:
            if source_path.exists():
                if source_path.is_dir():
                    payload["source_name"] = source_path.name
                    cleanup_path = _zip_directory(source_path)
                    upload_path = cleanup_path
                elif source_path.is_file():
                    payload["source_name"] = source_path.name
                    upload_path = source_path
                else:
                    return _tool_error(f"Unsupported local resource path: {url}")
                payload["temp_file_id"] = client.upload_temp_file(upload_path)
            elif _is_local_path_reference(url):
                return _tool_error(f"Local resource path does not exist: {url}")
            else:
                payload["path"] = url
        else:
            payload["path"] = url

        resp = client.post("/api/v1/resources", payload)
        result = resp.get("result", {})
    finally:
        if cleanup_path:
            cleanup_path.unlink(missing_ok=True)

    return json.dumps({
        "status": "added",
        "root_uri": result.get("root_uri", ""),
        "message": "Resource queued for processing. Use viking_search after a moment to find it.",
    }, ensure_ascii=False)


@mcp.tool()
def memory_recall(
    query: str,
    max_results: int = 10,
    layers: str = "L2,hindsight,L3",
) -> str:
    """Unified layered memory retrieval. Searches L0 (injected context) →
    L2 (OpenViking long-term) → Hindsight (graph reasoning) →
    L1 (working memory) → L3 (evolution signals).
    Returns deduplicated, ranked results with source layer tags.
    """
    if not query:
        return _tool_error("query is required")

    if layers.strip().lower() == "all":
        active_layers = {"L0", "L2", "hindsight", "L1", "L3"}
    else:
        active_layers = {l.strip() for l in layers.split(",") if l.strip()}

    all_results: List[Dict[str, Any]] = []
    seen_uris = set()
    client = _get_client()

    # ── L2: OpenViking semantic search ──
    if "L2" in active_layers:
        try:
            payload = {"query": query, "top_k": max_results}
            resp = client.post("/api/v1/search/find", payload)
            result = resp.get("result", {})
            for ctx_type in ("memories", "resources"):
                for item in result.get(ctx_type, [])[:max_results]:
                    uri = item.get("uri", "")
                    if uri in seen_uris:
                        continue
                    seen_uris.add(uri)
                    all_results.append({
                        "layer": "L2",
                        "source": ctx_type.rstrip("s"),
                        "uri": uri,
                        "score": round(item.get("score", 0), 3),
                        "snippet": (item.get("abstract", "") or "")[:300],
                    })
        except Exception as e:
            logger.debug("memory_recall L2 failed: %s", e)

    # ── Hindsight: recall + reflect ──
    if "hindsight" in active_layers:
        try:
            httpx_mod = _lazy_httpx()
            if httpx_mod:
                resp = httpx_mod.post(
                    f"{_HINDSIGHT_URL}/v1/default/banks/{_HINDSIGHT_BANK}/recall",
                    json={"query": query, "max_results": min(max_results, 5)},
                    timeout=15.0,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for mem in data.get("results", data.get("memories", []))[:5]:
                        content = mem.get("content", mem.get("text", ""))
                        uri = f"hindsight:{mem.get('id', '')}"
                        if uri in seen_uris:
                            continue
                        seen_uris.add(uri)
                        all_results.append({
                            "layer": "hindsight",
                            "source": "graph-recall",
                            "uri": uri,
                            "score": round(mem.get("score", 0), 3),
                            "snippet": (content or "")[:300],
                        })
                if len(all_results) < 3:
                    resp2 = httpx_mod.post(
                        f"{_HINDSIGHT_URL}/v1/default/banks/{_HINDSIGHT_BANK}/reflect",
                        json={"query": query, "budget": "low", "max_tokens": 512},
                        timeout=20.0,
                    )
                    if resp2.status_code == 200:
                        reflection = resp2.json()
                        insight = reflection.get("insight", reflection.get("reflection", ""))
                        if insight and len(str(insight)) > 20:
                            all_results.append({
                                "layer": "hindsight",
                                "source": "reflect",
                                "uri": "hindsight:reflect",
                                "score": 0.0,
                                "snippet": str(insight)[:500],
                            })
        except Exception as e:
            logger.debug("memory_recall Hindsight failed: %s", e)

    # ── L3: Evolution signals ──
    if "L3" in active_layers:
        try:
            db_path = os.path.expanduser("~/.hermes/simplemem_evolution/evolution.db")
            if os.path.exists(db_path):
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute(
                    "SELECT id, type, timestamp, summary FROM evolution_events "
                    "WHERE summary LIKE ? ORDER BY timestamp DESC LIMIT ?",
                    (f"%{query}%", max_results),
                )
                for row in cur.fetchall():
                    uri = f"evolution:{row['id']}"
                    if uri in seen_uris:
                        continue
                    seen_uris.add(uri)
                    all_results.append({
                        "layer": "L3",
                        "source": "evolution",
                        "uri": uri,
                        "score": 0.0,
                        "snippet": (row["summary"] or "")[:300],
                    })
                conn.close()
        except Exception as e:
            logger.debug("memory_recall L3 failed: %s", e)

    if not all_results:
        return "No results found across any memory layer."

    lines = []
    for r in all_results[:max_results]:
        lines.append(
            f"[{r['layer']}] {r['uri']} (score={r['score']})\n{r['snippet']}"
        )
    return "\n---\n".join(lines)


# ── Main ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    mcp.run()
