"""Step 2: extract text from every PDF.

Primary engine: PyMuPDF (fitz). Fallback: pdfplumber.
PDFs that yield no/very little text are flagged as 'scanned' (OCR candidates);
if an OCR engine is available it is used, otherwise they are logged for OCR.
Outputs mirror the repo layout under processed/extracted_text/TRACK/YEAR/file.txt
"""
import json
import os
import sys
import traceback

import fitz  # PyMuPDF

from common import REPO, iter_pdfs

OUT_ROOT = os.path.join(REPO, "processed")
TXT_ROOT = os.path.join(OUT_ROOT, "extracted_text")
FAIL_LOG = os.path.join(OUT_ROOT, "failed_extractions.log")
MANIFEST = os.path.join(OUT_ROOT, "_extract_manifest.json")

# A doc is treated as scanned/image-only if it has fewer than this many
# non-whitespace characters per page on average.
SCANNED_CHARS_PER_PAGE = 25

# Try to set up an OCR engine lazily (PaddleOCR preferred, else None)
_OCR = None
_OCR_TRIED = False


def get_ocr():
    global _OCR, _OCR_TRIED
    if _OCR_TRIED:
        return _OCR
    _OCR_TRIED = True
    try:
        from paddleocr import PaddleOCR
        # French + multilingual; Arabic handled by 'arabic' lang if needed.
        _OCR = PaddleOCR(use_angle_cls=True, lang="fr", show_log=False)
        print("  [OCR] PaddleOCR ready (lang=fr)")
    except Exception as e:
        print(f"  [OCR] PaddleOCR unavailable: {e}")
        _OCR = None
    return _OCR


def extract_fitz(path):
    parts = []
    with fitz.open(path) as doc:
        npages = doc.page_count
        for page in doc:
            parts.append(page.get_text("text"))
    return "\n".join(parts), npages


def extract_pdfplumber(path):
    import pdfplumber
    parts = []
    with pdfplumber.open(path) as pdf:
        npages = len(pdf.pages)
        for pg in pdf.pages:
            parts.append(pg.extract_text() or "")
    return "\n".join(parts), npages


def ocr_pdf(path, ocr):
    """Render each page to an image and OCR it."""
    import numpy as np
    texts = []
    with fitz.open(path) as doc:
        for page in doc:
            pix = page.get_pixmap(dpi=200)
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                pix.height, pix.width, pix.n)
            if pix.n == 4:
                img = img[:, :, :3]
            res = ocr.ocr(img, cls=True)
            lines = []
            for block in (res or []):
                for line in (block or []):
                    try:
                        lines.append(line[1][0])
                    except Exception:
                        pass
            texts.append("\n".join(lines))
    return "\n".join(texts)


def out_path_for(pdf_path):
    rel = os.path.relpath(pdf_path, REPO)
    rel_txt = os.path.splitext(rel)[0] + ".txt"
    return os.path.join(TXT_ROOT, rel_txt)


def nonws(s):
    return sum(1 for c in s if not c.isspace())


def main():
    do_ocr = "--ocr" in sys.argv
    pdfs = list(iter_pdfs())
    total = len(pdfs)
    manifest = []
    failures = []
    open(FAIL_LOG, "w", encoding="utf-8").close()  # reset log

    for i, pdf in enumerate(pdfs, 1):
        rel = os.path.relpath(pdf, REPO).replace("\\", "/")
        text, npages, method, err = "", 0, None, None
        try:
            text, npages = extract_fitz(pdf)
            method = "pymupdf"
        except Exception as e:
            err = f"pymupdf: {e}"
            try:
                text, npages = extract_pdfplumber(pdf)
                method = "pdfplumber"
                err = None
            except Exception as e2:
                err = f"pymupdf+pdfplumber failed: {e2}"

        chars = nonws(text)
        per_page = chars / npages if npages else 0
        scanned = npages > 0 and per_page < SCANNED_CHARS_PER_PAGE

        if err is None and scanned and do_ocr:
            ocr = get_ocr()
            if ocr is not None:
                try:
                    otext = ocr_pdf(pdf, ocr)
                    if nonws(otext) > chars:
                        text, method = otext, "paddleocr"
                        chars = nonws(text)
                except Exception as e:
                    err = f"ocr: {e}"

        # Write output (even if empty, so the mirror is complete) unless hard failure
        op = out_path_for(pdf)
        os.makedirs(os.path.dirname(op), exist_ok=True)
        if err is None:
            with open(op, "w", encoding="utf-8") as f:
                f.write(text)
        else:
            failures.append((rel, err))
            with open(FAIL_LOG, "a", encoding="utf-8") as f:
                f.write(f"{rel}\t{err}\n")

        status = ("OK" if err is None else "FAIL")
        flag = " [scanned/no-text]" if (err is None and scanned and method != "paddleocr") else ""
        print(f"[{i}/{total}] {status} {method or '-'} {chars}c {npages}p{flag}  {rel}", flush=True)

        manifest.append({
            "filepath": rel, "method": method, "chars": chars,
            "pages": npages, "scanned": bool(scanned and method != "paddleocr"),
            "error": err, "txt": os.path.relpath(op, REPO).replace("\\", "/") if err is None else None,
        })

    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)

    ok = sum(1 for m in manifest if not m["error"])
    sc = sum(1 for m in manifest if m["scanned"])
    print(f"\nDONE: {ok}/{total} extracted, {len(failures)} failed, {sc} flagged scanned(no-text).")
    print(f"Manifest -> {MANIFEST}")
    print(f"Failures -> {FAIL_LOG} ({len(failures)})")


if __name__ == "__main__":
    main()
