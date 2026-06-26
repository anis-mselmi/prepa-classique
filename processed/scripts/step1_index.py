"""Step 1: walk repo, detect metadata, export dataset_index.csv."""
import csv
import os
import sys
from common import REPO, iter_pdfs, parse_file

OUT_DIR = os.path.join(REPO, "processed")
os.makedirs(OUT_DIR, exist_ok=True)
CSV_PATH = os.path.join(OUT_DIR, "dataset_index.csv")

rows = []
for fp in iter_pdfs():
    meta = parse_file(fp)
    rel = os.path.relpath(fp, REPO).replace("\\", "/")
    rows.append({
        "track": meta["track"],
        "subject": meta["subject"],
        "year": meta["year"],
        "type": meta["type"],
        "filename": os.path.basename(fp),
        "filepath": rel,
    })

rows.sort(key=lambda r: (r["track"] or "", r["year"] or 0, r["subject"], r["type"]))

with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["track", "subject", "year", "type", "filename", "filepath"])
    w.writeheader()
    w.writerows(rows)

print(f"Wrote {len(rows)} rows -> {CSV_PATH}")
# Quick summary
from collections import Counter
print("By track:", dict(Counter(r["track"] for r in rows)))
print("By type :", dict(Counter(r["type"] for r in rows)))
print("Years   :", sorted({r["year"] for r in rows}))
print("Subjects:", sorted({r["subject"] for r in rows}))
miss = [r["filepath"] for r in rows if not r["track"] or not r["year"]]
if miss:
    print("WARN missing track/year:", miss[:20], "..." if len(miss) > 20 else "")
