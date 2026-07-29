"""MT worker — runs INSIDE the MT venv (D:\\xlkg-models\\venv-mt, Python 3.11).

Protocol (line-delimited JSON over stdio; parent: src/mt_backend.py):
  stdin  <- {"id": "...", "text": "...", "src_lang": "tam_Taml", "tgt_lang": "eng_Latn"}
  stdout -> {"id": "...", "translation": "..."}
Loads the model once, then streams. "READY" is printed on stdout when warm.
Model repo comes from argv[1] (default: dist-200M). CORRECTION 2026-07-29
(zeus HOD-revision audit): this comment previously claimed "runs use the 1B";
that was false. run_matrix.py's --mt-model defaults to None and
run_matrix_forever.ps1 never passes it, so mt_backend.DEFAULT_MODEL
(dist-200M) is what actually ran. Verified against data/mt_cache.sqlite:
4,447 of 4,447 cached rows are attributed to
ai4bharat/indictrans2-indic-en-dist-200M; zero rows for any other model.
main.tex now names the checkpoint explicitly. Deterministic: beam search, no
sampling.
"""

import json
import os
import sys

os.environ.setdefault("HF_HOME", r"D:\xlkg-models\hf")

import torch  # noqa: E402
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer  # noqa: E402

from vendor.indictrans_processor import IndicProcessor  # noqa: E402


def main() -> int:
    model_name = sys.argv[1] if len(sys.argv) > 1 else "ai4bharat/indictrans2-indic-en-dist-200M"
    tok = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_name, trust_remote_code=True)
    model.eval()
    ip = IndicProcessor(inference=True)

    print("READY", flush=True)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        req = json.loads(line)
        batch = ip.preprocess_batch([req["text"]], src_lang=req["src_lang"],
                                    tgt_lang=req.get("tgt_lang", "eng_Latn"))
        inputs = tok(batch, return_tensors="pt", padding=True)
        with torch.no_grad():
            out = model.generate(**inputs, max_length=256, num_beams=4)
        dec = tok.batch_decode(out, skip_special_tokens=True,
                               clean_up_tokenization_spaces=True)
        post = ip.postprocess_batch(dec, lang=req.get("tgt_lang", "eng_Latn"))
        print(json.dumps({"id": req["id"], "translation": post[0]},
                         ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
