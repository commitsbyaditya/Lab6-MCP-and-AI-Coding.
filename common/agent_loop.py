"""The classic tool-calling agent loop, shared by every client in the lab.

    user question -> LLM -> (tool calls -> MCP server -> results -> LLM)* -> answer
"""

import json

from common.mcp_tools import tool_result_to_text


def _parse_arguments(raw) -> dict:
    """LLMs sometimes emit broken JSON; never let that crash the loop."""
    if isinstance(raw, dict):
        return raw
    try:
        args = json.loads(raw or "{}")
        return args if isinstance(args, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


async def run_agent_turn(session, llm, messages: list[dict], tools: list[dict],
                         on_event=None, max_steps: int = 5) -> str:
    """Answer the latest user message, calling MCP tools as needed.

    `messages` is extended in place so the caller keeps the full history.
    `on_event(kind, data)` is an optional callback for showing progress in a UI.
    """
    def emit(kind, data):
        if on_event:
            on_event(kind, data)

    for _ in range(max_steps):
        reply = llm.chat(messages, tools)

        # No tool calls means the model is done: this is the final answer.
        if not reply["tool_calls"]:
            answer = reply["content"] or ""
            messages.append({"role": "assistant", "content": answer})
            emit("answer", {"text": answer})
            return answer

        # Show any "thinking" that came along with the tool calls.
        thought = reply["reasoning"] or reply["content"]
        if thought:
            emit("thinking", {"text": thought})

        # Record the assistant's request (without the reasoning field).
        messages.append({
            "role": "assistant",
            "content": reply["content"],
            "tool_calls": reply["tool_calls"],
        })

        # Run each requested tool on the MCP server and feed the result back.
        for call in reply["tool_calls"]:
            name = call["function"]["name"]
            args = _parse_arguments(call["function"]["arguments"])
            emit("tool_call", {"name": name, "arguments": args})
            try:
                result = await session.call_tool(name, args)
                text = tool_result_to_text(result)
            except Exception as e:  # keep going; let the LLM see the error
                text = f"ERROR: {e}"
            emit("tool_result", {"name": name, "text": text})
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": text})

    # Ran out of steps: ask once more with no tools so we still get an answer.
    reply = llm.chat(messages)
    answer = reply["content"] or "(stopped: too many tool calls)"
    messages.append({"role": "assistant", "content": answer})
    emit("answer", {"text": answer})
    return answer
