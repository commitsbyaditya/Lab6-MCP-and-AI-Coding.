"""CS3235 Lab 6 - Experiment 1: MCP client for the personal notes (memory) server.

Connects to notes_server.py over stdio, discovers its tools, and lets an LLM
decide whether to save_note, search_notes, list_notes, update_note or
delete_note for each user query. If the LLM is unavailable, a clearly
labelled rule-based router is used instead.

Usage:
    python notes_client.py                       # interactive REPL
    python notes_client.py --query "What did I say about the project deadline?"
    python notes_client.py --demo
    python notes_client.py --notes-file my_notes.json --demo
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Windows consoles default to cp1252; emoji panels need UTF-8.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass

from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.markdown import Markdown  # noqa: E402
from rich.panel import Panel  # noqa: E402
from rich.syntax import Syntax  # noqa: E402
from rich.table import Table  # noqa: E402
from rich.text import Text  # noqa: E402

from common.agent_loop import run_agent_turn  # noqa: E402
from common.llm import LLMClient, LLMError  # noqa: E402
from common.mcp_tools import mcp_tools_to_openai, tool_result_to_text  # noqa: E402

SERVER_PATH = Path(__file__).resolve().parent / "notes_server.py"

DEMO_QUERIES = [
    "Remember that the project deadline for Lab 6 is Friday 25 September and I must "
    "upload the GitHub URL and screenshots",
    "What did I say about the project deadline?",
    "Note that I need to buy milk and eggs tomorrow",
    "Show me all my notes tagged shopping",
]

console = Console()


def build_system_prompt() -> str:
    today = date.today()
    return (
        "You are a personal memory assistant backed by a notes server (MCP tools).\n"
        f"Today's date is {today.isoformat()} ({today.strftime('%A')}).\n\n"
        "Rules:\n"
        "1. When the user states a fact, reminder or plan (e.g. 'remember ...', 'note that ...', "
        "'I have ...', 'don't let me forget ...'), call save_note with the content rewritten as a "
        "clear, self-contained note and 1-3 short lowercase tags you infer (e.g. 'deadline', "
        "'lab6', 'shopping'). Resolve relative dates like 'tomorrow' using today's date.\n"
        "2. When the user asks about anything personal or anything they may have told you before, "
        "ALWAYS call search_notes first with the key words of the question (e.g. 'project "
        "deadline'). You have no memory of your own: never answer such a question, or claim a "
        "note does not exist, without searching first. If they ask for notes with a "
        "specific tag or for all notes, call list_notes (with tag if given).\n"
        "3. Use update_note / delete_note only when the user explicitly asks to change or remove "
        "a note; find its id first with search_notes or list_notes if needed.\n"
        "4. Answer ONLY from the tool results. Never invent notes. Search results are ranked by "
        "relevance and can include loosely related notes: use every result that answers the "
        "question (mention each relevant note, most relevant first) and ignore the rest. If a "
        "search returns nothing relevant, say plainly that you have no saved note about it.\n"
        "5. After saving, briefly confirm what was saved and with which tags.\n"
        "Keep answers short and friendly."
    )


# --------------------------------------------------------------------------- rendering


def _json_or_text(text: str):
    """Return a renderable: syntax-highlighted JSON if parseable, else plain text."""
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError):
        return Text(str(text))
    return Syntax(json.dumps(parsed, indent=2, ensure_ascii=False), "json",
                  theme="monokai", word_wrap=True)


def on_event(kind: str, data: dict) -> None:
    if kind == "thinking":
        text = (data.get("text") or "").strip()
        if text:
            console.print(Panel(Text(text, style="dim"), title="🧠 LLM thought",
                                border_style="dim", title_align="left"))
    elif kind == "tool_call":
        args = data.get("arguments")
        if not isinstance(args, str):
            args = json.dumps(args, ensure_ascii=False)
        line = Text()
        line.append("🔧 Tool call → ", style="bold yellow")
        line.append(str(data.get("name")), style="bold cyan")
        line.append(" " + args, style="yellow")
        console.print(line)
    elif kind == "tool_result":
        console.print(Panel(_json_or_text(data.get("text", "")),
                            title=f"📦 Tool result ({data.get('name')})",
                            border_style="blue", title_align="left"))
    elif kind == "answer":
        console.print(Panel(Markdown(data.get("text") or "(no answer)"), title="💬 Answer",
                            border_style="green", title_align="left"))


def print_header(server_name: str, tools, llm_desc: str) -> None:
    table = Table(show_header=True, header_style="bold magenta", expand=True)
    table.add_column("Tool", style="cyan", no_wrap=True)
    table.add_column("Description")
    for t in tools:
        desc = (t.description or "").strip().splitlines()
        table.add_row(t.name, desc[0] if desc else "")
    body = Table.grid(padding=(0, 1))
    body.add_row(Text("MCP server:", style="bold"), Text(server_name))
    body.add_row(Text("LLM backend:", style="bold"), Text(llm_desc))
    body.add_row(Text("Tools found:", style="bold"), Text(str(len(tools))))
    console.print(Panel(body, title="📝 Expt 1 - Personal Memory Notes Client",
                        border_style="magenta", title_align="left"))
    console.print(table)


# --------------------------------------------------------------------------- fallback router

_TAG_PATTERN = re.compile(r"\btagged\s+['\"]?([\w-]+)", re.IGNORECASE)
# A save request starts with a command word ("Remember that ...", "Please note
# that ..."). Questions such as "What did I save about milk?" are searches.
_LEADING = re.compile(r"^\s*(please\s+)?(remember( that)?|note( that)?|save( a note)?( that)?|"
                      r"add( a note)?( that)?)\b[\s:,-]*", re.IGNORECASE)
_TAG_KEYWORDS = {
    "deadline": ["deadline", "due", "submit", "upload"],
    "lab6": ["lab 6", "lab6"],
    "shopping": ["buy", "milk", "eggs", "grocery", "groceries", "shop"],
    "meeting": ["meeting", "call", "meet"],
    "project": ["project"],
}


def _infer_tags(text: str) -> list[str]:
    low = text.lower()
    tags = [tag for tag, words in _TAG_KEYWORDS.items() if any(w in low for w in words)]
    return tags[:3] or ["general"]


async def fallback_route(session: ClientSession, query: str, reason: str) -> str:
    console.print(Panel(Text(f"[fallback router: LLM unavailable]\nReason: {reason}",
                             style="bold red"), border_style="red", title_align="left"))
    tag_match = _TAG_PATTERN.search(query)
    if _LEADING.match(query) and not query.rstrip().endswith("?"):
        content = _LEADING.sub("", query).strip() or query.strip()
        content = content[0].upper() + content[1:] if content else content
        name, args = "save_note", {"content": content, "tags": _infer_tags(query)}
    elif tag_match:
        name, args = "list_notes", {"tag": tag_match.group(1).lower()}
    else:
        name, args = "search_notes", {"query": query}

    on_event("tool_call", {"name": name, "arguments": args})
    result = await session.call_tool(name, args)
    text = tool_result_to_text(result)
    on_event("tool_result", {"name": name, "text": text})
    answer = f"[fallback router: LLM unavailable] Called {name}; raw result shown above."
    on_event("answer", {"text": answer})
    return answer


# --------------------------------------------------------------------------- main loop


async def handle_query(session, llm, messages, tools, query: str) -> None:
    console.print(Text(f"You> {query}", style="bold white"))
    checkpoint = len(messages)
    if llm is not None:
        messages.append({"role": "user", "content": query})
        try:
            await run_agent_turn(session, llm, messages, tools, on_event=on_event, max_steps=5)
            return
        except LLMError as exc:
            del messages[checkpoint:]  # drop any half-finished turn
            reason = str(exc)
    else:
        reason = "no LLM backend configured"
    answer = await fallback_route(session, query, reason)
    messages.append({"role": "user", "content": query})
    messages.append({"role": "assistant", "content": answer})


async def main_async(args) -> None:
    env = {**os.environ}
    if args.notes_file:
        env["NOTES_FILE"] = str(Path(args.notes_file).resolve())
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER_PATH)], env=env)

    try:
        llm = LLMClient()
        llm_desc = llm.describe()
    except LLMError as exc:
        llm, llm_desc = None, f"unavailable ({exc}) - using fallback router"

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            server_name = getattr(getattr(init, "serverInfo", None), "name", None) or "notes"
            mcp_tools = (await session.list_tools()).tools
            tools = mcp_tools_to_openai(mcp_tools)
            print_header(server_name, mcp_tools, llm_desc)

            messages: list[dict] = [{"role": "system", "content": build_system_prompt()}]

            scripted = DEMO_QUERIES if args.demo else (args.query or [])
            if scripted:
                for i, q in enumerate(scripted, 1):
                    console.rule(f"[bold]Query {i}/{len(scripted)}")
                    await handle_query(session, llm, messages, tools, q)
                return

            console.print("[dim]Type a message (e.g. 'Remember that ...' or "
                          "'What did I say about ...?'). 'exit' or 'quit' to stop.[/dim]")
            while True:
                try:
                    q = await asyncio.to_thread(input, "You> ")
                except (EOFError, KeyboardInterrupt):
                    break
                q = q.strip()
                if not q:
                    continue
                if q.lower() in {"exit", "quit"}:
                    break
                try:
                    await handle_query(session, llm, messages, tools, q)
                except Exception as exc:  # keep the REPL alive
                    console.print(f"[red]Error: {exc}[/red]")
            console.print("[dim]Bye.[/dim]")


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="MCP notes client (CS3235 Lab 6, Expt 1)")
    p.add_argument("--query", action="append",
                   help="Run this query non-interactively (repeatable), then exit.")
    p.add_argument("--demo", action="store_true", help="Run the scripted demo sequence.")
    p.add_argument("--notes-file", help="Path of the JSON notes file (sets NOTES_FILE).")
    return p.parse_args(argv)


def main() -> None:
    args = parse_args()
    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
