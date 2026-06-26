# Processed dataset — Concours Prépa Classique (MP / PC / BG / T)

Automated pipeline output built from the exam PDFs in this repo (énoncés + corrections).

## Contents

| File | Description |
|------|-------------|
| `dataset_index.csv` | Inventory of every PDF: `track, subject, year, type, filename, filepath` |
| `structured_dataset.json` | One object per PDF with a `questions` array (see schema below) |
| `extracted_text/<TRACK>/<YEAR>/*.txt` | Extracted plain text, mirroring the repo layout |
| `failed_extractions.log` | Files that could not be extracted (tab-separated: `filepath <TAB> reason`) |
| `_extract_manifest.json` | Per-file extraction metrics (method, chars, pages, scanned flag) |
| `_ocr_manifest.json` | Per-file OCR metrics (only files processed by OCR) |

## How it was built

1. **Inventory** — filenames follow `YEAR.TRACK.SUBJECT.TYPE.pdf`. `track` and `year`
   are taken from the folder layout (most reliable); `subject` is normalized
   (e.g. `Math`/`Mathématiques` → `Maths`); `type` is `correction` when the name
   contains `corr`, otherwise `sujet` (covers `eno`, `ép`, and bare names used in
   2022/2023/2025).
2. **Text extraction** — PyMuPDF (primary), pdfplumber (fallback).
3. **OCR fallback** — PDFs with no text layer are image-only scans. OCR uses
   **EasyOCR** (French + English models; Arabic optional) on CPU.
   > Note: the originally requested **PaddleOCR** has no wheels for Python 3.14 on
   > this machine, so EasyOCR (equivalent PP-OCR-class quality) was used instead.
4. **Structuring** — text is segmented into numbered questions (`1-`, `2.`, `1.1-`,
   `3)`) grouped under `Problème`/`Partie`/`Exercice` sections. For `sujet` files the
   text goes in `question_text`; for `correction` files it goes in `official_answer`.
   When a sujet and its correction share aligned numbering, answers are merged into
   the sujet's `official_answer`.

## structured_dataset.json schema

```json
{
  "track": "MP",
  "subject": "Maths",
  "year": 2022,
  "type": "sujet | correction",
  "filepath": "MP/2022/2022.MP.Math I.pdf",
  "text_extracted": true,
  "num_questions": 12,
  "questions": [
    {
      "question_id": "MP_Maths_2022_Q1",
      "question_text": "...",
      "official_answer": "...",
      "max_grade": null,
      "section": "Problème 1",
      "marker": "1-"
    }
  ]
}
```

## Coverage note

Most PDFs (≈ 93%) are scanned images and require OCR; only ≈ 7% (mostly 2018–2025)
carry a real text layer. OCR text quality on decades-old scanned French + math
exams is imperfect — treat `question_text`/`official_answer` from OCR'd files as
best-effort. Original PDFs are never modified.
