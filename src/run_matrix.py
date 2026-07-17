"""Experiment runner: languages x systems x arms (PREREGISTRATION.md section 2).

Arms:
  D (direct)   — source-language sentence -> extract -> canonicalize
  P (pivot)    — source sentence -> MT to English -> same English pipeline
  E (english)  — English control slice -> extract -> canonicalize (ceiling)

Pipeline per item (all stages archive raw generations BEFORE parsing):
  sentence --[arm transform]--> stage-1 extraction (llm_backend) -> parse ->
  per-triple stage-2 canonicalization (canonicalize.py, candidates retrieved
  outside the LLM) -> parsed-results JSONL under outputs/parsed/.

Resumable by construction: each (item, model, arm) already present in the
parsed-results file is skipped; raw archives are append-only. Kill it anytime.

Scoring lives in score.py, NOT here. Hard rule: no scoring until the
pre-registration commit (61f1ee1) is an ancestor of HEAD — enforced in
score.py against git itself.

Still TODO when real data lands (day 5+):
  - materialize XAlign reversed gold (or fallback rebuild) into dataset.py
    format under data/
  - closed relation inventory -> property_inventory (canonicalize.py §5)
  - mREBEL baseline row (admin/mrebel-coverage.md; day-8 keep/drop gate)
  - few-shot prompt variant (K fixed before the day-8 freeze)
  - QE scores per pivot translation (B2 probe 1; admin/qe-tool-verification.md)
  - synthetic-parallel probe (en->indic MT of English gold, arm D on it)
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from canonicalize import canonicalize_triple
from dataset import load_items
from llm_backend import MODELS, LlamaServer, RawArchive, response_text
from mt_backend import MTBackend
from parse_outputs import parse_extraction
from wikidata_client import WikidataClient

LANGUAGES = ["hi", "bn", "te", "ta", "kn", "ml", "mr", "gu"]
CONTROL = "en"
ARMS = ["direct", "pivot", "english"]

OUT_ROOT = Path(__file__).resolve().parent.parent / "outputs"

_EXTRACT_TEMPLATE = None


def extract_template() -> str:
    global _EXTRACT_TEMPLATE
    if _EXTRACT_TEMPLATE is None:
        lines = (Path(__file__).resolve().parent / "prompts" / "direct_extract.txt")\
            .read_text(encoding="utf-8").splitlines()
        _EXTRACT_TEMPLATE = "\n".join(l for l in lines if not l.startswith("#")).strip()
    return _EXTRACT_TEMPLATE


def arm_input(item, arm: str, mt: MTBackend) -> tuple[str, str] | None:
    """(sentence, surface_lang) the arm feeds to the pipeline; None = arm
    does not apply to this item (language/control mismatches)."""
    if arm == "direct":
        return (item.sentence, item.lang) if item.lang != CONTROL else None
    if arm == "pivot":
        if item.lang == CONTROL:
            return None
        return (mt.translate(item.sentence, item.lang), CONTROL)
    if arm == "english":
        return (item.sentence, CONTROL) if item.lang == CONTROL else None
    raise ValueError(arm)


def done_keys(results_path: Path) -> set[tuple]:
    done = set()
    if results_path.exists():
        for line in results_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                done.add((r["item_id"], r["model"], r["arm"]))
    return done


def run(dataset_path: str, model_keys: list[str], arms: list[str],
        run_id: str, mt_model: str | None = None,
        property_inventory: list[dict] | None = None) -> Path:
    items = load_items(dataset_path)
    out_dir = OUT_ROOT / "parsed"
    out_dir.mkdir(parents=True, exist_ok=True)
    results_path = out_dir / ("%s.jsonl" % run_id)
    done = done_keys(results_path)

    wd = WikidataClient()
    mt_kwargs = {"model": mt_model} if mt_model else {}
    with MTBackend(**mt_kwargs) as mt:
        for model_key in model_keys:                 # sequential: 6 GB VRAM
            spec = MODELS[model_key]
            todo = [(it, arm) for it in items for arm in arms
                    if (it.id, spec.name, arm) not in done
                    and arm_input(it, arm, mt) is not None]
            # note: arm_input may translate during planning; cache absorbs it
            if not todo:
                continue
            raw_x = RawArchive(OUT_ROOT / "raw" / ("%s.%s.extract.jsonl" % (run_id, spec.name)))
            raw_c = RawArchive(OUT_ROOT / "raw" / ("%s.%s.canon.jsonl" % (run_id, spec.name)))
            with LlamaServer(spec) as server:
                for item, arm in todo:
                    sentence, surf_lang = arm_input(item, arm, mt)
                    messages = [{"role": "user", "content":
                                 extract_template().format(sentence=sentence)}]
                    t_x0 = time.perf_counter()
                    resp = server.chat(messages, max_tokens=256)
                    extract_s = time.perf_counter() - t_x0
                    raw_x.append(spec, messages, resp,
                                 meta={"item_id": item.id, "arm": arm,
                                       "lang": item.lang, "surface_lang": surf_lang,
                                       "run_id": run_id})
                    parsed = parse_extraction(response_text(resp))
                    t_c0 = time.perf_counter()
                    canon = []
                    for st in parsed.triples:
                        # a single pathological triple must not kill a multi-day
                        # run: failures are archived and scored as unresolved
                        try:
                            cp = canonicalize_triple(
                                server, raw_c, st, surf_lang, wd,
                                property_inventory=property_inventory,
                                meta={"item_id": item.id, "arm": arm, "run_id": run_id})
                        except Exception as e:
                            canon.append({"surface": list(st), "subject_qid": None,
                                          "property_pid": None, "object": None,
                                          "parsed": False, "error": str(e)[:300]})
                            print("CANON-FAIL %s %s %s: %s"
                                  % (item.id, spec.name, arm, str(e)[:160]), flush=True)
                            continue
                        canon.append({
                            "surface": list(st),
                            "subject_qid": cp.subject, "property_pid": cp.property,
                            "object": cp.obj, "parsed": cp.parsed})
                    record = {
                        "ts_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        "run_id": run_id, "item_id": item.id, "model": spec.name,
                        "arm": arm, "lang": item.lang, "surface_lang": surf_lang,
                        "sentence_used": sentence,
                        "surface_triples": [list(t) for t in parsed.triples],
                        "canonical": canon,
                        "flags": {"had_think": parsed.had_think,
                                  "is_none": parsed.is_none,
                                  "unparsed_lines": parsed.unparsed_lines},
                        # exploratory cost accounting (never enters verdicts):
                        # wall seconds per stage + engine-reported token usage
                        "cost": {"extract_s": round(extract_s, 3),
                                 "canon_s": round(time.perf_counter() - t_c0, 3),
                                 "usage": resp.get("usage")},
                    }
                    with open(results_path, "a", encoding="utf-8") as f:
                        f.write(json.dumps(record, ensure_ascii=False) + "\n")
                    print("done %s %s %s (%d triples)" %
                          (item.id, spec.name, arm, len(canon)), flush=True)
    return results_path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--models", default="qwen3-8b")
    ap.add_argument("--arms", default="direct,pivot,english")
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--mt-model", default=None)
    ap.add_argument("--property-inventory", default=None,
                    help="JSON file: [{id,label,description}] closed relation set")
    args = ap.parse_args()
    inventory = None
    if args.property_inventory:
        inventory = json.loads(Path(args.property_inventory).read_text(encoding="utf-8"))
    path = run(args.dataset, args.models.split(","), args.arms.split(","),
               args.run_id, args.mt_model, property_inventory=inventory)
    print("results ->", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
