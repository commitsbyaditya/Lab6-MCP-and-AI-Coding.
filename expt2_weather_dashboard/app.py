"""CS3235 Lab 6 - Experiment 2: MCP Weather Dashboard (Streamlit).

A small chat app that makes the MCP client <-> server interaction visible.
For every question the app:

1. spawns the weather MCP server (``weather_server.py``) over stdio,
2. discovers its tools and hands them to the LLM,
3. runs the agent loop, and renders each step *live*:
   thought -> tool call -> raw MCP server response -> final answer.

Run from the ``Lab6`` folder:

    python -m streamlit run expt2_weather_dashboard/app.py
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import threading
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st  # noqa: E402
from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

from common.agent_loop import run_agent_turn  # noqa: E402
from common.llm import LLMClient, LLMError  # noqa: E402
from common.mcp_tools import mcp_tools_to_openai, tool_result_to_text  # noqa: E402

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
SERVER_PATH = (Path(__file__).resolve().parent / "weather_server.py").resolve()

SYSTEM_PROMPT = (
    "You are a helpful weather assistant connected to a weather MCP server. "
    "For ANY question about weather, temperature, rain, forecasts or comparing "
    "places you MUST call the available tools (get_current_weather, "
    "get_forecast, compare_weather) instead of guessing. Never invent weather "
    "data. After receiving tool results, summarise them concisely (a few "
    "sentences or a short list) and add practical advice, e.g. whether to "
    "carry an umbrella, wear a jacket, or use sunscreen."
)

EXAMPLE_PROMPTS = [
    "What's the weather in Tokyo?",
    "Should I carry an umbrella in Bengaluru tomorrow?",
    "Compare the weather in London, Dubai and Singapore",
]

CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"


def circled(n: int) -> str:
    return CIRCLED[n - 1] if 1 <= n <= len(CIRCLED) else f"({n})"


def server_params() -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_PATH)],
        env={**os.environ},
    )


# --------------------------------------------------------------------------- #
# Async helpers
# --------------------------------------------------------------------------- #
def run_async(coro_factory: Callable[[], Any]) -> Any:
    """Run a coroutine from Streamlit's script thread.

    ``asyncio.run`` normally works (Windows uses the Proactor loop, which
    supports subprocesses). If a loop is already running in this thread we
    fall back to a fresh thread with its own loop, attaching the Streamlit
    script context so live ``st.*`` calls from callbacks still work.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro_factory())

    from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx

    result: dict[str, Any] = {}

    def target() -> None:
        try:
            if sys.platform == "win32":
                loop = asyncio.ProactorEventLoop()
            else:
                loop = asyncio.new_event_loop()
            try:
                result["value"] = loop.run_until_complete(coro_factory())
            finally:
                loop.close()
        except BaseException as exc:  # noqa: BLE001
            result["error"] = exc

    t = threading.Thread(target=target, daemon=True)
    add_script_run_ctx(t, get_script_run_ctx())
    t.start()
    t.join()
    if "error" in result:
        raise result["error"]
    return result.get("value")


async def discover_tools() -> list[dict[str, str]]:
    async with stdio_client(server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            return [
                {"name": t.name, "description": (t.description or "").strip()}
                for t in listed.tools
            ]


# --------------------------------------------------------------------------- #
# Rule-based fallback router
# --------------------------------------------------------------------------- #
CITY_RE = re.compile(
    r"\b(?:in|at|for)\s+([A-Za-z][A-Za-z .'\-]*?)"
    r"(?=\s+(?:today|tomorrow|now|tonight|this|next|right|and|or)\b|[?.!,;]|$)",
    re.IGNORECASE,
)


def extract_city(text: str) -> str | None:
    m = CITY_RE.search(text.strip())
    if m:
        city = m.group(1).strip(" .'-")
        if city and city.lower() not in {"the", "a", "my"}:
            return city
    return None


# --------------------------------------------------------------------------- #
# Step rendering (shared by live view and history)
# --------------------------------------------------------------------------- #
def render_step(n: int, kind: str, data: dict[str, Any]) -> None:
    if kind == "thinking":
        st.markdown(f"**{circled(n)} 🧠 Thought**")
        text = (data.get("text") or "").strip() or "_(no reasoning text)_"
        st.markdown("\n".join("> " + line for line in text.splitlines()) or "> ")
    elif kind == "tool_call":
        st.markdown(f"**{circled(n)} 🔧 Tool call: `{data.get('name', '?')}`**")
        args = data.get("arguments")
        if isinstance(args, str):
            try:
                args = json.loads(args) if args.strip() else {}
            except json.JSONDecodeError:
                pass
        if isinstance(args, (dict, list)):
            st.json(args)
        else:
            st.code(str(args))
    elif kind == "tool_result":
        st.markdown(f"**{circled(n)} 📦 MCP server response** (`{data.get('name', '?')}`)")
        st.code(str(data.get("text", "")), language="text")
    elif kind == "answer":
        st.markdown(f"**{circled(n)} 💬 Final answer**")
        st.markdown(str(data.get("text", "")))
    elif kind == "warning":
        st.warning(str(data.get("text", "")))
    else:
        st.markdown(f"**{circled(n)} {kind}**")
        st.write(data)


def render_steps(steps: list[dict[str, Any]]) -> None:
    n = 0
    for step in steps:
        if step["kind"] != "warning":
            n += 1
        render_step(n, step["kind"], step["data"])


def render_trace(messages: list[dict[str, Any]]) -> None:
    with st.expander("🔍 Raw message trace (JSON)", expanded=False):
        st.json(json.dumps(messages, default=str, ensure_ascii=False))


# --------------------------------------------------------------------------- #
# One query = one MCP session
# --------------------------------------------------------------------------- #
async def answer_query(
    question: str,
    llm: LLMClient | None,
    history: list[dict[str, Any]],
    on_event: Callable[[str, dict[str, Any]], None],
    llm_error: str | None = None,
) -> tuple[str, list[dict[str, Any]], bool]:
    """Returns (answer, updated_messages, used_fallback)."""
    async with stdio_client(server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            tools = mcp_tools_to_openai(listed.tools)

            if llm is not None:
                messages = [dict(m) for m in history]
                messages.append({"role": "user", "content": question})
                try:
                    answer = await run_agent_turn(
                        session, llm, messages, tools, on_event=on_event, max_steps=5
                    )
                    return answer, messages, False
                except LLMError as exc:
                    llm_error = str(exc)

            # ---- Fallback: rule-based router --------------------------------
            on_event(
                "warning",
                {"text": f"LLM unavailable — using rule-based router. ({llm_error})"},
            )
            city = extract_city(question)
            if not city:
                answer = (
                    "I couldn't find a city in your question. Try e.g. "
                    "*What's the weather in Tokyo?*"
                )
                on_event("answer", {"text": answer})
            else:
                on_event(
                    "thinking",
                    {"text": f"Rule-based router: matched city '{city}' → get_current_weather."},
                )
                args = {"location": city}
                on_event("tool_call", {"name": "get_current_weather", "arguments": args})
                result = await session.call_tool("get_current_weather", args)
                text = tool_result_to_text(result)
                on_event("tool_result", {"name": "get_current_weather", "text": text})
                answer = f"```text\n{text}\n```"
                on_event("answer", {"text": answer})
            messages = [dict(m) for m in history]
            messages.append({"role": "user", "content": question})
            messages.append({"role": "assistant", "content": answer})
            return answer, messages, True


# --------------------------------------------------------------------------- #
# Page
# --------------------------------------------------------------------------- #
st.set_page_config(page_title="MCP Weather Dashboard", page_icon="🌦️", layout="wide")
st.title("🌦️ MCP Weather Dashboard")
st.caption(
    "Client (this app + LLM) ⇄ **MCP Server** (`weather_server.py`, stdio) ⇄ "
    "**wttr.in**. Every step of the agent — its thought, the tool call, the raw "
    "MCP response and the final answer — is shown below."
)

ss = st.session_state
ss.setdefault("turns", [])  # [{question, steps, answer, trace}]
ss.setdefault("messages", [{"role": "system", "content": SYSTEM_PROMPT}])
ss.setdefault("pending", None)

# LLM client (created once per session)
if "llm" not in ss:
    try:
        ss.llm = LLMClient()
        ss.llm_desc = ss.llm.describe()
        ss.llm_init_error = None
    except LLMError as exc:
        ss.llm = None
        ss.llm_desc = "unavailable"
        ss.llm_init_error = str(exc)
    except Exception as exc:  # noqa: BLE001
        ss.llm = None
        ss.llm_desc = "unavailable"
        ss.llm_init_error = f"{type(exc).__name__}: {exc}"

# Tool discovery (once per session)
if "tools_info" not in ss:
    try:
        ss.tools_info = run_async(discover_tools)
        ss.tools_error = None
    except Exception as exc:  # noqa: BLE001  (incl. ExceptionGroup from anyio)
        ss.tools_info = []
        ss.tools_error = f"{type(exc).__name__}: {exc}"

# ---- Sidebar ---------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Setup")
    st.markdown(f"**LLM backend:** `{ss.llm_desc}`")
    if ss.llm_init_error:
        st.warning(f"LLM init failed: {ss.llm_init_error}")
    st.markdown("**MCP server:**")
    st.code(str(SERVER_PATH), language="text")

    st.subheader("🧰 Discovered tools")
    if ss.tools_error:
        st.error(f"Could not list tools: {ss.tools_error}")
    for t in ss.tools_info:
        st.markdown(f"- **`{t['name']}`** — {t['description'].splitlines()[0] if t['description'] else ''}")
    if st.button("🔄 Refresh tools", use_container_width=True):
        ss.pop("tools_info", None)
        st.rerun()

    st.subheader("💡 Try an example")
    for i, prompt in enumerate(EXAMPLE_PROMPTS):
        if st.button(prompt, key=f"example_{i}", use_container_width=True):
            ss.pending = prompt

    st.divider()
    if st.button("🗑️ Clear chat", use_container_width=True):
        ss.turns = []
        ss.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        ss.pending = None
        st.rerun()

# ---- History ---------------------------------------------------------------
for turn in ss.turns:
    with st.chat_message("user"):
        st.markdown(turn["question"])
    with st.chat_message("assistant"):
        with st.expander(f"🧩 Agent steps ({len(turn['steps'])})", expanded=False):
            render_steps(turn["steps"])
        st.markdown(turn["answer"])
    render_trace(turn["trace"])

# ---- New query -------------------------------------------------------------
typed = st.chat_input("Ask about the weather, e.g. What's the weather in Tokyo?")
question = typed or ss.pending
ss.pending = None

if question:
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        steps: list[dict[str, Any]] = []
        status = st.status("Agent working…", expanded=True)
        counter = {"n": 0}

        def on_event(kind: str, data: dict[str, Any]) -> None:
            data = dict(data or {})
            steps.append({"kind": kind, "data": data})
            with status:
                if kind == "warning":
                    render_step(0, kind, data)
                else:
                    counter["n"] += 1
                    render_step(counter["n"], kind, data)

        try:
            answer, new_messages, used_fallback = run_async(
                lambda: answer_query(
                    question, ss.llm, ss.messages, on_event, ss.llm_init_error
                )
            )
            ss.messages = new_messages
            status.update(
                label="Done (rule-based fallback)" if used_fallback else "Agent finished ✅",
                state="complete",
                expanded=False,
            )
        except Exception as exc:  # noqa: BLE001  (incl. ExceptionGroup from anyio)
            answer = f"⚠️ Error while talking to the MCP server: `{type(exc).__name__}: {exc}`"
            new_messages = ss.messages + [{"role": "user", "content": question}]
            status.update(label="Failed ❌", state="error", expanded=True)

        st.markdown(answer)

    render_trace(new_messages)
    ss.turns.append(
        {"question": question, "steps": steps, "answer": answer, "trace": new_messages}
    )
