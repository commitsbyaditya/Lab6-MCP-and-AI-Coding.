"""Render the saved prompts, AI responses and run outputs as PNG screenshots.

    python partA_ai_coding/render.py      (run after ask_chatgpt.py and run_all.py)

images/<tool>_<subtask>_chat.png  prompt bubble + the tool's reply
images/<name>_output.png          console output of the program
"""

import os
import re
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from prompts import PROMPTS  # noqa: E402

RESP = os.path.join(HERE, "responses")
OUT = os.path.join(HERE, "outputs")
IMG = os.path.join(HERE, "images")

FONTS = "C:/Windows/Fonts/"
SANS = ImageFont.truetype(FONTS + "segoeui.ttf", 17)
SANS_B = ImageFont.truetype(FONTS + "segoeuib.ttf", 17)
SANS_H = ImageFont.truetype(FONTS + "segoeuib.ttf", 19)
MONO = ImageFont.truetype(FONTS + "consola.ttf", 15)
MONO_B = ImageFont.truetype(FONTS + "consolab.ttf", 15)

TOOLS = {
    "claude": {"label": "Claude Code  ·  Claude Opus 5.5", "accent": (217, 119, 87),
               "bg": (38, 38, 36), "bubble": (60, 59, 55), "code": (26, 26, 25)},
    "chatgpt": {"label": "ChatGPT  ·  OpenAI gpt-oss-20b", "accent": (16, 163, 127),
                "bg": (33, 33, 33), "bubble": (48, 48, 48), "code": (15, 15, 15)},
}
TEXT = (236, 236, 236)
MUTED = (160, 160, 160)
WIDTH = 900
MAX_CODE_LINES = 24


def clean(s):
    # Consolas has no glyph for the non-breaking hyphen some models emit.
    return s.replace("\u2011", "-").replace("\u202f", " ")


def wrap(text, font, width):
    """Greedy word-wrap for a proportional font."""
    words, lines, line = text.split(" "), [], ""
    for w in words:
        trial = (line + " " + w).strip()
        if font.getlength(trial) <= width:
            line = trial
        else:
            if line:
                lines.append(line)
            line = w
    lines.append(line)
    return lines


def md_blocks(md):
    """Split markdown into ('code', lines) and ('text', line) blocks."""
    blocks, in_code, code, lang = [], False, [], ""
    for raw in clean(md).splitlines():
        if raw.startswith("```"):
            if in_code:
                blocks.append(("code", (lang or "output", code)))
                code = []
            else:
                lang = raw[3:].strip()
            in_code = not in_code
            continue
        if in_code:
            code.append(raw)
        else:
            blocks.append(("text", raw))
    return blocks


def plain(s):
    return re.sub(r"\*\*|`", "", s)


def render_chat(tool, subtask):
    t = TOOLS[tool]
    with open(os.path.join(RESP, f"{tool}_{subtask}.md"), encoding="utf-8") as fh:
        reply = fh.read()
    prompt = clean(PROMPTS[subtask])

    # Lay everything out as draw ops first, then size the canvas to fit.
    ops, y, pad = [], 70, 34
    # user bubble (right-aligned)
    bubble_w = 600
    b_lines = []
    for para in prompt.splitlines():
        if para.startswith("    ") or para.startswith("def ") or re.match(r"^\S+ = |^\s|^print|^avg|^for |^top|^total", para):
            b_lines.append(("mono", para))
        else:
            b_lines += [("sans", ln) for ln in wrap(para, SANS, bubble_w - 36)] if para else [("sans", "")]
    bh = sum(20 if k == "mono" else 25 for k, _ in b_lines) + 28
    ops.append(("rect", (WIDTH - pad - bubble_w, y, WIDTH - pad, y + bh), t["bubble"]))
    yy = y + 14
    for kind, ln in b_lines:
        ops.append(("text", (WIDTH - pad - bubble_w + 18, yy), ln, MONO if kind == "mono" else SANS, TEXT))
        yy += 20 if kind == "mono" else 25
    y += bh + 26

    for kind, content in md_blocks(reply):
        if kind == "code":
            lang, content = content
            lines = content
            cut = len(lines) - MAX_CODE_LINES
            if cut > 0:
                lines = lines[:MAX_CODE_LINES] + [f"# ... {cut} more lines (full code in the report)"]
            h = 20 * len(lines) + 46
            ops.append(("rect", (pad, y, WIDTH - pad, y + h), t["code"]))
            ops.append(("text", (pad + 14, y + 8), lang, MONO, MUTED))
            yy = y + 34
            for ln in lines:
                ops.append(("text", (pad + 14, yy), ln[:100], MONO, TEXT))
                yy += 20
            y += h + 12
            continue
        line = content
        if not line.strip() or line.strip() == "---":
            y += 8
            continue
        font, x, bullet = SANS, pad, None
        if line.startswith("#"):
            font, line = SANS_H, line.lstrip("#").strip()
        elif re.match(r"^\s*([-*]|\d+\.)\s", line):
            m = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)", line)
            x = pad + 18 + 18 * (len(m.group(1)) // 2)
            bullet = "•" if m.group(2) in "-*" else m.group(2)
            line = m.group(3)
        elif line.startswith("|"):
            if set(line) <= set("|-: "):
                continue
            ops.append(("text", (pad, y), plain(line)[:108], MONO, TEXT))
            y += 21
            continue
        bold_line = line.startswith("**") and line.rstrip().endswith("**")
        for i, ln in enumerate(wrap(plain(line), SANS_B if bold_line else font, WIDTH - x - pad - 20)):
            if bullet and i == 0:
                ops.append(("text", (x - 20, y), bullet, SANS, TEXT))
            ops.append(("text", (x, y), ln, SANS_B if bold_line else font, TEXT))
            y += 26 if font is SANS_H else 25
        y += 4

    img = Image.new("RGB", (WIDTH, y + 30), t["bg"])
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, WIDTH, 46), fill=tuple(max(c - 12, 0) for c in t["bg"]))
    d.ellipse((pad, 15, pad + 16, 31), fill=t["accent"])
    d.text((pad + 26, 11), t["label"], font=SANS_B, fill=TEXT)
    for op in ops:
        if op[0] == "rect":
            d.rounded_rectangle(op[1], radius=12, fill=op[2])
        else:
            d.text(op[1], op[2], font=op[3], fill=op[4])
    img.save(os.path.join(IMG, f"{tool}_{subtask}_chat.png"))


def render_output(name, title):
    with open(os.path.join(OUT, name + ".txt"), encoding="utf-8") as fh:
        lines = clean(fh.read()).rstrip("\n").splitlines()
    width = max(560, min(900, 40 + int(max(MONO.getlength(ln) for ln in lines + [title])) + 40))
    h = 58 + 20 * len(lines) + 24
    img = Image.new("RGB", (width, h), (30, 30, 30))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, width, 38), fill=(20, 20, 20))
    d.text((18, 10), "$ " + title, font=MONO_B, fill=(129, 199, 132))
    y = 52
    for ln in lines:
        colour = (255, 138, 128) if ("Error" in ln or ln.startswith("Traceback")) else (224, 224, 224)
        d.text((20, y), ln, font=MONO, fill=colour)
        y += 20
    img.save(os.path.join(IMG, name + "_output.png"))


def main():
    os.makedirs(IMG, exist_ok=True)
    for tool in TOOLS:
        for subtask in PROMPTS:
            render_chat(tool, subtask)
    for f in sorted(os.listdir(OUT)):
        name = f[:-4]
        render_output(name, f"python {name}.py")
    print("rendered", len(os.listdir(IMG)), "images into", IMG)


if __name__ == "__main__":
    main()
