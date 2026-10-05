#!/usr/bin/env python3
"""Build the bilingual study site (index.html) from the kit's own sources.

English questions and glossary come from ../07_agent_interview_prep_guide.md,
so the guide stays the single source of truth. Chinese text comes from
zh_*.json (keyed by question id / glossary term). Plan and project pages come
from site_data.json. Missing translations fall back to English and are listed.

    python study_site/build.py        # writes study_site/index.html
"""
import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GUIDE = HERE.parent / "07_agent_interview_prep_guide.md"
QUESTION = re.compile(r"^\*\*([A-L])(\d+)\.\s*(★\s*)?(.+?)\*\*\s*(.*)$")
BEHAVIORAL = re.compile(r'^- \*\*"(.+?)"\*\*\s*(.*)$')
SECTION = re.compile(r"^### ([A-L])\. (.+)$")


def inline(text):
    """Escape, then apply `code`, **bold**, *italic* and [links](url)."""
    parts = re.split(r"(`[^`]+`)", text)
    out = []
    for part in parts:
        if part.startswith("`") and part.endswith("`") and len(part) > 1:
            out.append("<code>" + html.escape(part[1:-1]) + "</code>")
            continue
        part = html.escape(part, quote=False)
        part = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", part)
        part = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", part)
        part = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", lambda m: link(m.group(1), m.group(2)), part)
        out.append(part)
    return "".join(out)


def link(label, target):
    if target.startswith("http"):
        return f'<a href="{html.escape(target)}" target="_blank" rel="noopener">{label}</a>'
    return f"<span class=\"path\">{label}</span>"  # Repo paths are not reachable from the site.


def render(markdown):
    """Tiny Markdown subset: paragraphs, bullet/numbered lists, fenced code."""
    blocks, lines, i = [], markdown.strip("\n").split("\n"), 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            code = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code.append(lines[i])
                i += 1
            blocks.append("<pre><code>" + html.escape("\n".join(code)) + "</code></pre>")
            i += 1
        elif re.match(r"^\s*(- |\d+\. )", line):
            ordered = bool(re.match(r"^\s*\d+\. ", line))
            items = []
            while i < len(lines) and re.match(r"^\s*(- |\d+\. )", lines[i]):
                items.append("<li>" + inline(re.sub(r"^\s*(- |\d+\. )", "", lines[i])) + "</li>")
                i += 1
            tag = "ol" if ordered else "ul"
            blocks.append(f"<{tag}>" + "".join(items) + f"</{tag}>")
        elif line.strip():
            para = [line.strip()]
            i += 1
            while i < len(lines) and lines[i].strip() and not re.match(r"^(```|\s*- |\s*\d+\. )", lines[i]):
                para.append(lines[i].strip())
                i += 1
            blocks.append("<p>" + inline(" ".join(para)) + "</p>")
        else:
            i += 1
    return "".join(blocks)


def parse_guide(text):
    body = text[text.index("## 5. Interview questions & answers"):text.index("## 6. Related AI knowledge")]
    sections, questions, current, section = [], [], None, None
    for line in body.split("\n"):
        heading = SECTION.match(line)
        if heading:
            section = heading.group(1)
            sections.append({"id": section, "en": heading.group(2).split(" (")[0]})
            current = None
            continue
        if line.startswith("#### "):
            current = None
            continue
        match = QUESTION.match(line)
        if match and section:
            letter, number, star, question, rest = match.groups()
            current = {"id": f"{letter}{number}", "section": letter, "star": bool(star),
                       "q_en": question.strip().rstrip("."), "a_en": [rest] if rest else []}
            questions.append(current)
            continue
        behavioral = BEHAVIORAL.match(line)
        if behavioral and section == "K":
            current = {"id": f"K{sum(q['section'] == 'K' for q in questions) + 1}", "section": "K",
                       "star": False, "q_en": behavioral.group(1), "a_en": [behavioral.group(2)]}
            questions.append(current)
            current = None
            continue
        if line.startswith("---") or line.startswith("**Template"):
            current = None
            continue
        if current is not None:
            current["a_en"].append(line)
    for question in questions:
        question["a_en"] = "\n".join(question["a_en"]).strip()
    return sections, questions


def parse_glossary(text):
    body = text[text.index("## 3. Glossary"):text.index("## 4. Your project story")]
    groups, rows, group = [], [], None
    for line in body.split("\n"):
        if line.startswith("### "):
            group = line[4:].strip()
            groups.append(group)
        elif line.startswith("| ") and not line.startswith("| Term") and not line.startswith("|---") and group:
            cells = [c.strip() for c in line.strip().strip("|").split(" | ")]
            if len(cells) >= 3:
                term = cells[0]
                zh_in_term = re.search(r"（(.+?)）", term)
                rows.append({"group": group, "term": re.sub(r"（.+?）", "", term).strip(),
                             "term_zh": zh_in_term.group(1) if zh_in_term else "",
                             "en": cells[1], "repo": cells[2]})
    return groups, rows


def load_zh():
    merged = {"questions": {}, "glossary": {}, "sections": {}, "groups": {}}
    for path in sorted(HERE.glob("zh_*.json")):
        data = json.loads(path.read_text())
        for key in merged:
            merged[key].update(data.get(key, {}))
    return merged


def main():
    text = GUIDE.read_text()
    sections, questions = parse_guide(text)
    groups, glossary = parse_glossary(text)
    zh = load_zh()
    missing = []
    for section in sections:
        section["zh"] = zh["sections"].get(section["id"], section["en"])
    for q in questions:
        tr = zh["questions"].get(q["id"])
        if not tr:
            missing.append(q["id"])
            tr = {"q": q["q_en"], "a": q["a_en"]}
        q["q_zh"], q["a_zh"] = tr["q"], render(tr["a"])
        q["a_en"] = render(q["a_en"])
    for row in glossary:
        tr = zh["glossary"].get(row["term"])
        if not tr:
            missing.append("glossary:" + row["term"])
        row["zh"] = inline(tr or row["en"])
        row["en"], row["repo"] = inline(row["en"]), inline(row["repo"])
    data = {"sections": sections, "questions": questions,
            "groups": [{"en": g, "zh": zh["groups"].get(g, g)} for g in groups],
            "glossary": glossary, **json.loads((HERE / "site_data.json").read_text())}
    template = (HERE / "template.html").read_text()
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    (HERE / "index.html").write_text(template.replace("/*__DATA__*/null", payload))
    print(f"{len(questions)} questions in {len(sections)} sections, {len(glossary)} glossary terms")
    if missing:
        print("missing Chinese:", ", ".join(missing), file=sys.stderr)


if __name__ == "__main__":
    main()
