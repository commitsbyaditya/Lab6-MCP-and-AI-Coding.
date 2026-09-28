"""Extract the code from every AI response, run it, and save the console output.

    python partA_ai_coding/run_all.py

Writes code/<tool>_<subtask>.py and outputs/<name>.txt. Programs that call input()
get their answers from a fixed list, and each answer is echoed after its prompt so
the saved output looks like an interactive run.
"""

import builtins
import contextlib
import io
import os
import re
import runpy
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from prompts import FAULTY_CODE, ORIGINAL_CODE, UNDOCUMENTED_CODE  # noqa: E402

RESP = os.path.join(HERE, "responses")
CODE = os.path.join(HERE, "code")
OUT = os.path.join(HERE, "outputs")

# Same class for every interactive program, so the tools can be compared.
CLASS_INPUT = ["5", "Aditya", "78", "Priya", "64", "Rohan", "35", "Sneha", "91", "Karan", "29"]
MENU_INPUT = ["1", "Asha", "85", "1", "Rahul", "38", "1", "Meena", "92", "1", "Kiran", "25",
              "2", "3", "4", "5"]

# Subtask 4 is only functions, so it is imported and called by this driver.
DOC_DRIVER = '''
marks = {"Asha": 85, "Rahul": 72, "Meena": 38, "Vikram": 91}
print("calculate_average ->", calculate_average(marks))
print("get_topper        ->", get_topper(marks))
print("get_failed_students ->", get_failed_students(marks))
print()
help(calculate_average)
'''

# name -> (source, stdin answers, extra code appended before running)
RUNS = {
    "subtask1_claude": ("claude_subtask1", CLASS_INPUT, ""),
    "subtask1_chatgpt": ("chatgpt_subtask1", CLASS_INPUT, ""),
    "subtask2_faulty": (FAULTY_CODE, [], ""),
    "subtask2_claude": ("claude_subtask2", [], ""),
    "subtask2_chatgpt": ("chatgpt_subtask2", [], ""),
    "subtask3_original": (ORIGINAL_CODE, [], ""),
    "subtask3_claude": ("claude_subtask3", [], ""),
    "subtask3_chatgpt": ("chatgpt_subtask3", [], ""),
    "subtask4_undocumented": (UNDOCUMENTED_CODE, [], DOC_DRIVER.replace("help(calculate_average)", "")),
    "subtask4_claude": ("claude_subtask4", [], DOC_DRIVER),
    "subtask4_chatgpt": ("chatgpt_subtask4", [], DOC_DRIVER),
    "subtask5_claude": ("claude_subtask5", [], ""),
    "subtask5_chatgpt": ("chatgpt_subtask5", MENU_INPUT, ""),
}


def first_python_block(markdown):
    match = re.search(r"```python\n(.*?)```", markdown, re.S)
    if not match:
        raise ValueError("no ```python block found")
    return match.group(1).rstrip() + "\n"


def run_source(path, answers):
    """Run a script with scripted input() answers; return everything it printed."""
    queue = list(answers)
    buffer = io.StringIO()

    def fake_input(prompt=""):
        value = queue.pop(0)
        buffer.write(f"{prompt}{value}\n")
        return value

    real_input = builtins.input
    builtins.input = fake_input
    try:
        with contextlib.redirect_stdout(buffer):
            runpy.run_path(path, run_name="__main__")
    except Exception:
        # Keep the traceback short: only the frames from the student's file.
        etype, value, tb = sys.exc_info()
        frames = [f for f in traceback.extract_tb(tb) if f.filename == path]
        buffer.write("Traceback (most recent call last):\n")
        buffer.write("".join(traceback.format_list(frames)))
        buffer.write("".join(traceback.format_exception_only(etype, value)))
    finally:
        builtins.input = real_input
    return buffer.getvalue().replace(path, os.path.basename(path))


def main():
    os.makedirs(CODE, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    for name, (source, answers, extra) in RUNS.items():
        if source.startswith(("claude_", "chatgpt_")):
            with open(os.path.join(RESP, source + ".md"), encoding="utf-8") as fh:
                code = first_python_block(fh.read())
        else:
            code = source + "\n"
        path = os.path.join(CODE, name + ".py")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(code + extra)
        output = run_source(path, answers)
        with open(os.path.join(OUT, name + ".txt"), "w", encoding="utf-8") as fh:
            fh.write(output)
        print(f"===== {name}\n{output}")


if __name__ == "__main__":
    main()
