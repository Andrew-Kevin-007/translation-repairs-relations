"""Deterministic main.tex -> main_review_copy.docx converter.

Produces a Word REVIEW COPY of the manuscript for human readers (author, HOD).
The LaTeX file remains the manuscript master; rerun this script after any tex
change. No LLM involved — pure parsing, so the copy is always faithful.

Usage:  python make_review_docx.py          (from the paper/ directory)
"""

from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

HERE = Path(__file__).resolve().parent
TEX = HERE / "main.tex"
BIB = HERE / "references.bib"
OUT = HERE / "main_review_copy.docx"

BLUE = RGBColor(0x1F, 0x4E, 0xD8)
RED = RGBColor(0xC0, 0x1D, 0x1D)
GRAY = RGBColor(0x66, 0x66, 0x66)

MATH_MAP = {
    r"\geq": "≥", r"\leq": "≤", r"\times": "×",
    r"\in": "∈", r"\rho": "ρ", r"\tau": "τ",
    r"\mathrm{GRR}": "GRR", r"\mathrm": "", r"\text": "", r"\textsc": "",
    r"\emph": "", r"\frac": "", r"\;": " ", r"\,": " ", r"---": "—",
    r"\{": "{", r"\}": "}", r"~": " ", r"$": "",
}


def clean_math(s: str) -> str:
    for k, v in MATH_MAP.items():
        s = s.replace(k, v)
    s = re.sub(r"_\{([^{}]*)\}", r"_\1", s)
    s = re.sub(r"\^\{([^{}]*)\}", r"^\1", s)
    return re.sub(r"\s+", " ", s.replace("{", "").replace("}", "")).strip()


def strip_comments(tex: str) -> str:
    out = []
    for line in tex.splitlines():
        if line.lstrip().startswith("%"):
            continue
        # remove trailing unescaped comment
        line = re.sub(r"(?<!\\)%.*$", "", line)
        out.append(line)
    return "\n".join(out)


def parse_bib_order(tex: str, bib: str) -> list[tuple[str, str]]:
    """Bib entries formatted, ordered by first citation appearance."""
    order = []
    for m in re.finditer(r"\\cite\{([^}]+)\}", tex):
        for key in m.group(1).split(","):
            key = key.strip()
            if key and key not in order:
                order.append(key)
    entries = {}
    for m in re.finditer(r"@\w+\{([^,]+),(.*?)\n\}", bib, re.S):
        key, body = m.group(1).strip(), m.group(2)
        fields = {}
        for fm in re.finditer(r"(\w+)\s*=\s*\{(.*?)\}\s*,?\s*\n", body, re.S):
            fields[fm.group(1).lower()] = re.sub(r"\s+", " ", fm.group(2)) \
                .replace("{", "").replace("}", "").replace("\\'i", "í") \
                .replace("\\'e", "é").replace("\\textsuperscript", "^")
        authors = fields.get("author", "?").replace(" and ", "; ")
        venue = fields.get("booktitle") or fields.get("journal") or ""
        entries[key] = "%s: %s. %s (%s)" % (
            authors, fields.get("title", "?"), venue, fields.get("year", "?"))
    return [(k, entries.get(k, "[missing bib entry: %s]" % k)) for k in order]


def add_runs(par, text: str, cite_index: dict[str, int]) -> None:
    """Render inline LaTeX into styled docx runs."""
    token = re.compile(
        r"(\\afterruns\{[^}]*\}|\\citeneed\{[^}]*\}|\\cite\{[^}]+\}"
        r"|\\emph\{[^}]*\}|\\textbf\{[^}]*\}|\\textsc\{[^}]*\}"
        r"|\$[^$]+\$|\\ref\{[^}]*\}|\\footnote\{[^{}]*\})")
    pos = 0
    for m in token.finditer(text):
        if m.start() > pos:
            par.add_run(plain(text[pos:m.start()]))
        tok = m.group(0)
        if tok.startswith("\\afterruns"):
            r = par.add_run("[AFTER RUNS: %s]" % inner(tok))
            r.font.color.rgb = BLUE
        elif tok.startswith("\\citeneed"):
            r = par.add_run("[citation needed: %s]" % inner(tok))
            r.font.color.rgb = RED
        elif tok.startswith("\\cite"):
            nums = ",".join(str(cite_index.get(k.strip(), "?"))
                            for k in inner(tok).split(","))
            par.add_run("[%s]" % nums)
        elif tok.startswith("\\emph"):
            par.add_run(plain(inner(tok))).italic = True
        elif tok.startswith("\\textbf"):
            par.add_run(plain(inner(tok))).bold = True
        elif tok.startswith("\\textsc"):
            r = par.add_run(plain(inner(tok)))
            r.font.small_caps = True
        elif tok.startswith("\\ref"):
            par.add_run("§")   # section symbol; numbering approximated
        elif tok.startswith("\\footnote"):
            r = par.add_run(" (footnote: %s)" % plain(inner(tok)))
            r.font.color.rgb = GRAY
        elif tok.startswith("$"):
            par.add_run(clean_math(tok))
        pos = m.end()
    if pos < len(text):
        par.add_run(plain(text[pos:]))


def inner(tok: str) -> str:
    return tok[tok.index("{") + 1:tok.rindex("}")]


def plain(s: str) -> str:
    s = s.replace("---", "—").replace("--", "–")
    s = s.replace("``", "“").replace("''", "”")
    s = s.replace(r"\%", "%").replace(r"\&", "&").replace("~", " ")
    s = re.sub(r"\\(smallskip|noindent|centering|midrule|toprule|bottomrule)", "", s)
    s = re.sub(r"\\label\{[^}]*\}", "", s)
    return re.sub(r"[ \t]+", " ", s)


def main() -> None:
    tex = strip_comments(TEX.read_text(encoding="utf-8"))
    bib = BIB.read_text(encoding="utf-8")
    refs = parse_bib_order(tex, bib)
    cite_index = {k: i + 1 for i, (k, _) in enumerate(refs)}

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(10)

    notice = doc.add_paragraph()
    r = notice.add_run(
        "REVIEW COPY generated from main.tex (the manuscript master). "
        "Formatting approximates Springer CCIS; the submission PDF is produced "
        "from LaTeX. Comment freely — edits here do not flow back "
        "automatically.")
    r.italic = True
    r.font.color.rgb = GRAY

    title_m = re.search(r"\\title\{(.*?)\}\s*\n", tex, re.S)
    tpar = doc.add_paragraph()
    tpar.alignment = WD_ALIGN_PARAGRAPH.CENTER
    tr = tpar.add_run(plain(title_m.group(1)) if title_m else "[no title]")
    tr.bold = True
    tr.font.size = Pt(14)
    for line in ("Anonymous Author(s)", "Anonymous Institution"):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.add_run(line)

    abs_m = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", tex, re.S)
    if abs_m:
        p = doc.add_paragraph()
        p.add_run("Abstract. ").bold = True
        add_runs(p, re.sub(r"\s+", " ", abs_m.group(1)).strip(), cite_index)
        for run in p.runs:
            run.font.size = Pt(9)

    body_start = tex.index("\\section")
    body = tex[body_start:tex.index("\\bibliographystyle")]
    sec_n, sub_n = 0, 0
    for block in re.split(r"\n\s*\n", body):
        block = block.strip()
        if not block:
            continue
        sm = re.match(r"\\section\{(.*?)\}", block, re.S)
        um = re.match(r"\\subsection\{(.*?)\}", block, re.S)
        if sm:
            sec_n += 1
            sub_n = 0
            h = doc.add_paragraph()
            hr = h.add_run("%d  %s" % (sec_n, plain(re.sub(r"\\label\{[^}]*\}", "", sm.group(1)))))
            hr.bold = True
            hr.font.size = Pt(12)
            block = block[sm.end():].strip()
        elif um:
            sub_n += 1
            h = doc.add_paragraph()
            hr = h.add_run("%d.%d  %s" % (sec_n, sub_n, plain(re.sub(r"\\label\{[^}]*\}", "", um.group(1)))))
            hr.bold = True
            hr.font.size = Pt(11)
            block = block[um.end():].strip()
        if not block:
            continue
        if block.startswith("\\begin{table}"):
            cap = re.search(r"\\caption\{(.*?)\}\s*\n", block, re.S)
            p = doc.add_paragraph()
            cr = p.add_run("Table: " + plain(cap.group(1)) if cap else "Table")
            cr.italic = True
            rows = [r for r in re.findall(r"^(.*?)\\\\", block, re.M)
                    if "&" in r]
            if rows:
                t = doc.add_table(rows=0, cols=rows[0].count("&") + 1)
                t.style = "Light Grid Accent 1"
                for row in rows:
                    cells = t.add_row().cells
                    for i, cell in enumerate(row.split("&")):
                        cell = cell.strip()
                        cells[i].text = ("[AFTER RUNS]" if "\\afterruns" in cell
                                         else plain(re.sub(r"\\afterruns\{[^}]*\}", "", cell)))
            continue
        if block.startswith("\\["):
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.add_run(clean_math(block.replace("\\[", "").replace("\\]", "")))
            continue
        p = doc.add_paragraph()
        add_runs(p, re.sub(r"\s+", " ", block), cite_index)

    h = doc.add_paragraph()
    hr = h.add_run("References")
    hr.bold = True
    hr.font.size = Pt(12)
    for i, (key, entry) in enumerate(refs, 1):
        p = doc.add_paragraph()
        p.add_run("%d. %s" % (i, entry)).font.size = Pt(9)

    doc.save(OUT)
    print("wrote %s (%d references, %d sections)" % (OUT, len(refs), sec_n))


if __name__ == "__main__":
    main()
