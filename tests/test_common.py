"""Unit tests for common/mcp_tools.py and common/agent_loop.py (fully offline)."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from mcp.types import CallToolResult, TextContent

LAB6 = Path(__file__).resolve().parent.parent
if str(LAB6) not in sys.path:
    sys.path.insert(0, str(LAB6))

from common.mcp_tools import mcp_tools_to_openai, tool_result_to_text  # noqa: E402
from common.agent_loop import run_agent_turn  # noqa: E402


# --------------------------------------------------------------------------- #
# mcp_tools_to_openai
# --------------------------------------------------------------------------- #
def test_mcp_tools_to_openai_converts_schema():
    schema = {
        "type": "object",
        "properties": {"location": {"type": "string"}},
        "required": ["location"],
    }
    tools = [
        SimpleNamespace(name="get_current_weather", description="Current weather", inputSchema=schema),
        SimpleNamespace(name="noop", description="Does nothing", inputSchema={"type": "object", "properties": {}}),
    ]
    out = mcp_tools_to_openai(tools)
    assert isinstance(out, list) and len(out) == 2
    first = out[0]
    assert first["type"] == "function"
    assert first["function"]["name"] == "get_current_weather"
    assert first["function"]["description"] == "Current weather"
    assert first["function"]["parameters"] == schema
    assert out[1]["function"]["name"] == "noop"
    # must be JSON-serialisable to be sent to an OpenAI-compatible API
    json.dumps(out)


def test_mcp_tools_to_openai_empty():
    assert mcp_tools_to_openai([]) == []


# --------------------------------------------------------------------------- #
# tool_result_to_text
# --------------------------------------------------------------------------- #
def test_tool_result_to_text_joins_text_content():
    result = CallToolResult(
        content=[TextContent(type="text", text="hello"), TextContent(type="text", text="world")],
        isError=False,
    )
    text = tool_result_to_text(result)
    assert "hello" in text and "world" in text
    assert text.index("hello") < text.index("world")
    assert not text.startswith("ERROR")


def test_tool_result_to_text_error_prefix():
    result = CallToolResult(content=[TextContent(type="text", text="boom")], isError=True)
    text = tool_result_to_text(result)
    assert text.startswith("ERROR: ")
    assert "boom" in text


def test_tool_result_to_text_simple_namespace():
    fake = SimpleNamespace(content=[SimpleNamespace(type="text", text="ok")], isError=False)
    assert "ok" in tool_result_to_text(fake)


# --------------------------------------------------------------------------- #
# run_agent_turn
# --------------------------------------------------------------------------- #
class FakeLLM:
    """Scripted LLM: first asks for a tool call, then answers."""

    def __init__(self):
        self.calls = []
        self.script = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "get_current_weather",
                            "arguments": json.dumps({"location": "Tokyo"}),
                        },
                    }
                ],
                "reasoning": "I should call the tool",
            },
            {
                "role": "assistant",
                "content": "It is 26°C in Tokyo.",
                "tool_calls": [],
                "reasoning": None,
            },
        ]

    def chat(self, messages, tools):
        # snapshot so later in-place mutation doesn't affect our record
        self.calls.append([dict(m) for m in messages])
        return self.script.pop(0)


class FakeSession:
    def __init__(self):
        self.calls = []

    async def call_tool(self, name, args=None, *a, **kw):
        self.calls.append((name, args))
        return CallToolResult(
            content=[TextContent(type="text", text="Temperature: 26°C (feels like 28°C)")],
            isError=False,
        )


async def test_run_agent_turn_event_order_and_messages():
    llm = FakeLLM()
    session = FakeSession()
    messages = [{"role": "user", "content": "Weather in Tokyo?"}]
    tools = [{"type": "function", "function": {"name": "get_current_weather", "description": "", "parameters": {}}}]
    events = []

    answer = await run_agent_turn(
        session, llm, messages, tools, on_event=lambda kind, data: events.append((kind, data))
    )

    # return value
    assert answer == "It is 26°C in Tokyo."

    # tool executed with parsed args
    assert session.calls == [("get_current_weather", {"location": "Tokyo"})]
    assert len(llm.calls) == 2

    # event order: thinking -> tool_call -> tool_result -> answer
    kinds = [k for k, _ in events]
    assert kinds == ["thinking", "tool_call", "tool_result", "answer"], kinds
    assert "I should call the tool" in str(events[0][1])
    assert "get_current_weather" in str(events[1][1])
    assert "26" in str(events[2][1])
    assert "26°C in Tokyo" in str(events[3][1])

    # messages mutated in place: assistant(tool_calls) -> tool -> assistant(answer)
    tool_msgs = [m for m in messages if m.get("role") == "tool"]
    assert len(tool_msgs) == 1
    assert tool_msgs[0]["tool_call_id"] == "call_1"
    assert "26" in tool_msgs[0]["content"]
    roles = [m["role"] for m in messages]
    assert roles[0] == "user"
    assert roles.index("tool") > 0 and roles[roles.index("tool") - 1] == "assistant"
    assert messages[-1]["role"] == "assistant"
    assert messages[-1]["content"] == "It is 26°C in Tokyo."

    # second LLM call must have seen the tool result
    assert any(m.get("role") == "tool" for m in llm.calls[1])


async def test_run_agent_turn_no_tools_direct_answer():
    class DirectLLM:
        def chat(self, messages, tools):
            return {"role": "assistant", "content": "Hi!", "tool_calls": [], "reasoning": None}

    session = FakeSession()
    messages = [{"role": "user", "content": "hello"}]
    events = []
    answer = await run_agent_turn(session, DirectLLM(), messages, [], on_event=lambda k, d: events.append(k))
    assert answer == "Hi!"
    assert session.calls == []
    assert events[-1] == "answer"
    assert "tool_call" not in events


async def test_run_agent_turn_stops_after_max_steps():
    class LoopingLLM:
        def __init__(self):
            self.n = 0

        def chat(self, messages, tools=None):
            self.n += 1
            if tools is None:  # final "no tools" call after max_steps
                return {"role": "assistant", "content": "giving up", "tool_calls": [], "reasoning": None}
            return {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"id": f"c{self.n}", "type": "function",
                                "function": {"name": "get_current_weather", "arguments": "not json"}}],
                "reasoning": None,
            }

    llm = LoopingLLM()
    session = FakeSession()
    messages = [{"role": "user", "content": "loop forever"}]
    answer = await run_agent_turn(session, llm, messages, [{"type": "function"}], max_steps=2)
    assert answer == "giving up"
    assert len(session.calls) == 2
    # broken JSON arguments must degrade to {} rather than crash
    assert session.calls[0] == ("get_current_weather", {})
    assert messages[-1] == {"role": "assistant", "content": "giving up"}
