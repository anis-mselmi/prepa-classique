"""Shared helpers: filename -> metadata parsing and subject normalization."""
import os
import re
import unicodedata

# Repo root: env override, else two levels up from this file (processed/scripts/ -> repo)
REPO = os.environ.get("PREPA_REPO") or os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".."))
TRACKS = {"MP", "PC", "BG", "T"}

# Canonical subject map (key = accent-stripped, lowercased, space-collapsed)
SUBJECT_CANON = {
    "math": "Maths",
    "maths": "Maths",
    "mathematique": "Maths",
    "mathematiques": "Maths",
    "mathsmatique": "Maths",
    "math i": "Maths I",
    "maths i": "Maths I",
    "mathematiques i": "Maths I",
    "math ii": "Maths II",
    "maths ii": "Maths II",
    "mathematiques ii": "Maths II",
    "francais": "Francais",
    "anglais": "Anglais",
    "physique": "Physique",
    "chimie": "Chimie",
    "chimie inorganique": "Chimie Inorganique",
    "chimie organique": "Chimie Organique",
    "biochimie": "Biochimie",
    "biologie animale": "Biologie Animale",
    "biologie vegetale": "Biologie Vegetale",
    "geologie": "Geologie",
    "informatique": "Informatique",
    "sta": "STA",
    "sta(msi-aut)": "STA",
    "cfm": "CFM",
}

# Tokens that indicate the file's type rather than a subject
TYPE_TOKENS = {"eno", "corr", "ep", "enonce", "correction", "epreuve"}


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s)
                    if unicodedata.category(c) != "Mn")


def normalize_subject(raw: str) -> str:
    key = strip_accents(raw).lower().strip()
    key = re.sub(r"\s+", " ", key)
    if key in SUBJECT_CANON:
        return SUBJECT_CANON[key]
    # Title-case fallback for anything unmapped
    return raw.strip().title()


def parse_file(filepath: str):
    """Return dict(track, subject, year, type) from a PDF path inside REPO.
    track/year come from the directory layout; subject/type from the filename."""
    rel = os.path.relpath(filepath, REPO)
    parts = rel.replace("\\", "/").split("/")
    track = parts[0] if parts[0] in TRACKS else None

    # year = first 4-digit path segment
    year = None
    for p in parts:
        m = re.fullmatch(r"(19|20)\d{2}", p)
        if m:
            year = int(p)
            break

    name = os.path.splitext(os.path.basename(filepath))[0]
    # Type detection: 'corr' anywhere -> correction, else sujet
    low = strip_accents(name).lower()
    ftype = "correction" if re.search(r"(^|[.\s_-])corr", low) else "sujet"

    # Build subject by dropping year / track / type tokens
    tokens = name.split(".")
    kept = []
    for tok in tokens:
        t = tok.strip()
        if not t:
            continue
        tl = strip_accents(t).lower()
        if re.fullmatch(r"(19|20)\d{2}", t):
            continue
        if t in TRACKS:
            continue
        if tl in TYPE_TOKENS:
            continue
        kept.append(t)
    raw_subject = " ".join(kept).strip() if kept else name
    subject = normalize_subject(raw_subject)
    return {"track": track, "subject": subject, "year": year,
            "type": ftype, "raw_subject": raw_subject}


def iter_pdfs():
    for root, dirs, files in os.walk(REPO):
        if ".git" in root.split(os.sep):
            continue
        dirs[:] = [d for d in dirs if d != ".git"]
        for f in files:
            if f.lower().endswith(".pdf"):
                yield os.path.join(root, f)
