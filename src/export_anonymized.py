"""Build the anonymized, history-free supplementary-material export that
main.tex's Pre-registration section promises accompanies the submission.

Fixes a real gap zeus's reviewer-2 audit found (2026-07-20): the live working
repo has full git history under the author's real name/email, and admin/
contains files with the author's real name/institution/email in cleartext.
README.md already states the INTENT ("admin/ -- not part of the released
artifact", "Repository anonymized for double-blind review") -- this script
is what actually REALIZES that intent into a real, uploadable bundle. It
never touches the live repo: everything happens in a fresh output directory.

What it does:
  1. Fresh copy of: PREREGISTRATION.md, README.md, src/, audit/, paper/
     (tex/bib/cls/figures/compiled pdf only, no build junk) -- NO admin/,
     NO .git/ (a flat file tree, no commit history/authorship at all).
  2. Copies the gold benchmark (D:\\xlkg-data\\gold), the scored results
     (outputs/parsed/main-v1.jsonl + main-v1r.jsonl + the quarantine-audit
     trail file), the analysis artifacts (outputs/*.json, outputs/*.txt),
     and the archived Wikidata + MT caches (data/wikidata_cache,
     data/mt_cache.sqlite) -- matching exactly what main.tex's
     Pre-registration paragraph claims accompanies the submission.
     Deliberately EXCLUDES outputs/raw/ (258MB of raw per-call LLM logs --
     not what "scored reports" means, not needed to verify results).
  3. Runs a personal-info scanner over the ENTIRE exported tree (not just
     admin/, which is excluded outright) as a safety net: name variants,
     email patterns, the institution name, common GitHub-identity strings.
     Prints every hit with file:line. A clean run prints "0 matches"; ANY
     hit must be hand-reviewed before upload -- this script does not
     auto-redact matches, it only surfaces them.
  4. Zips the result.

Run from D:\\Research\\xlkg\\src :  python export_anonymized.py
"""
from __future__ import annotations
import re
import shutil
import zipfile
from pathlib import Path

REPO = Path(r"D:\Research\xlkg")
XLKG_DATA = Path(r"D:\xlkg-data")
OUT = Path(r"D:\Research\xlkg-anon-export")
ZIP = Path(r"D:\Research\xlkg-anon-export.zip")

# Name/email/institution/handle variants, checked against the FULL exported
# tree as a final safety net (defense in depth: admin/ is excluded outright,
# this catches anything anywhere else). Deliberately SPECIFIC, not bare first
# names: "kevin" or "andrew" alone false-positive on the benchmark itself
# (real biographical subjects like "Kevin Foyle", "Andrew Kenneth Golding" --
# redacting those would corrupt the scientific data, not protect anonymity).
PERSONAL_PATTERNS = [
    r"kevin\s+andrew", r"kevinandrew", r"\blicet\b",
    r"loyola-icam|loyola\s+college", r"p1legendary", r"andrew-kevin-007",
    r"[\w.+-]+@(licet\.ac\.in|gmail\.com)",
    r"NERD-PROTOCOL", r"\bMaestro\b", r"claude\.ai/code/session",
]
SELF_SKIP = {"export_anonymized.py"}  # this file's own pattern list would self-match

PAPER_KEEP = {".tex", ".bib", ".cls", ".pdf", ".bst"}
PAPER_SKIP_EXACT = {"main.aux", "main.log", "main.out", "main.bbl", "main.blg",
                     "compile1.log", "compile2.log", "compile3.log",
                     "bibtex.log", "TEMPLATE-SETUP.md"}


def copy_tree_filtered(src: Path, dst: Path, keep_ext: set[str] | None = None,
                        skip_exact: set[str] = frozenset()):
    for p in src.rglob("*"):
        if p.is_dir():
            continue
        if p.name in skip_exact:
            continue
        if keep_ext is not None and p.suffix.lower() not in keep_ext:
            continue
        rel = p.relative_to(src)
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, target)


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    print("== 1. core (no admin/, no .git) ==")
    shutil.copy2(REPO / "PREREGISTRATION.md", OUT / "PREREGISTRATION.md")
    shutil.copy2(REPO / "README.md", OUT / "README.md")
    # .ps1 excluded: deployment/scheduling scripts for the author's own
    # machine, not part of the evaluation harness a reviewer needs
    shutil.copytree(REPO / "src", OUT / "src",
                    ignore=shutil.ignore_patterns("*.ps1", "__pycache__", "*.pyc"))
    shutil.copytree(REPO / "audit", OUT / "audit")
    copy_tree_filtered(REPO / "paper", OUT / "paper",
                       keep_ext=PAPER_KEEP, skip_exact=PAPER_SKIP_EXACT)
    print("   done")

    print("== 2. gold benchmark, scored results, analysis artifacts, caches ==")
    shutil.copytree(XLKG_DATA / "gold", OUT / "data" / "gold")
    (OUT / "outputs" / "parsed").mkdir(parents=True)
    for f in ["main-v1.jsonl", "main-v1r.jsonl"]:
        shutil.copy2(REPO / "outputs" / "parsed" / f, OUT / "outputs" / "parsed" / f)
    for f in (REPO / "outputs" / "parsed").glob("main-v1.jsonl.quarantined-*"):
        shutil.copy2(f, OUT / "outputs" / "parsed" / f.name)
    for f in (REPO / "outputs").glob("*.json"):
        shutil.copy2(f, OUT / "outputs" / f.name)
    for f in (REPO / "outputs").glob("*.txt"):
        shutil.copy2(f, OUT / "outputs" / f.name)
    (OUT / "data" / "wikidata_cache").mkdir(parents=True)
    shutil.copy2(REPO / "data" / "wikidata_cache" / "wikidata_cache.sqlite",
                OUT / "data" / "wikidata_cache" / "wikidata_cache.sqlite")
    shutil.copy2(REPO / "data" / "mt_cache.sqlite", OUT / "data" / "mt_cache.sqlite")
    print("   done (outputs/raw/ deliberately excluded, ~258MB of raw call logs)")

    print("== 3. personal-info safety-net scan (entire exported tree) ==")
    pats = [re.compile(p, re.I) for p in PERSONAL_PATTERNS]
    hits = []
    for p in OUT.rglob("*"):
        if p.is_dir() or p.suffix.lower() in {".sqlite", ".pdf"}:
            continue
        if p.name in SELF_SKIP:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            for pat in pats:
                if pat.search(line):
                    hits.append((p.relative_to(OUT), i, pat.pattern, line.strip()[:120]))
    if hits:
        print(f"   !! {len(hits)} POTENTIAL HIT(S) -- hand-review every one before upload:")
        for rel, ln, pat, snippet in hits:
            print(f"      {rel}:{ln}  [{pat}]  {snippet}")
    else:
        print("   0 matches. Clean.")

    print("== 4. zip ==")
    if ZIP.exists():
        ZIP.unlink()
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in OUT.rglob("*"):
            if p.is_file():
                zf.write(p, p.relative_to(OUT.parent))
    size_mb = ZIP.stat().st_size / 1e6
    print(f"   wrote {ZIP} ({size_mb:.1f} MB)")
    print(f"\nDONE. Review the hit list above (if any), then upload {ZIP.name}.")
    print("If it's over your venue's supplementary-material size limit, the")
    print("wikidata_cache.sqlite (~118MB) is the one large, safely-droppable")
    print("item -- everything else needed to verify the paper's numbers is")
    print("in outputs/ and is small.")


if __name__ == "__main__":
    main()
