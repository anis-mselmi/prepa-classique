"""Step 3: parse extracted text into questions/answers -> structured_dataset.json

For each PDF we emit one object following the requested schema:
  {track, subject, year, type, questions: [
      {question_id, question_text, official_answer, max_grade, section, marker}
  ]}

Segmentation is best-effort: exam questions are numbered with markers such as
`1-`, `2.`, `1.1-`, `3)` and grouped under `Problème`/`Partie`/`Exercice`
sections. For `sujet` files question text goes in question_text; for
`correction` files the same blocks are the official answers, so they are placed
in official_answer (question_text left null). Where a sujet and a correction for
the same (track, subject, year) both parse into aligned numbered items, the
answers are merged back into the sujet's official_answer fields.
"""
import json
import os
import re
from collections import defaultdict

from common import REPO, iter_pdfs, parse_file

OUT_ROOT = os.path.join(REPO, "processed")
TXT_ROOT = os.path.join(OUT_ROOT, "extracted_text")
OUT_JSON = os.path.join(OUT_ROOT, "structured_dataset.json")

# A question marker at the start of a line: 1-  2.  1.1-  3)  10.2.1-
Q_MARKER = re.compile(r"^\s*((?:\d+\.)*\d+)\s*([-.)])\s+(?=\S)")
SECTION = re.compile(r"^\s*((?:Probl[èe]me|Partie|Exercice|Sous[- ]partie)\b[^\n]*)",
                     re.IGNORECASE)
PAGE_MARK = re.compile(r"^\s*---\s*page\s+\d+\s*---\s*$", re.IGNORECASE)
# barème / grade like "(2 pts)" "/ 1,5" "1.5 point"
GRADE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:pts?|points?)\b", re.IGNORECASE)


def txt_path_for(rel_pdf):
    return os.path.join(TXT_ROOT, os.path.splitext(rel_pdf)[0] + ".txt")


def clean(s):
    return re.sub(r"[ \t]+", " ", s).strip()


def segment(text):
    """Yield (marker, section, body) tuples for each detected question."""
    lines = text.splitlines()
    section = None
    items = []
    cur = None  # dict marker, body lines
    for ln in lines:
        if PAGE_MARK.match(ln):
            continue
        sm = SECTION.match(ln)
        if sm and not Q_MARKER.match(ln):
            section = clean(sm.group(1))
            # don't start a question; section header
            if cur:
                cur["body"].append(ln)
            continue
        qm = Q_MARKER.match(ln)
        if qm:
            if cur:
                items.append(cur)
            cur = {"marker": qm.group(1) + qm.group(2), "section": section,
                   "body": [ln]}
        else:
            if cur:
                cur["body"].append(ln)
    if cur:
        items.append(cur)
    out = []
    for it in items:
        body = clean("\n".join(it["body"]))
        out.append({"marker": it["marker"], "section": it["section"], "body": body})
    return out


def grade_of(body):
    m = GRADE.search(body)
    if m:
        try:
            return float(m.group(1).replace(",", "."))
        except ValueError:
            return None
    return None


def build():
    # group files by (track, subject, year) to merge sujet+correction
    files = []
    for pdf in iter_pdfs():
        rel = os.path.relpath(pdf, REPO).replace("\\", "/")
        meta = parse_file(pdf)
        tp = txt_path_for(rel)
        text = ""
        if os.path.exists(tp):
            with open(tp, encoding="utf-8") as f:
                text = f.read()
        files.append({"rel": rel, "meta": meta, "text": text})

    # pre-parse answers from corrections, keyed by (t,s,y) -> {marker: answer}
    corr_by_key = defaultdict(dict)
    for fr in files:
        if fr["meta"]["type"] == "correction" and fr["text"].strip():
            for it in segment(fr["text"]):
                corr_by_key[(fr["meta"]["track"], fr["meta"]["subject"],
                             fr["meta"]["year"])].setdefault(it["marker"], it["body"])

    dataset = []
    for fr in files:
        meta, rel, text = fr["meta"], fr["rel"], fr["text"]
        key = (meta["track"], meta["subject"], meta["year"])
        items = segment(text) if text.strip() else []
        questions = []
        for n, it in enumerate(items, 1):
            qid = f"{meta['track']}_{meta['subject'].replace(' ', '')}_{meta['year']}_Q{n}"
            if meta["type"] == "correction":
                q_text, ans = None, it["body"]
            else:
                q_text = it["body"]
                ans = corr_by_key.get(key, {}).get(it["marker"])  # merge if available
            questions.append({
                "question_id": qid,
                "question_text": q_text,
                "official_answer": ans,
                "max_grade": grade_of(it["body"]),
                "section": it["section"],
                "marker": it["marker"],
            })
        dataset.append({
            "track": meta["track"],
            "subject": meta["subject"],
            "year": meta["year"],
            "type": meta["type"],
            "filepath": rel,
            "text_extracted": bool(text.strip()),
            "num_questions": len(questions),
            "questions": questions,
        })

    dataset.sort(key=lambda d: (d["track"] or "", d["year"] or 0, d["subject"], d["type"]))
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, indent=1)

    total_q = sum(d["num_questions"] for d in dataset)
    withtext = sum(1 for d in dataset if d["text_extracted"])
    print(f"Wrote {len(dataset)} file-objects ({withtext} with text), "
          f"{total_q} questions -> {OUT_JSON}")


if __name__ == "__main__":
    build()
