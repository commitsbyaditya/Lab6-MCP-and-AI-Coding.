# -*- coding: utf-8 -*-
"""Build the Lab 6 report: Lab6_1RVU23CSE029_WWLLM.docx

Part A  - lab manual Exp 6 (code generation, debugging, refactoring, documentation,
          tool comparison), using Claude Code and ChatGPT (OpenAI gpt-oss-20b).
Part B  - Classroom Lab_06 experiments: MCP memory server and MCP weather dashboard.

Every prompt, AI answer, code listing and program output is read from partA_ai_coding/
(written by ask_chatgpt.py, run_all.py and render.py), and the MCP code is read from
the source files, so the report always matches what was actually run.

    python build_report.py
"""

import ast
import os
import re
import sys

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_COLOR_INDEX
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from PIL import Image
from pygments import lex
from pygments.lexers import PythonLexer
from pygments.token import Comment, Keyword, Name, Number, Operator, String, Token

HERE = os.path.dirname(os.path.abspath(__file__))
A = os.path.join(HERE, "partA_ai_coding")
sys.path.insert(0, A)
from prompts import PROMPTS  # noqa: E402

NAME, USN = "Aditya Kumar", "1RVU23CSE029"
OUT_FILE = os.path.join(HERE, f"Lab6_{USN}_WWLLM.docx")
GITHUB_URL = "https://github.com/commitsbyaditya/Lab6-MCP-and-AI-Coding."

SERIF = "Times New Roman"
MONO = "Courier New"


def read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as fh:
        return fh.read()


def code_of(name):
    return read(A, "code", name + ".py").rstrip("\n")


def response(tool, subtask):
    return read(A, "responses", f"{tool}_{subtask}.md")


def img(name):
    return os.path.join(A, "images", name)


# --------------------------------------------------------------------------- #
# document helpers
# --------------------------------------------------------------------------- #
doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Inches(8.5), Inches(11)
for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
    setattr(sec, side, Inches(1))
normal = doc.styles["Normal"]
normal.font.name = SERIF
normal.font.size = Pt(12)
normal.element.rPr.rFonts.set(qn("w:eastAsia"), SERIF)
normal.paragraph_format.space_after = Pt(6)

FIG = 0


def shade(cell, hex_fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    tc_pr.append(shd)


def run(p, text, bold=False, italic=False, size=12, font=SERIF, color=None):
    r = p.add_run(text)
    r.bold, r.italic = bold, italic
    r.font.size = Pt(size)
    r.font.name = font
    r._element.rPr.rFonts.set(qn("w:eastAsia"), font)
    if color:
        r.font.color.rgb = RGBColor.from_string(color)
    return r


def para(text="", bold=False, size=12, align=None, italic=False, after=6):
    p = doc.add_paragraph()
    if align:
        p.alignment = align
    p.paragraph_format.space_after = Pt(after)
    if text:
        run(p, text, bold=bold, size=size, italic=italic)
    if bold:
        p.paragraph_format.keep_with_next = True  # never leave a label alone at a page end
    return p


def rich(text, size=12, align=None, style=None):
    """Paragraph where **bold** and `code` spans are formatted."""
    p = doc.add_paragraph(style=style)
    if align:
        p.alignment = align
    for part in re.split(r"(\*\*.+?\*\*|`[^`]+`)", text):
        if part.startswith("**"):
            run(p, part[2:-2], bold=True, size=size)
        elif part.startswith("`"):
            run(p, part[1:-1], size=size - 1.5, font=MONO)
        elif part:
            run(p, part, size=size)
    return p


def label(lbl, text):
    """'Step 1: Open ...' style line with a bold label."""
    p = doc.add_paragraph()
    p.paragraph_format.keep_with_next = True
    run(p, lbl, bold=True)
    run(p, " ")
    for part in re.split(r"(`[^`]+`)", text):
        if part.startswith("`"):
            run(p, part[1:-1], size=10.5, font=MONO)
        elif part:
            run(p, part)
    return p


def bullets(items):
    for it in items:
        rich(it, style="List Bullet")


def heading(text, size=14, before=12):
    p = para(text, bold=True, size=size, after=6)
    p.paragraph_format.space_before = Pt(before)
    p.paragraph_format.keep_with_next = True
    return p


def part_banner(text):
    t = doc.add_table(rows=1, cols=1)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    c = t.rows[0].cells[0]
    shade(c, "1F3864")
    p = c.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run(p, text, bold=True, size=14, color="FFFFFF")
    para(after=2)


# VS Code "Dark+" colours, as in the Colab screenshots.
PALETTE = [
    (Comment, "6A9955"), (String, "CE9178"), (Number, "B5CEA8"),
    (Keyword, "569CD6"), (Name.Builtin, "4EC9B0"), (Name.Function, "DCDCAA"),
    (Name.Class, "4EC9B0"), (Name.Decorator, "DCDCAA"), (Operator, "D4D4D4"),
]


def colour_for(tok):
    for base, hexcol in PALETTE:
        if tok in base:
            return hexcol
    return "D4D4D4"


def code_block(code, lang="python", size=9.5):
    """Dark, syntax-highlighted code listing in a one-cell table."""
    t = doc.add_table(rows=1, cols=1)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = t.rows[0].cells[0]
    shade(cell, "1E1E1E")
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = 1.0
    if lang == "python":
        tokens = lex(code, PythonLexer())
    else:
        tokens = [(Token.Text, code)]
    for tok, val in tokens:
        pieces = val.split("\n")
        for i, piece in enumerate(pieces):
            if i:
                p = cell.add_paragraph()
                p.paragraph_format.space_after = Pt(0)
                p.paragraph_format.line_spacing = 1.0
            if piece:
                run(p, piece.replace(" ", " "), size=size, font=MONO, color=colour_for(tok))
    # lex() adds a trailing newline -> drop an empty last paragraph
    if not cell.paragraphs[-1].text and len(cell.paragraphs) > 1:
        cell._tc.remove(cell.paragraphs[-1]._p)
    para(after=4)


def prompt_box(text):
    """Grey box holding the exact prompt; code lines in monospace."""
    t = doc.add_table(rows=1, cols=1)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = t.rows[0].cells[0]
    shade(cell, "F2F2F2")
    first = True
    in_code = False
    for line in text.splitlines():
        p = cell.paragraphs[0] if first else cell.add_paragraph()
        first = False
        p.paragraph_format.space_after = Pt(0)
        if re.match(r"^(def |students|total|avg|top|for |print|    |\}|\s*$)", line) and not line.startswith(("1.", "Goals")):
            in_code = in_code or bool(line.strip())
        if in_code:
            run(p, line.replace(" ", " "), size=10, font=MONO)
        else:
            run(p, line, italic=True, size=11.5)
    para(after=4)


def figure(path, caption, max_w=6.3, max_h=8.4):
    global FIG
    FIG += 1
    w, h = Image.open(path).size
    width = min(max_w, max_h * w / h)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(path, width=Inches(width))
    c = para(f"Figure {FIG}: {caption}", italic=True, size=10, align=WD_ALIGN_PARAGRAPH.CENTER)
    return c


def table(header, rows, widths=None, font_size=11):
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(header):
        c = t.rows[0].cells[i]
        shade(c, "D9E2F3")
        run(c.paragraphs[0], h, bold=True, size=font_size)
    for r in rows:
        cells = t.add_row().cells
        for i, v in enumerate(r):
            p = cells[i].paragraphs[0]
            for part in re.split(r"(`[^`]+`)", str(v)):
                if part.startswith("`"):
                    run(p, part[1:-1], size=font_size - 1.5, font=MONO)
                elif part:
                    run(p, part, size=font_size)
    if widths:
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Inches(w)
    para(after=4)
    return t


def md_section(md):
    """Render a small markdown fragment (headings, tables, code, bullets, text)."""
    lines = md.strip().splitlines()
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("```"):
            lang = ln[3:].strip() or "text"
            j = i + 1
            while not lines[j].startswith("```"):
                j += 1
            code_block("\n".join(lines[i + 1:j]), lang="python" if lang == "python" else "text")
            i = j + 1
            continue
        if ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                if not set(lines[i]) <= set("|-: "):
                    rows.append([c.strip() for c in lines[i].strip("|").split("|")])
                i += 1
            table(rows[0], rows[1:], font_size=10.5)
            continue
        if ln.startswith("#"):
            p = para(ln.lstrip("#").strip(), bold=True, size=12, after=3)
            p.paragraph_format.keep_with_next = True
        elif re.match(r"^\s*[-*] ", ln):
            rich(re.sub(r"^\s*[-*] ", "", ln), size=11.5, style="List Bullet")
        elif ln.strip():
            rich(ln, size=11.5)
        i += 1


def source_of(path, func_name):
    """Exact source of one top-level function, decorators included."""
    src = read(path)
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
            start = min([d.lineno for d in node.decorator_list] + [node.lineno])
            return "\n".join(src.splitlines()[start - 1:node.end_lineno])
    raise KeyError(func_name)


# --------------------------------------------------------------------------- #
# Title block (same layout as the class template)
# --------------------------------------------------------------------------- #
para("Experiment 6", bold=True, size=16, align=WD_ALIGN_PARAGRAPH.CENTER, after=2)
para("LLMs for Code Generation & Software Development", bold=True, size=12,
     align=WD_ALIGN_PARAGRAPH.CENTER, after=10)
para(NAME, align=WD_ALIGN_PARAGRAPH.RIGHT, after=0)
para(USN, align=WD_ALIGN_PARAGRAPH.RIGHT, after=10)

p = doc.add_paragraph()
run(p, "AIM:", bold=True)
run(p, " Using AI Coding Assistants for Code Generation, Debugging, Refactoring, Documentation, "
       "and Tool Comparison, and building Model Context Protocol (MCP) servers and clients that let "
       "an LLM call real tools (a personal notes store and a live weather API).")

para("OBJECTIVES:", bold=True, after=2)
para("After completing this experiment, the learner will be able to:", after=2)
bullets([
    "Use AI tools to generate working code from a problem statement.",
    "Debug faulty code using AI coding assistants.",
    "Refactor code for readability, modularity, and performance.",
    "Generate useful documentation and comments.",
    "Compare outputs from different AI tools on the same software task.",
    "Implement an MCP server that exposes CRUD tools over a local JSON file, and an MCP client "
    "in which an LLM decides which tool to call.",
    "Connect an LLM to a real-time public API through an MCP server and show the model's "
    "decision-making step by step in a web app.",
])

para("THEORY:", bold=True, after=2)
para("Large Language Models (LLMs) can assist in software development by generating code from "
     "natural-language requirements, identifying and fixing programming errors, improving existing "
     "code, and generating documentation. Because they are trained on large amounts of source code "
     "and explanations, AI coding assistants can turn a short problem statement into a working "
     "program and explain why a piece of code fails. Their output still has to be run and checked: "
     "a model can produce code that looks right but gives a wrong number, or a comment that does "
     "not match what the code does. In Part A, two AI tools are used on the same student marks "
     "management system, every answer is executed, and the tools are compared on correctness, "
     "readability, documentation and ease of understanding.")
para("The Model Context Protocol (MCP) is an open standard for connecting LLM applications to "
     "external tools and data. An MCP server exposes tools, each with a name, a description and a "
     "JSON-Schema for its inputs. An MCP client inside a host application lists these tools "
     "(tools/list), gives them to the LLM, and when the LLM asks for a tool it runs it on the "
     "server (tools/call) and returns the result to the LLM. The LLM never touches the data "
     "directly: it only decides which tool to call and with which arguments. Part B builds two "
     "such servers and clients using the MCP Python SDK (FastMCP).")

p = doc.add_paragraph()
run(p, "Tools used: ", bold=True)
run(p, "Claude Code (Claude Opus 5.5) and ChatGPT (OpenAI gpt-oss-20b, queried through the "
       "OpenAI-compatible chat API). The lab manual allows any two of Cursor, ChatGPT, GitHub "
       f"Copilot, Gemini and Claude. All programs were run with Python {sys.version.split()[0]} "
       "on Windows 11.")

# =========================================================================== #
# PART A
# =========================================================================== #
part_banner("PART A: AI Coding Assistants for Software Development")

# ---------------- Subtask 1 ----------------
heading("Subtask 1: Code Generation")
label("Objective:", "Use an AI assistant to generate Python code from a natural language requirement.")
para("STEPS:", bold=True, after=2)
label("Step 1:", "Open an AI Coding Assistant (Claude Code)")
label("Step 2:", "Give the following Prompt")
para("Prompt:", after=2)
prompt_box(PROMPTS["subtask1"])
figure(img("claude_subtask1_chat.png"), "Claude Code response to the code generation prompt")
label("Step 3:", "Run the output of Claude Code")
code_block(code_of("subtask1_claude"))
para("Output:", bold=True, after=2)
figure(img("subtask1_claude_output.png"), "Output of the generated program for a class of 5 students",
       max_w=4.6)
para("The same prompt was also given to ChatGPT and its program was run with the same five "
     "students, to check that the results agree:", after=4)
figure(img("subtask1_chatgpt_output.png"), "Output of ChatGPT's program for the same input", max_w=4.6)
para("OBSERVATION TABLE (verification of the generated code):", bold=True, after=2)
table(["Check", "Expected (by hand)", "Claude output", "ChatGPT output", "Correct?"], [
    ["Class average", "(78+64+35+91+29)/5 = 59.4", "59.4", "59.40", "Yes"],
    ["Topper", "Sneha, 91", "Sneha with 91.0 marks", "Sneha (91.0)", "Yes"],
    ["Students below 40", "Rohan (35), Karan (29)", "Rohan, Karan", "Rohan - 35.0, Karan - 29.0", "Yes"],
    ["Uses functions", "-", "4 functions + main()", "5 functions + main()", "Yes"],
    ["Input validation", "-", "None", "Count > 0, marks 0-100, non-numeric input", "-"],
], widths=[1.3, 1.6, 1.3, 1.6, 0.7], font_size=10.5)

# ---------------- Subtask 2 ----------------
heading("Subtask 2: Debugging Using AI")
label("Objective:", "Use an AI assistant to identify and correct errors in code.")
para("STEPS:", bold=True, after=2)
label("Step 1:", "Run the faulty code to see the error")
figure(img("subtask2_faulty_output.png"), "The faulty code fails with a TypeError", max_w=4.8)
label("Step 2:", "Open two AI Coding Assistants and give both the following Prompt")
para("Prompt:", after=2)
prompt_box(PROMPTS["subtask2"])
figure(img("claude_subtask2_chat.png"), "Claude Code finds and explains the bug")
figure(img("chatgpt_subtask2_chat.png"), "ChatGPT finds and explains the same bug")
label("Step 3:", "Run the corrected code")
para("Corrected code (Claude Code):", bold=True, after=2)
code_block(code_of("subtask2_claude"))
figure(img("subtask2_claude_output.png"), "Claude's corrected code runs", max_w=4.2)
para("Corrected code (ChatGPT):", bold=True, after=2)
code_block(code_of("subtask2_chatgpt"))
figure(img("subtask2_chatgpt_output.png"), "ChatGPT's corrected code runs", max_w=4.2)
para("OBSERVATION TABLE:", bold=True, after=2)
table(["Criteria", "Claude Code", "ChatGPT"], [
    ["Did it find the bug?", "Yes", "Yes"],
    ["Did it explain clearly?", "Yes. Shows the exact TypeError message", "Yes. Also notes that len() counts keys"],
    ["Was the corrected code working?", "Yes (Average marks: 65.0)", "Yes (Average marks: 65.0)"],
    ["Where the fix was made", "Inside the function: `marks.values()`", "At the call: `average_marks(students.values())`"],
    ["Extra improvements", "One-line `sum()` tip", "Guard against an empty collection, plus a one-line alternative"],
    ["Was the explanation beginner-friendly?", "Yes, short", "Yes, a little longer"],
], widths=[2.0, 2.2, 2.3], font_size=10.5)

# ---------------- Subtask 3 ----------------
heading("Subtask 3: Refactoring Code")
label("Objective:", "Use AI to improve code readability, modularity, and maintainability.")
para("STEPS:", bold=True, after=2)
label("Step 1:", "Run the original code to record its behaviour")
figure(img("subtask3_original_output.png"), "Output of the original (un-refactored) code", max_w=4.2)
label("Step 2:", "Give the following Prompt to the AI Coding Assistant")
para("Prompt:", after=2)
prompt_box(PROMPTS["subtask3"])
figure(img("claude_subtask3_chat.png"), "Claude Code's refactored version")
label("Step 3:", "Run the Refactored Code")
code_block(code_of("subtask3_claude"))
figure(img("subtask3_claude_output.png"), "The refactored code gives the same results", max_w=4.2)
para("The same prompt was given to ChatGPT for comparison:", after=4)
figure(img("chatgpt_subtask3_chat.png"), "ChatGPT's refactored version")
figure(img("subtask3_chatgpt_output.png"), "Output of ChatGPT's refactored code", max_w=4.2)
para("OBSERVATION TABLE:", bold=True, after=2)
table(["Aspect", "Claude Code", "ChatGPT"], [
    ["Functions used", "Yes: calculate_average, get_topper, get_failed_students, main", "Yes: calculate_average, find_topper, failing_students"],
    ["Meaningful variable names", "Yes (student_marks, topper, topper_marks)", "Yes (scores, topper, fails)"],
    ["Repeated logic", "Reduced (3 loops replaced by sum/max/list comprehension)", "Reduced (same approach)"],
    ["Pass mark", "Named constant PASS_MARK", "Function parameter threshold=40"],
    ["Readability", "Improved", "Improved"],
    ["Maintainability", "Improved; printing only in main()", "Improved"],
    ["Same behaviour as original", "Yes; also prints the topper's marks", "Yes; average shown as 71.50"],
    ["Accuracy of explanation", "Accurate", "Its 'What changed' table mentions 'implicit string concatenation', "
                                                "which the original code does not use"],
    ["Code execution", "Successful", "Successful"],
], widths=[1.7, 2.4, 2.4], font_size=10.5)

# ---------------- Subtask 4 ----------------
heading("Subtask 4: Code Documentation")
label("Objective:", "Use AI to generate comments, docstrings, and README-style documentation.")
para("STEPS:", bold=True, after=2)
label("Step 1:", "Open an AI Coding Assistant (Claude Code)")
label("Step 2:", "Give the following Prompt")
para("Prompt:", after=2)
prompt_box(PROMPTS["subtask4"])
figure(img("claude_subtask4_chat.png"), "Claude Code adds docstrings, comments and a README")
label("Step 3:", "Documented Code")
code_block(code_of("subtask4_claude").split("\nmarks = {")[0].rstrip())
label("Step 4:", "README-Style Output")
md_section(response("claude", "subtask4").split("## README", 1)[1])
label("Step 5:", "Check that the documented code still works and that help() shows the new docstring")
figure(img("subtask4_claude_output.png"), "Running the documented functions and printing help(calculate_average)",
       max_w=4.6)
para("The same prompt was given to ChatGPT. Its README example was checked by running it:", after=4)
figure(img("chatgpt_subtask4_chat.png"), "ChatGPT's documented code and README")
table(["Line in ChatGPT's README", "Comment in README", "Actual result when run"], [
    ["print(calculate_average(marks)) with Alice 78, Bob 35, Charlie 92, Diana 41",
     "# -> 64.5", "61.5  ((78+35+92+41)/4 = 246/4)"],
], widths=[3.0, 1.3, 2.2], font_size=10.5)
para("OBSERVATION TABLE:", bold=True, after=2)
table(["Aspect", "Claude Code", "ChatGPT"], [
    ["Function-level docstrings", "Added (Google style: Args / Returns)", "Added (NumPy style: Parameters / Returns)"],
    ["Inline comments", "Added (one per function)", "Added (one per function)"],
    ["Parameters explained", "Yes", "Yes"],
    ["Return values explained", "Yes", "Yes"],
    ["README documentation", "Added, with a function table and usage example", "Added, with usage example"],
    ["Example values correct?", "Yes (71.5, ('Vikram', 91), ['Meena'])", "No: README says 64.5, the real value is 61.5"],
    ["Edge cases mentioned", "Yes: empty dictionary causes an error", "No"],
    ["Code readability", "Improved", "Improved"],
], widths=[1.8, 2.35, 2.35], font_size=10.5)

# ---------------- Subtask 5 ----------------
heading("Subtask 5: Compare Different AI Tools")
label("Objective:", "Compare how different AI coding assistants respond to the same task.")
para("STEPS:", bold=True, after=2)
label("Step 1:", "Open two Coding Agents (Claude Code and ChatGPT)")
label("Step 2:", "Give the following Prompt to both AI tools")
para("Prompt:", after=2)
prompt_box(PROMPTS["subtask5"])
para("Claude Code:", bold=True, after=2)
figure(img("claude_subtask5_chat.png"), "Claude Code's response to the common prompt")
para("ChatGPT:", bold=True, after=2)
figure(img("chatgpt_subtask5_chat.png"), "ChatGPT's response to the common prompt")
para("Generated Codes:", bold=True, after=2)
para("Claude Code:", bold=True, after=2)
code_block(code_of("subtask5_claude"))
para("Output:", bold=True, after=2)
figure(img("subtask5_claude_output.png"), "Output of Claude Code's program", max_w=4.2)
para("ChatGPT:", bold=True, after=2)
code_block(code_of("subtask5_chatgpt"))
para("Output (menu inputs: add Asha 85, Rahul 38, Meena 92, Kiran 25, then options 2, 3, 4, 5):",
     bold=True, after=2)
figure(img("subtask5_chatgpt_output.png"), "Output of ChatGPT's menu-driven program", max_w=4.0)

para("COMPARISON TABLE:", bold=True, after=2)
table(["Evaluation Criteria", "ChatGPT", "Claude Code"], [
    ["Code correctness", "Good (average 60.00, topper and list correct)", "Good (average 62.20, topper and list correct)"],
    ["Readability", "Good, but long (155 lines) with section banners", "Great (80 lines)"],
    ["Use of functions", "Yes (6 functions)", "Yes (6 functions)"],
    ["Data handling", "Global list shared by all functions", "Dictionary passed to each function"],
    ["Documentation quality", "Good: detailed NumPy-style docstrings", "Good: short Google-style docstrings"],
    ["Error handling", "Better: menu, range check, non-numeric input", "Basic: range check, empty class"],
    ["Interactivity", "Menu-driven (user types marks)", "Sample data (edit to change)"],
    ["Simplicity for UG students", "Good (type hints like `tuple | None` are advanced)", "Great"],
    ["Output clarity", "Good", "Great (aligned report)"],
    ["Overall rating /10", "8.5/10", "9/10"],
], widths=[1.8, 2.35, 2.35], font_size=10.5)

para("Overall comparison across all five subtasks:", bold=True, after=2)
table(["Subtask", "ChatGPT", "Claude Code"], [
    ["1. Code generation", "Correct; adds input validation", "Correct; shorter and simpler"],
    ["2. Debugging", "Found the bug; fixed at the call site; added empty guard", "Found the bug; fixed inside the function; showed the exact error"],
    ["3. Refactoring", "Correct; one inaccurate claim in its explanation", "Correct; kept the topper's marks in the output"],
    ["4. Documentation", "Thorough docstrings; README example has a wrong value (64.5 vs 61.5)", "Accurate docstrings and README; mentions the empty-input edge case"],
    ["5. Full program", "More features (menu, input checks)", "Easier to read and explain"],
], widths=[1.5, 2.5, 2.5], font_size=10.5)

para("RESULT:", bold=True, after=2)
para("Part A was completed using two AI coding assistants, Claude Code and ChatGPT, for code "
     "generation, debugging, refactoring, documentation and comparison. Every program the tools "
     "produced was run with the same input: all generated and refactored programs gave the correct "
     "average, topper and list of students below 40, and both tools found and fixed the TypeError "
     "in the faulty code. Running the code also caught one mistake that reading alone would miss: "
     "ChatGPT's README example states an average of 64.5 where the real value is 61.5.")

# =========================================================================== #
# PART B
# =========================================================================== #
doc.add_page_break()
part_banner("PART B: MCP Servers and Clients (Lab_06 Experiments)")

p = doc.add_paragraph()
run(p, "GitHub Repository: ", bold=True)
if GITHUB_URL:
    run(p, GITHUB_URL, color="1F4E79")
else:
    r = run(p, "<add GitHub URL here after pushing>")
    r.font.highlight_color = WD_COLOR_INDEX.YELLOW

para("Both experiments follow the same pattern: a host application (the MCP client) starts its "
     "MCP server as a subprocess and talks to it over stdio using JSON-RPC. It gives the server's "
     "tool list to the LLM and runs a tool-calling loop: the LLM asks for a tool, the host runs it on "
     "the MCP server, the result goes back to the LLM, and this repeats until the LLM gives a final "
     "answer. No API key is needed: with no key set, the LLM is OpenAI gpt-oss-20b on a free keyless "
     "endpoint. OpenAI, Groq and Gemini keys are also supported.")
figure(os.path.join(HERE, "docs", "architecture.png"), "Architecture of both experiments")

table(["Folder / file", "Role"], [
    ["`common/llm.py`", "LLM client (OpenAI-style chat + function calling; OpenAI / Groq / Gemini / keyless)"],
    ["`common/mcp_tools.py`", "Converts MCP tool schemas into OpenAI function-calling schemas"],
    ["`common/agent_loop.py`", "The tool-calling loop shared by both clients"],
    ["`expt1_memory_server/notes_server.py`", "Expt 1 MCP server (FastMCP): notes CRUD on notes.json"],
    ["`expt1_memory_server/notes_client.py`", "Expt 1 MCP client: command-line chat (Rich)"],
    ["`expt2_weather_dashboard/weather_server.py`", "Expt 2 MCP server: live weather from wttr.in"],
    ["`expt2_weather_dashboard/app.py`", "Expt 2 MCP client: Streamlit web dashboard"],
    ["`tests/`", "51 pytest tests for both servers and the shared code"],
], widths=[2.9, 3.6], font_size=10.5)

# ---------------- Expt 1 ----------------
heading('Experiment 1: The "Personal Assistant" Memory Server')
label("Objective:", "Implement a basic MCP Server with tools that perform CRUD operations.")
para("Project Components:", bold=True, after=2)
rich("**MCP Server** (`notes_server.py`): exposes `save_note` (takes content and tags) and "
     "`search_notes` (takes a query) as asked, plus `list_notes`, `update_note` and `delete_note` "
     "so that all four CRUD operations are covered. It reads from and writes to a local "
     "`notes.json` file (written atomically through a temp file, so a crash cannot corrupt it).")
rich("**MCP Client** (`notes_client.py`): a Python script that connects to the server, lets the "
     "user type a query (e.g. \"What did I say about the project deadline?\") and uses an LLM to "
     "decide whether to call `save_note` or `search_notes`. It prints the LLM's thought, the tool "
     "call, the tool result and the final answer.")
table(["Tool", "Inputs", "CRUD", "What it does"], [
    ["`save_note`", "content, tags", "Create", "Adds a note with an id, lower-cased tags and timestamps"],
    ["`search_notes`", "query", "Read", "Keyword search; ignores filler words, ranks tag matches higher"],
    ["`list_notes`", "tag (optional)", "Read", "All notes newest first, optionally filtered by tag"],
    ["`update_note`", "note_id, content, tags", "Update", "Changes a note's text and/or tags"],
    ["`delete_note`", "note_id", "Delete", "Removes a note by id"],
], widths=[1.3, 1.5, 0.8, 2.9], font_size=10.5)
para("STEPS:", bold=True, after=2)
label("Step 1:", "Install the requirements: `pip install -r requirements.txt`")
label("Step 2:", "Write the MCP server. FastMCP turns each decorated function into an MCP tool; the "
                 "docstring becomes the description that the LLM reads.")
code_block(source_of(os.path.join(HERE, "expt1_memory_server", "notes_server.py"), "save_note"))
code_block(source_of(os.path.join(HERE, "expt1_memory_server", "notes_server.py"), "search_notes"))
label("Step 3:", "Write the tool-calling loop used by the client. The LLM only requests a tool; the "
                 "client runs it on the MCP server and sends the result back.")
code_block(source_of(os.path.join(HERE, "common", "agent_loop.py"), "run_agent_turn"))
label("Step 4:", "Run the client: `python expt1_memory_server/notes_client.py` "
                 "(or add `--demo` to run four sample queries)")
figure(os.path.join(HERE, "screenshots", "expt1_tools_list.png"),
       "The client connects to the MCP server and discovers its 5 tools")
figure(os.path.join(HERE, "screenshots", "expt1_cli_demo.png"),
       "Queries 1-2: the LLM chooses save_note, then search_notes for the deadline question")
figure(os.path.join(HERE, "screenshots", "expt1_cli_demo_2.png"),
       "Queries 3-4: save_note with a resolved date, then list_notes filtered by tag")
para("OBSERVATION TABLE:", bold=True, after=2)
table(["User query", "Tool chosen by LLM", "Arguments", "Result"], [
    ["Remember that the project deadline for Lab 6 is Friday 25 September and I must upload the GitHub URL and screenshots",
     "`save_note`", "content + tags deadline, lab6, github", "Saved as note id 5"],
    ["What did I say about the project deadline?", "`search_notes`", "query: \"project deadline\"",
     "3 matches; top 2 are the deadline notes"],
    ["Note that I need to buy milk and eggs tomorrow", "`save_note`", "\"tomorrow\" resolved to 2026-09-26; tags shopping, groceries",
     "Saved as note id 6"],
    ["Show me all my notes tagged shopping", "`list_notes`", "tag: \"shopping\"", "2 notes, newest first"],
], widths=[2.4, 1.2, 1.7, 1.2], font_size=10)

# ---------------- Expt 2 ----------------
heading('Experiment 2: The "Data Dashboard" Connector')
label("Objective:", "Connect an AI to a public data service (a weather API) to fetch real-time "
                    "data and summarize it: a context enhancement use case.")
para("Project Components:", bold=True, after=2)
rich("**MCP Server** (`weather_server.py`): exposes `get_current_weather(location)`, which fetches "
     "live data from the free wttr.in API (`?format=j1`) and returns it as structured text. It also "
     "has `get_forecast` and `compare_weather`. Place names are first geocoded with Open-Meteo so "
     "that cities like Tokyo resolve to the right place.")
rich("**MCP Client** (`app.py`): a Streamlit web app. The user types \"What's the weather in "
     "Tokyo?\" and the app shows each step of the LLM's thought process: its thought, the tool call "
     "with arguments, the raw MCP server response, and the final answer. A raw JSON message trace "
     "can also be opened. This makes the client-server interaction visible.")
para("STEPS:", bold=True, after=2)
label("Step 1:", "Write the weather MCP tool")
code_block(source_of(os.path.join(HERE, "expt2_weather_dashboard", "weather_server.py"), "get_current_weather"))
label("Step 2:", "Start the dashboard: `streamlit run expt2_weather_dashboard/app.py`")
label("Step 3:", "Ask \"What's the weather in Tokyo?\" and open the agent steps")
figure(os.path.join(HERE, "screenshots", "expt2_dashboard_tokyo.png"),
       "The dashboard answering \"What's the weather in Tokyo?\" with live data")
figure(os.path.join(HERE, "screenshots", "expt2_dashboard_steps.png"),
       "The LLM's thought process: thought, tool call, MCP server response, final answer")
para("OBSERVATION TABLE:", bold=True, after=2)
table(["Step", "What the app showed"], [
    ["1. Thought", "\"We need to call get_current_weather for Tokyo.\""],
    ["2. Tool call", "`get_current_weather` with {\"location\": \"Tokyo\"}"],
    ["3. MCP server response", "Tokyo, Japan: patchy rain nearby, 23 °C (feels like 23 °C), humidity 69%, "
                               "wind 12 km/h E, precipitation 0.1 mm, UV index 0 (source: wttr.in, live)"],
    ["4. Final answer", "A formatted summary of the conditions plus practical advice "
                        "(carry an umbrella, a light sweater is enough, no sunscreen needed)"],
], widths=[1.8, 4.7], font_size=10.5)

heading("Testing", size=12)
para("A pytest suite of 51 tests checks both servers (saving, searching, tag handling, updates, "
     "deletes, persistence, weather formatting, geocoding, error handling), the shared tool-calling "
     "loop, and a full client-server session over stdio. All 51 tests pass.")
figure(os.path.join(HERE, "screenshots", "tests_passing.png"), "All 51 tests pass")

para("RESULT:", bold=True, after=2)
para("Two MCP servers and their clients were implemented with the MCP Python SDK. In Experiment 1 "
     "the LLM correctly chose save_note to store facts and search_notes or list_notes to recall "
     "them, and every change was saved in notes.json. In Experiment 2 the LLM called "
     "get_current_weather for Tokyo, received live data from wttr.in through the MCP server, and "
     "summarized it, with every step shown in the Streamlit dashboard.")

para("SUMMARY:", bold=True, after=2)
para("I compared Claude Code and ChatGPT on the same five tasks and ran every piece of code they "
     "produced. Both tools generated correct programs, found the dictionary bug, and refactored and "
     "documented the code well. ChatGPT tended to add more features, such as input validation and a "
     "menu, while Claude Code gave shorter code that is easier for a beginner to follow. ChatGPT made "
     "one factual mistake in its README example (64.5 instead of 61.5), which I only noticed because "
     "I ran the example. So AI-generated code and documentation must always be tested. In the MCP "
     "experiments I learned how an LLM can use real tools safely: the model only chooses a tool and "
     "its arguments, and the MCP server does the actual work of reading notes or calling the "
     "weather API.")

doc.save(OUT_FILE)
print("saved", OUT_FILE, "with", FIG, "figures")
