"""Tests for Experiment 1: the persistent notes MCP server.

Unit tests call the tool functions directly (FastMCP v1 leaves decorated
functions callable). One end-to-end test spawns the server over stdio and
talks to it with the official MCP client.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from pathlib import Path

import pytest

LAB_ROOT = Path(__file__).resolve().parent.parent
SERVER_PATH = LAB_ROOT / "expt1_memory_server" / "notes_server.py"


def _load_server():
    """Import notes_server.py from its path (the folder is not a package)."""
    spec = importlib.util.spec_from_file_location("notes_server_under_test", SERVER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def notes_file(tmp_path, monkeypatch):
    path = tmp_path / "notes.json"
    monkeypatch.setenv("NOTES_FILE", str(path))
    return path


@pytest.fixture
def server(notes_file):
    return _load_server()


def call(fn, *args, **kwargs) -> dict:
    """Call a tool function and decode its JSON string result."""
    raw = fn(*args, **kwargs)
    assert isinstance(raw, str), f"tool should return a JSON string, got {type(raw)}"
    return json.loads(raw)


def save(server, content, tags=None) -> dict:
    result = call(server.save_note, content, tags)
    assert result["status"] == "saved", result
    return result["note"]


# --------------------------------------------------------------------------- save


def test_save_creates_file_and_increments_ids(server, notes_file):
    assert not notes_file.exists()
    first = save(server, "First note")
    assert notes_file.exists()
    second = save(server, "Second note")

    assert first["content"] == "First note"
    for key in ("id", "content", "tags", "created_at", "updated_at"):
        assert key in first
    assert int(second["id"]) == int(first["id"]) + 1


def test_tags_are_lowercased_and_deduplicated(server):
    note = save(server, "Tagged note", ["Work", "work", "  URGENT ", "urgent"])
    assert sorted(note["tags"]) == ["urgent", "work"]
    assert len(note["tags"]) == len(set(note["tags"]))


def test_empty_content_is_an_error(server):
    for bad in ("", "   "):
        result = call(server.save_note, bad)
        assert result["status"] == "error"
        assert result["message"]


# --------------------------------------------------------------------------- search


def test_natural_question_finds_deadline_not_groceries(server):
    deadline = save(server, "The project deadline is Friday 3 October", ["project"])
    groceries = save(server, "Buy milk, eggs and bread", ["groceries"])

    result = call(server.search_notes, "What did I say about the project deadline?")
    ids = [r["id"] for r in result["results"]]

    assert result["query"] == "What did I say about the project deadline?"
    assert result["count"] == len(result["results"])
    assert deadline["id"] in ids
    assert groceries["id"] not in ids


def test_tag_hits_rank_first(server):
    body_only = save(server, "Remember to call the dentist")
    tagged = save(server, "Appointment on Monday at 10am", ["dentist"])
    result = call(server.search_notes, "dentist")
    ids = [r["id"] for r in result["results"]]
    assert set(ids) == {body_only["id"], tagged["id"]}
    assert ids[0] == tagged["id"]


@pytest.mark.parametrize("query", ["", "*"])
def test_empty_or_star_query_returns_all(server, query):
    save(server, "alpha")
    save(server, "beta")
    save(server, "gamma")
    result = call(server.search_notes, query)
    assert result["count"] == 3
    assert len(result["results"]) == 3


# --------------------------------------------------------------------------- list


def test_list_by_tag(server):
    a = save(server, "Standup at 9", ["work"])
    save(server, "Buy apples", ["groceries"])
    c = save(server, "Quarterly review", ["Work", "review"])

    def notes_of(result):
        notes = result.get("notes", result.get("results"))
        assert notes is not None, result
        return notes

    assert len(notes_of(call(server.list_notes))) == 3

    result = call(server.list_notes, "WORK")  # tag filter should be case-insensitive
    assert {n["id"] for n in notes_of(result)} == {a["id"], c["id"]}


# --------------------------------------------------------------------------- update / delete


def test_update_changes_content_and_updated_at(server):
    note = save(server, "Draft text", ["draft"])
    time.sleep(1.1)  # timestamps may have one-second resolution
    result = call(server.update_note, note["id"], content="Final text")
    assert result.get("status") != "error", result
    updated = result["note"]
    assert updated["id"] == note["id"]
    assert updated["content"] == "Final text"
    assert updated["tags"] == ["draft"]  # untouched when tags=None
    assert updated["created_at"] == note["created_at"]
    assert updated["updated_at"] != note["updated_at"]

    retag = call(server.update_note, note["id"], tags=["Final", "final"])["note"]
    assert retag["tags"] == ["final"]
    assert retag["content"] == "Final text"


def test_delete_removes_note(server):
    keep = save(server, "keep me")
    gone = save(server, "delete me")
    result = call(server.delete_note, gone["id"])
    assert result.get("status") != "error", result

    remaining = call(server.search_notes, "")
    ids = [r["id"] for r in remaining["results"]]
    assert ids == [keep["id"]]


@pytest.mark.parametrize("op", ["update", "delete"])
def test_unknown_id_is_an_error(server, op):
    save(server, "only note")
    if op == "update":
        result = call(server.update_note, 9999, content="x")
    else:
        result = call(server.delete_note, 9999)
    assert result["status"] == "error"
    assert result["message"]


# --------------------------------------------------------------------------- persistence


def test_persistence_across_fresh_import(server, notes_file):
    note = save(server, "Persist me across restarts", ["memory"])

    # The file on disk must be valid JSON containing the note.
    assert "Persist me across restarts" in notes_file.read_text(encoding="utf-8")
    json.loads(notes_file.read_text(encoding="utf-8"))

    fresh = _load_server()  # simulates a server restart
    result = call(fresh.search_notes, "restarts")
    assert [r["id"] for r in result["results"]] == [note["id"]]
    assert result["results"][0]["tags"] == ["memory"]


# --------------------------------------------------------------------------- end to end


def _tool_json(result) -> dict:
    assert not result.isError, result
    text = "".join(c.text for c in result.content if getattr(c, "type", "") == "text")
    return json.loads(text)


async def test_end_to_end_over_stdio(tmp_path):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    notes = tmp_path / "e2e_notes.json"
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_PATH)],
        env={**os.environ, "NOTES_FILE": str(notes)},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            names = {t.name for t in tools.tools}
            assert {"save_note", "search_notes"} <= names

            saved = _tool_json(await session.call_tool(
                "save_note",
                {"content": "The project deadline is Friday", "tags": ["Project"]},
            ))
            assert saved["status"] == "saved"
            assert saved["note"]["tags"] == ["project"]

            found = _tool_json(await session.call_tool(
                "search_notes", {"query": "When is the project deadline?"}
            ))
            assert found["count"] >= 1
            assert found["results"][0]["id"] == saved["note"]["id"]

    assert notes.exists()
