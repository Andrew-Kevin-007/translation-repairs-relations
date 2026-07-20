"""Tally the filled Tamil audit worksheet -> validity rate + C2 miss rate.
Usage: python audit_tally.py [path-to-filled-csv]"""
import csv, sys

path = sys.argv[1] if len(sys.argv) > 1 else r"D:/xlkg-data/audit/tamil-audit-worksheet.csv"
rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
facts = [r for r in rows if r["VALID? (Y/N)"].strip()]
invalid = [r for r in facts if r["VALID? (Y/N)"].strip().upper().startswith("N")]
items = {}
for r in rows:
    iid = r["item_id"]
    miss_col = r["MISSING facts asserted by sentence but absent from gold (write; blank=none)"].strip()
    if iid not in items:
        items[iid] = miss_col not in ("", "—")
n_items = len(items)
miss_items = sum(items.values())
print(f"facts judged: {len(facts)}/1090 | invalid facts: {len(invalid)} "
      f"({100*len(invalid)/max(1,len(facts)):.1f}% of judged)")
print(f"items with missing facts: {miss_items}/{n_items} = {100*miss_items/max(1,n_items):.2f}%")
print(f"C2 threshold 5%: {'REACHED -> understates claim' if miss_items/max(1,n_items) >= 0.05 else 'NOT reached -> reliable-reuse (inverse) claim'}")
