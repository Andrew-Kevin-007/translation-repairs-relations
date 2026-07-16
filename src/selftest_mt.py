"""Live smoke test for the pivot-arm MT engine (IndicTrans2, CPU).

Run inside the MT venv (D:\\xlkg-models\\venv-mt, Python 3.11):
    python selftest_mt.py

Uses the distilled 200M indic-en model for plumbing validation; the run-matrix
wiring decides dist-200M vs 1B against observed quality on the study data
(admin/mt-backend-verification.md). Weights cache to D: (HF_HOME).
"""

import os

os.environ.setdefault("HF_HOME", r"D:\xlkg-models\hf")

import torch  # noqa: E402
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer  # noqa: E402

# IndicTransToolkit ships no Windows wheels; we run a faithful pure-Python port
# of its IndicProcessor (see vendor/indictrans_processor.py for provenance).
from vendor.indictrans_processor import IndicProcessor

MODEL = "ai4bharat/indictrans2-indic-en-dist-200M"

CASES = [
    ("tam_Taml", "சென்னை தமிழ்நாட்டின் தலைநகரம் ஆகும்."),
    ("hin_Deva", "दिल्ली भारत की राजधानी है।"),
    ("ben_Beng", "রবীন্দ্রনাথ ঠাকুর ১৮৬১ সালে জন্মগ্রহণ করেন।"),
]


def main() -> int:
    print("loading", MODEL)
    tok = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True)
    model = AutoModelForSeq2SeqLM.from_pretrained(MODEL, trust_remote_code=True)
    model.eval()
    ip = IndicProcessor(inference=True)

    ok = True
    for lang, sent in CASES:
        batch = ip.preprocess_batch([sent], src_lang=lang, tgt_lang="eng_Latn")
        inputs = tok(batch, return_tensors="pt", padding=True)
        with torch.no_grad():
            out = model.generate(**inputs, max_length=64, num_beams=4)
        dec = tok.batch_decode(out, skip_special_tokens=True,
                               clean_up_tokenization_spaces=True)
        post = ip.postprocess_batch(dec, lang="eng_Latn")
        print("%s -> %s" % (lang, post[0]))
        if not post[0].strip():
            ok = False

    print("MT SMOKE %s" % ("OK" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
