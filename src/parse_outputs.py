"""Parsers for model outputs (stage-1 extraction, stage-2 canonicalization).

Rules here are part of the instrument and FREEZE on day 8 with the prompts.
Every leniency is deliberate and logged per item (unparsed lines are counted,
never silently dropped) so parse failures are analyzable — models are graded
on what the parser accepts, and the raw archives (llm_backend.RawArchive)
always allow re-parsing without re-running models.

Leniencies (fixed set):
  - <think>...</think> blocks stripped (Qwen3 leak-proofing), flagged.
  - leading list markers stripped per line: "-", "*", "1.", "1)", bullets.
  - surrounding whitespace and markdown bold (**...**) stripped per line.
  - format ECHOES ignored (not triples, not unparsed): a line that merely
    repeats the template header ("subject | relation | object") and pure
    separator lines (only -=_| characters). Found in the 2026-07-17 dry run:
    Llama-3.1 echoes the header before real triples.
NOT tolerated: wrong field count (!= 3 pipe-separated fields) -> unparsed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
_MARKER_RE = re.compile(r"^\s*(?:[-*•]|\d{1,3}[.)])\s+")
_BOLD_RE = re.compile(r"^\*\*(.*)\*\*$")
_SEPARATOR_RE = re.compile(r"^[\s\-=_|]+$")
_HEADER_ECHO = ("subject", "relation", "object")
# stage-2 template header (src/prompts/canonicalize.txt); Amendment 2 (A5):
# the same frozen format-echo leniency, completed for the canon stage
_CANON_HEADER_ECHO = ("subject_qid", "property_pid", "object_qid_or_literal")


def strip_think(text: str) -> tuple[str, bool]:
    """Remove <think> blocks (and an unclosed trailing <think> prefix)."""
    had = "<think>" in text
    text = _THINK_RE.sub("", text)
    if "<think>" in text:  # unclosed block: drop everything after it
        text = text.split("<think>")[0]
    return text.strip(), had


@dataclass
class ExtractionParse:
    triples: list[tuple[str, str, str]] = field(default_factory=list)
    is_none: bool = False
    unparsed_lines: list[str] = field(default_factory=list)
    had_think: bool = False


def _clean_line(line: str) -> str:
    line = _MARKER_RE.sub("", line.strip())
    m = _BOLD_RE.match(line)
    return m.group(1) if m else line


def parse_extraction(text: str) -> ExtractionParse:
    """Parse stage-1 output: 'subject | relation | object' lines or NONE."""
    out = ExtractionParse()
    text, out.had_think = strip_think(text)
    for raw_line in text.splitlines():
        line = _clean_line(raw_line)
        if not line or _SEPARATOR_RE.match(line):
            continue
        if line.upper() == "NONE":
            out.is_none = True
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) == 3 and all(parts):
            if tuple(p.casefold() for p in parts) == _HEADER_ECHO:
                continue  # template header echoed back, not a fact
            out.triples.append((parts[0], parts[1], parts[2]))
        else:
            out.unparsed_lines.append(raw_line)
    return out


@dataclass
class CanonParse:
    subject: str | None = None   # QID, or None if model answered NONE / unparsed
    property: str | None = None  # PID
    obj: str | None = None       # QID or literal
    parsed: bool = False
    had_think: bool = False
    raw_line: str = ""


_QID_RE = re.compile(r"^Q[1-9][0-9]*$")
_PID_RE = re.compile(r"^P[1-9][0-9]*$")


def parse_canonicalization(text: str) -> CanonParse:
    """Parse stage-2 output: one 'subject_qid | property_pid | object' line;
    NONE allowed per slot (prompts/canonicalize.txt). First parseable line wins;
    IDs are validated by shape (bad QIDs/PIDs -> slot None, still 'parsed')."""
    out = CanonParse()
    text, out.had_think = strip_think(text)
    for raw_line in text.splitlines():
        line = _clean_line(raw_line)
        if not line:
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) != 3:
            continue
        if tuple(p.casefold() for p in parts) == _CANON_HEADER_ECHO:
            continue  # echoed stage-2 template header, not an answer (A5)
        out.raw_line = raw_line
        out.parsed = True
        s, p, o = parts
        out.subject = s if _QID_RE.match(s) else None
        out.property = p if _PID_RE.match(p) else None
        out.obj = None if o.upper() == "NONE" or not o else o
        return out
    return out
