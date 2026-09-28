"""Helpers that translate between MCP objects and OpenAI tool-calling format."""


def mcp_tools_to_openai(tools) -> list[dict]:
    """Convert MCP tool definitions into OpenAI "function" tool specs.

    `tools` is the list from `(await session.list_tools()).tools`.
    """
    converted = []
    for t in tools:
        schema = t.inputSchema or {"type": "object", "properties": {}}
        converted.append({
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description or "",
                "parameters": schema,
            },
        })
    return converted


def tool_result_to_text(result) -> str:
    """Flatten a CallToolResult into plain text the LLM can read."""
    parts = [item.text for item in (result.content or []) if getattr(item, "type", None) == "text"]
    text = "\n".join(parts)
    if getattr(result, "isError", False):
        return "ERROR: " + text
    return text
