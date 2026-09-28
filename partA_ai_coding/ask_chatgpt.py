"""Send every Exp 6 prompt to OpenAI's GPT model and save the raw answers.

Uses the same LLMClient as the MCP experiments. With no API key set it falls back
to the free keyless Pollinations endpoint, which serves OpenAI's gpt-oss-20b.

    python partA_ai_coding/ask_chatgpt.py            # all subtasks
    python partA_ai_coding/ask_chatgpt.py subtask2   # just one
"""

import json
import os
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # so `common` is importable

from common.llm import LLMClient  # noqa: E402
from prompts import PROMPTS  # noqa: E402

OUT_DIR = os.path.join(HERE, "responses")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    wanted = sys.argv[1:] or list(PROMPTS)
    client = LLMClient()
    print("Model:", client.describe())

    for key in wanted:
        print(f"-> {key} ...", flush=True)
        reply = client.chat([{"role": "user", "content": PROMPTS[key]}])
        answer = reply["content"] or ""
        with open(os.path.join(OUT_DIR, f"chatgpt_{key}.md"), "w", encoding="utf-8") as fh:
            fh.write(answer)
        with open(os.path.join(OUT_DIR, f"chatgpt_{key}.meta.json"), "w", encoding="utf-8") as fh:
            json.dump({"model": client.describe(),
                       "time": datetime.now().isoformat(timespec="seconds"),
                       "prompt": PROMPTS[key]}, fh, indent=2)
        print(f"   saved {len(answer)} chars")


if __name__ == "__main__":
    main()
