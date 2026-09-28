"""
CS3235 Lab 6 - Experiment 1: "Personal Assistant" Memory Server
================================================================

An MCP (Model Context Protocol) server exposing CRUD tools over a local
JSON file of notes. An LLM client (Claude Desktop, or our own client) can
connect over stdio and call these tools to remember and recall facts.

Tools exposed
-------------
    save_note(content, tags)                 -> create a note
    search_notes(query)                      -> keyword search (ranked)
    list_notes(tag)                          -> list all / by tag
    update_note(note_id, content, tags)      -> edit a note
    delete_note(note_id)                     -> remove a note

Storage
-------
    NOTES_FILE env var if set, otherwise ``notes.json`` next to this script.
    Writes are atomic (temp file + os.replace), UTF-8, indent=2.

IMPORTANT: stdio transport uses stdout for JSON-RPC messages, so this module
never prints to stdout. All logging goes to stderr, and only WARNING and above
is shown unless the LOG_LEVEL env var says otherwise (e.g. LOG_LEVEL=INFO).

Run:
    python notes_server.py
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

# --------------------------------------------------------------------------- #
# Logging (stderr only - stdout is reserved for the MCP stdio transport)
# --------------------------------------------------------------------------- #
# Quiet by default so server logs (inherited stderr) don't clutter the client
# UI. Set LOG_LEVEL=INFO (or DEBUG) to see every request.
LOG_LEVEL = os.environ.get("LOG_LEVEL", "WARNING").upper()
if LOG_LEVEL not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
    LOG_LEVEL = "WARNING"
logging.basicConfig(
    stream=sys.stderr,
    level=LOG_LEVEL,
    format="%(asctime)s [notes_server] %(levelname)s: %(message)s",
)
log = logging.getLogger("notes_server")

mcp = FastMCP("personal-memory", log_level=LOG_LEVEL)

# --------------------------------------------------------------------------- #
# Storage helpers
# --------------------------------------------------------------------------- #
_DEFAULT_NOTES_PATH = Path(__file__).resolve().parent / "notes.json"


def _notes_path() -> Path:
    """Resolve the notes file at call time (so tests can set NOTES_FILE late)."""
    env = os.environ.get("NOTES_FILE")
    return Path(env).expanduser().resolve() if env else _DEFAULT_NOTES_PATH


# Informational snapshot of the path at import time. Tools always call
# _notes_path() so that changes to os.environ["NOTES_FILE"] take effect.
NOTES_PATH = _notes_path()


def _load_notes() -> list[dict[str, Any]]:
    """Load notes from disk. A missing or empty file means no notes."""
    path = _notes_path()
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        log.error("Could not parse %s (%s); treating as empty.", path, exc)
        return []
    if not isinstance(data, list):
        log.error("%s does not contain a JSON list; treating as empty.", path)
        return []
    return data


def _save_notes(notes: list[dict[str, Any]]) -> None:
    """Atomically write notes to disk (temp file in same dir + os.replace)."""
    path = _notes_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".notes-", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(notes, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _normalise_tags(tags: list[str] | str | None) -> list[str]:
    """Lower-case, strip and de-duplicate tags, preserving first-seen order.

    Also tolerates a single comma-separated string (LLMs sometimes send one).
    """
    if tags is None:
        return []
    if isinstance(tags, str):
        tags = tags.split(",")
    out: list[str] = []
    for t in tags:
        t = str(t).strip().lower().lstrip("#")
        if t and t not in out:
            out.append(t)
    return out


def _ok(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _error(message: str) -> str:
    log.info("error: %s", message)
    return _ok({"status": "error", "message": message})


def _find(notes: list[dict[str, Any]], note_id: int) -> dict[str, Any] | None:
    for n in notes:
        if n.get("id") == note_id:
            return n
    return None


def _newest_first(notes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        notes,
        key=lambda n: (n.get("created_at", ""), n.get("id", 0)),
        reverse=True,
    )


# --------------------------------------------------------------------------- #
# Search helpers
# --------------------------------------------------------------------------- #
STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "of", "to", "in", "on", "at", "for",
    "with", "by", "from", "as", "is", "are", "was", "were", "be", "been", "am",
    "do", "does", "did", "done", "have", "has", "had", "i", "me", "my", "mine",
    "we", "our", "you", "your", "it", "its", "this", "that", "these", "those",
    "what", "which", "who", "whom", "when", "where", "why", "how", "any",
    "about", "say", "said", "tell", "told", "note", "notes", "remember",
    "there", "some", "all", "anything", "something", "can", "could", "would",
    "should", "will", "please", "show", "find", "get", "give", "list", "know",
    "regarding", "re", "s", "t",
}

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenise(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _variants(token: str) -> set[str]:
    """Very light stemming so 'deadlines' matches 'deadline' and vice versa."""
    v = {token}
    if len(token) > 3 and token.endswith("s"):
        v.add(token[:-1])
    return v


def _score(note: dict[str, Any], tokens: list[str]) -> int:
    content = str(note.get("content", "")).lower()
    content_words = set(_tokenise(content))
    tags = [str(t).lower() for t in note.get("tags", [])]
    score = 0
    for tok in tokens:
        forms = _variants(tok)
        # Content hit: whole-word match (incl. singular form) or substring for
        # longer tokens (so "groc" won't match, but "grocer" matches "grocery").
        if forms & content_words or (len(tok) >= 4 and tok in content):
            score += 1
        # Tag hit (weighted x2): exact tag or tag contains the token.
        if any(f == t or (len(f) >= 3 and f in t) for f in forms for t in tags):
            score += 2
    return score


# --------------------------------------------------------------------------- #
# MCP tools
# --------------------------------------------------------------------------- #
@mcp.tool()
def save_note(content: str, tags: list[str] | None = None) -> str:
    """Save a new note to the user's personal memory.

    Use this whenever the user asks you to remember, note down, or save
    something (e.g. "remember that my project deadline is Friday").

    Args:
        content: The full text of the note. Must be non-empty. Write it as a
            self-contained fact so it is understandable when recalled later.
        tags: Optional list of short topic keywords, e.g. ["project",
            "deadline"]. Tags are lower-cased and de-duplicated.

    Returns:
        JSON string: {"status": "saved", "note": {id, content, tags,
        created_at, updated_at}} or {"status": "error", "message": ...}.
    """
    if content is None or not str(content).strip():
        return _error("Note content must not be empty.")
    notes = _load_notes()
    now = _now()
    note = {
        "id": max((int(n.get("id", 0)) for n in notes), default=0) + 1,
        "content": str(content).strip(),
        "tags": _normalise_tags(tags),
        "created_at": now,
        "updated_at": now,
    }
    notes.append(note)
    _save_notes(notes)
    log.info("saved note id=%s", note["id"])
    return _ok({"status": "saved", "note": note})


@mcp.tool()
def search_notes(query: str) -> str:
    """Search the user's saved notes by keyword (case-insensitive).

    Use this to answer questions like "What did I say about the project
    deadline?" - pass the user's question or its key words as the query.
    Filler words (what, did, I, say, about, the, ...) are ignored. Notes are
    ranked by how many query keywords appear in their content and tags (tag
    matches count double), then newest first. Only matching notes are
    returned. An empty query or "*" returns every note.

    Args:
        query: Keywords or a natural-language question, e.g. "project deadline".

    Returns:
        JSON string: {"query": ..., "count": n, "results": [notes...]}.
        Each result also carries a "score" field showing match strength.
    """
    q = (query or "").strip()
    notes = _load_notes()
    if q in ("", "*"):
        results = _newest_first(notes)
        return _ok({"query": q, "count": len(results), "results": results})

    raw_tokens = _tokenise(q)
    tokens = [t for t in raw_tokens if t not in STOPWORDS]
    if not tokens:
        # Query was all filler words (e.g. "what did I say") - fall back to
        # the raw tokens rather than returning nothing useful.
        tokens = raw_tokens
    tokens = list(dict.fromkeys(tokens))  # dedupe, keep order

    scored: list[tuple[int, dict[str, Any]]] = []
    for n in notes:
        s = _score(n, tokens)
        if s > 0:
            scored.append((s, n))

    # Sort: score desc, then newest (created_at desc, id desc).
    scored.sort(
        key=lambda sn: (sn[0], sn[1].get("created_at", ""), sn[1].get("id", 0)),
        reverse=True,
    )
    results = [{**n, "score": s} for s, n in scored]
    log.info("search %r tokens=%s -> %d result(s)", q, tokens, len(results))
    return _ok({"query": q, "count": len(results), "results": results})


@mcp.tool()
def list_notes(tag: str | None = None) -> str:
    """List saved notes, newest first, optionally filtered by a single tag.

    Use this when the user wants to see everything they have saved, or all
    notes under one topic (e.g. tag="shopping").

    Args:
        tag: Optional tag to filter by (case-insensitive, exact tag match).
            Omit to list every note.

    Returns:
        JSON string: {"tag": tag-or-null, "count": n, "notes": [notes...]}.
    """
    notes = _load_notes()
    wanted = _normalise_tags([tag])[0] if tag and str(tag).strip() else None
    if wanted:
        notes = [n for n in notes if wanted in [str(t).lower() for t in n.get("tags", [])]]
    notes = _newest_first(notes)
    return _ok({"tag": wanted, "count": len(notes), "notes": notes})


@mcp.tool()
def update_note(
    note_id: int,
    content: str | None = None,
    tags: list[str] | None = None,
) -> str:
    """Update an existing note's content and/or tags.

    Use search_notes or list_notes first to find the note's id. Only the
    fields you pass are changed; tags, if given, REPLACE the existing tags.

    Args:
        note_id: The integer id of the note to update.
        content: New text for the note (optional; must be non-empty if given).
        tags: New list of tags (optional; replaces the old tags).

    Returns:
        JSON string: {"status": "updated", "note": {...}} or
        {"status": "error", "message": ...} if the id is unknown or the
        new content is empty.
    """
    try:
        note_id = int(note_id)
    except (TypeError, ValueError):
        return _error(f"Invalid note id: {note_id!r}.")
    if content is None and tags is None:
        return _error("Nothing to update: provide new content and/or tags.")
    if content is not None and not str(content).strip():
        return _error("Note content must not be empty.")
    notes = _load_notes()
    note = _find(notes, note_id)
    if note is None:
        return _error(f"No note with id {note_id}.")
    if content is not None:
        note["content"] = str(content).strip()
    if tags is not None:
        note["tags"] = _normalise_tags(tags)
    note["updated_at"] = _now()
    _save_notes(notes)
    log.info("updated note id=%s", note_id)
    return _ok({"status": "updated", "note": note})


@mcp.tool()
def delete_note(note_id: int) -> str:
    """Permanently delete a note by its id.

    Use search_notes or list_notes first to find the right id, and only
    delete when the user clearly asks to forget/remove a note.

    Args:
        note_id: The integer id of the note to delete.

    Returns:
        JSON string: {"status": "deleted", "note": {...deleted note...}} or
        {"status": "error", "message": ...} if the id is unknown.
    """
    try:
        note_id = int(note_id)
    except (TypeError, ValueError):
        return _error(f"Invalid note id: {note_id!r}.")
    notes = _load_notes()
    note = _find(notes, note_id)
    if note is None:
        return _error(f"No note with id {note_id}.")
    notes = [n for n in notes if n.get("id") != note_id]
    _save_notes(notes)
    log.info("deleted note id=%s", note_id)
    return _ok({"status": "deleted", "note": note})


if __name__ == "__main__":
    log.info("Starting personal-memory MCP server (notes file: %s)", _notes_path())
    mcp.run()
