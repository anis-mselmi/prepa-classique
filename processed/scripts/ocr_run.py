"""OCR scanned PDFs with EasyOCR (CPU). Writes .txt into the extracted_text mirror.

Usage:
  ocr_run.py --pilot [--max-pages N]      # OCR a representative validation subset
  ocr_run.py --all   [--max-pages N]      # OCR every scanned PDF (long job)
  ocr_run.py --list FILE                  # OCR the rel-paths listed in FILE

Languages: a Latin reader ['fr','en'] is primary (French scientific exams + math).
An Arabic reader ['ar','en'] is used additionally when --arabic is passed.
Models are read from the cached ~/.EasyOCR store (already populated).
"""
import argparse
import json
import os
import sys
import time

import fitz
import numpy as np

from common import REPO, parse_file

OUT_ROOT = os.path.join(REPO, "processed")
TXT_ROOT = os.path.join(OUT_ROOT, "extracted_text")
MANIFEST = os.path.join(OUT_ROOT, "_extract_manifest.json")
OCR_MANIFEST = os.path.join(OUT_ROOT, "_ocr_manifest.json")
FAIL_LOG = os.path.join(OUT_ROOT, "failed_extractions.log")

DPI = 220


def load_manifest():
    return json.load(open(MANIFEST, encoding="utf-8"))


def scanned_paths():
    return [m["filepath"] for m in load_manifest() if m["scanned"]]


def pick_pilot():
    """~36 files spanning tracks, eras, and OCR-challenging subjects."""
    m = {x["filepath"]: x for x in load_manifest()}
    scanned = [p for p in m if m[p]["scanned"]]
    meta = {p: parse_file(os.path.join(REPO, p)) for p in scanned}
    want_subj = ["Maths", "Maths I", "Physique", "Chimie", "Francais",
                 "Anglais", "Biologie Animale", "Geologie", "STA", "Informatique"]
    eras = [(2000, 2005), (2006, 2012), (2013, 2021)]
    picked, seen = [], set()
    for track in ["MP", "PC", "BG", "T"]:
        for era in eras:
            got = 0
            for subj in want_subj:           # up to 3 DISTINCT subjects per cell
                if got >= 3:
                    break
                cand = [p for p in scanned
                        if meta[p]["track"] == track
                        and meta[p]["subject"] == subj
                        and era[0] <= (meta[p]["year"] or 0) <= era[1]
                        and p not in seen]
                if cand:
                    cand.sort(key=lambda p: m[p]["pages"])  # prefer shorter
                    picked.append(cand[0]); seen.add(cand[0]); got += 1
    return picked


def page_image(page, dpi=DPI):
    pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csGRAY)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
    return img


def ocr_file(path, readers, max_pages, dpi=DPI):
    texts = []
    with fitz.open(path) as doc:
        n = doc.page_count if not max_pages else min(max_pages, doc.page_count)
        for i in range(n):
            img = page_image(doc[i], dpi)
            page_lines = []
            for rd in readers:
                try:
                    res = rd.readtext(img, detail=0, paragraph=True)
                    page_lines.extend(res)
                except Exception as e:
                    page_lines.append(f"[ocr-error:{e}]")
            texts.append(f"--- page {i+1} ---\n" + "\n".join(page_lines))
    return "\n\n".join(texts)


def out_path_for(rel):
    return os.path.join(TXT_ROOT, os.path.splitext(rel)[0] + ".txt")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--list")
    ap.add_argument("--max-pages", type=int, default=0)
    ap.add_argument("--dpi", type=int, default=DPI)
    ap.add_argument("--arabic", action="store_true")
    args = ap.parse_args()

    if args.pilot:
        targets = pick_pilot()
    elif args.all:
        targets = scanned_paths()
    elif args.list:
        targets = [l.strip() for l in open(args.list, encoding="utf-8") if l.strip()]
    else:
        ap.error("choose --pilot | --all | --list")

    print(f"OCR targets: {len(targets)} files, max_pages={args.max_pages or 'all'}")

    import easyocr
    print("Loading EasyOCR readers (cached models)...", flush=True)
    readers = [easyocr.Reader(["fr", "en"], gpu=False, verbose=False)]
    if args.arabic:
        readers.append(easyocr.Reader(["ar", "en"], gpu=False, verbose=False))
    print(f"Readers ready: {len(readers)}", flush=True)

    results = []
    t0 = time.time()
    for i, rel in enumerate(targets, 1):
        path = os.path.join(REPO, rel)
        ts = time.time()
        try:
            text = ocr_file(path, readers, args.max_pages, args.dpi)
            op = out_path_for(rel)
            os.makedirs(os.path.dirname(op), exist_ok=True)
            with open(op, "w", encoding="utf-8") as f:
                f.write(text)
            chars = sum(1 for c in text if not c.isspace())
            dt = time.time() - ts
            print(f"[{i}/{len(targets)}] OK {chars}c {dt:.1f}s  {rel}", flush=True)
            results.append({"filepath": rel, "chars": chars, "seconds": round(dt, 1),
                            "method": "easyocr", "ok": True})
        except Exception as e:
            print(f"[{i}/{len(targets)}] FAIL {e}  {rel}", flush=True)
            with open(FAIL_LOG, "a", encoding="utf-8") as f:
                f.write(f"{rel}\tocr: {e}\n")
            results.append({"filepath": rel, "ok": False, "error": str(e)})

    # merge into ocr manifest
    prev = {}
    if os.path.exists(OCR_MANIFEST):
        for r in json.load(open(OCR_MANIFEST, encoding="utf-8")):
            prev[r["filepath"]] = r
    for r in results:
        prev[r["filepath"]] = r
    json.dump(list(prev.values()), open(OCR_MANIFEST, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    ok = sum(1 for r in results if r.get("ok"))
    print(f"\nOCR DONE: {ok}/{len(targets)} ok in {time.time()-t0:.0f}s -> {OCR_MANIFEST}")


if __name__ == "__main__":
    main()
