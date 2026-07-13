"""
Phase 2 — Parse PDFs, clean, chunk, and write the processed layer.

Reads:  data/raw/<source>/manifest.jsonl  +  the raw PDFs it points at
Writes: data/processed/<source>/<file_id>.json

Idempotent: a document whose output JSON already exists is skipped.

CHANGED (Phase 3 fallout): the processed JSON now carries meeting_date,
meeting_title and doc_label through from the manifest. Without them the
database cannot cite anything -- metadata lost here is lost forever.
"""

import argparse
import io
import json
import logging
import re
from pathlib import Path

import fitz  # PyMuPDF
import pytesseract
from PIL import Image

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("process")

SOURCE = "bloomington-council"
RAW_DIR = Path("data/raw") / SOURCE
MANIFEST_PATH = RAW_DIR / "manifest.jsonl"
OUTPUT_DIR = Path("data/processed") / SOURCE

CHUNK_SIZE = 1000       # target max characters (~250 tokens, sized for all-MiniLM-L6-v2)
OVERLAP = 150           # characters carried between consecutive chunks
SEPARATORS = ["\n\n", "\n", ". ", " "]
OCR_THRESHOLD = 30      # a page with fewer than this many chars is probably a scan

# Metadata that MUST survive from the manifest into the processed layer.
CARRY_FIELDS = ["meeting_date", "meeting_title", "doc_label", "doc_title", "url"]


# --------------------------------------------------------------------------
# Manifest
# --------------------------------------------------------------------------

def load_manifest(manifest_path: Path) -> list[dict]:
    if not manifest_path.exists():
        raise SystemExit(f"No manifest at {manifest_path} — did Phase 1 run?")
    records = []
    with open(manifest_path) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    if not records:
        raise SystemExit(f"{manifest_path} is empty — did Phase 1 run?")
    log.info("Manifest: %d records", len(records))

    undated = sum(1 for r in records if not r.get("meeting_date"))
    if undated:
        log.warning(
            "%d/%d manifest records have no meeting_date — those documents "
            "will not be citable by date downstream.", undated, len(records)
        )
    return records


def build_index(records: list[dict]) -> dict:
    """Look up a manifest record by saved_path (reliable) or file_id (fallback).

    Phase 1 stores a numeric file_id; this script derives a slug-style id from
    the filename. They don't always agree, so saved_path is the honest join key.
    """
    index = {}
    for r in records:
        if r.get("saved_path"):
            index[("path", Path(r["saved_path"]).name)] = r
        if r.get("file_id") is not None:
            index[("id", str(r["file_id"]))] = r
    return index


def lookup(index: dict, pdf_path: Path, file_id: str) -> dict | None:
    return (
        index.get(("path", pdf_path.name))
        or index.get(("id", file_id))
        # last resort: the trailing numeric id inside a slug like undated_agenda_16961
        or index.get(("id", (m.group(1) if (m := re.search(r"(\d+)$", file_id)) else "")))
    )


# --------------------------------------------------------------------------
# Extraction
# --------------------------------------------------------------------------

def ocr_page(page) -> str:
    """Rasterize a PDF page and OCR it."""
    pix = page.get_pixmap(dpi=200)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    return pytesseract.image_to_string(img)


def extract_pages_smart(pdf_path: Path) -> tuple[list[str], str]:
    """Extract text per page, OCR-ing any page that looks like a scan.

    Returns (pages, mode) where mode is 'digital', 'ocr', or 'mixed'.
    """
    texts, ocr_count = [], 0
    with fitz.open(pdf_path) as doc:
        for page in doc:
            text = page.get_text("text")
            if len(text.strip()) < OCR_THRESHOLD:
                text = ocr_page(page)
                ocr_count += 1
            texts.append(text)

    if ocr_count == 0:
        mode = "digital"
    elif ocr_count == len(texts):
        mode = "ocr"
    else:
        mode = "mixed"
    return texts, mode


# --------------------------------------------------------------------------
# Cleaning
# --------------------------------------------------------------------------

def clean_text(text: str) -> str:
    """Clean conservatively. Every rule you add can also destroy signal."""
    text = text.replace("\u00ad", "")                    # soft hyphens
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)         # rejoin words split across lines
    text = re.sub(r"[ \t]+", " ", text)                  # collapse runs of spaces/tabs
    text = re.sub(r"\n{3,}", "\n\n", text)               # collapse blank-line runs
    return text.strip()


# --------------------------------------------------------------------------
# Chunking
# --------------------------------------------------------------------------

def split_text(text: str, size: int = CHUNK_SIZE) -> list[str]:
    """Recursively split at the coarsest natural boundary that fits `size`."""
    if len(text) <= size:
        return [text] if text.strip() else []

    for sep in SEPARATORS:
        parts = text.split(sep)
        if len(parts) == 1:
            continue                          # separator absent; try a finer one

        chunks, current = [], ""
        for part in parts:
            candidate = (current + sep + part) if current else part
            if len(candidate) <= size:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                if len(part) <= size:
                    current = part
                else:
                    chunks.extend(split_text(part, size))   # recurse: finer separators
                    current = ""
        if current:
            chunks.append(current)
        return [c for c in chunks if c.strip()]

    # last resort: hard cut
    return [text[i:i + size] for i in range(0, len(text), size)]


def add_overlap(chunks: list[str], overlap: int = OVERLAP) -> list[str]:
    """Prefix each chunk (except the first) with the tail of its predecessor."""
    out = []
    for i, c in enumerate(chunks):
        if i == 0:
            out.append(c)
        else:
            out.append(chunks[i - 1][-overlap:] + " … " + c)
    return out


def chunk_pages(pages: list[str], file_id: str) -> list[dict]:
    """Chunk page by page, so every chunk carries a page number for citation."""
    out = []
    for page_no, raw in enumerate(pages, start=1):
        cleaned = clean_text(raw)
        if not cleaned:
            continue
        pieces = add_overlap(split_text(cleaned))
        for i, piece in enumerate(pieces):
            out.append({
                "chunk_id": f"{file_id}:p{page_no}:c{i}",
                "text": piece,
                "page_start": page_no,
                "page_end": page_no,
            })
    return out


# --------------------------------------------------------------------------
# Pipeline
# --------------------------------------------------------------------------

def process_document(record: dict, index: dict, output_dir: Path, force: bool) -> dict | None:
    pdf_path = Path(record["saved_path"])
    if not pdf_path.exists():
        log.warning("Missing PDF %s — skipping", pdf_path)
        return None

    file_id = pdf_path.stem                      # e.g. "undated_agenda_16961"
    out_path = output_dir / f"{file_id}.json"
    if out_path.exists() and not force:
        return {"skipped": True}

    meta = lookup(index, pdf_path, file_id)
    if meta is None:
        # Shout. A doc with no manifest record has no date, title or label,
        # and would silently become an uncitable NULL row downstream.
        log.error("No manifest record for %s — cannot attach metadata", pdf_path.name)
        return None

    pages, mode = extract_pages_smart(pdf_path)
    chunks = chunk_pages(pages, file_id)

    doc = {
        "file_id": file_id,
        "source_path": str(pdf_path),
        "pages": len(pages),
        "extraction_mode": mode,
        # --- the metadata that Phase 3 needs and the old version dropped ---
        **{k: meta.get(k) for k in CARRY_FIELDS},
        "chunks": chunks,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(doc, f, indent=2)

    log.info(
        "%s — %d pages, %s, %d chunks, date=%s",
        file_id, len(pages), mode, len(chunks), doc.get("meeting_date") or "NONE",
    )
    return {
        "skipped": False,
        "pages": len(pages),
        "chunks": len(chunks),
        "mode": mode,
        "dated": bool(doc.get("meeting_date")),
    }


def main():
    parser = argparse.ArgumentParser(description="Parse and chunk the raw PDF corpus.")
    parser.add_argument("--manifest", default=str(MANIFEST_PATH))
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    parser.add_argument("--force", action="store_true",
                        help="Reprocess documents even if output already exists.")
    parser.add_argument("--limit", type=int, default=None,
                        help="Only process the first N documents (smoke test).")
    args = parser.parse_args()

    records = load_manifest(Path(args.manifest))
    index = build_index(records)
    output_dir = Path(args.output_dir)

    if args.limit:
        records = records[: args.limit]

    stats = {"docs": 0, "skipped": 0, "pages": 0, "chunks": 0,
             "ocr": 0, "mixed": 0, "undated": 0}

    for record in records:
        result = process_document(record, index, output_dir, args.force)
        if result is None:
            continue
        if result["skipped"]:
            stats["skipped"] += 1
            continue
        stats["docs"] += 1
        stats["pages"] += result["pages"]
        stats["chunks"] += result["chunks"]
        if result["mode"] == "ocr":
            stats["ocr"] += 1
        elif result["mode"] == "mixed":
            stats["mixed"] += 1
        if not result["dated"]:
            stats["undated"] += 1

    log.info(
        "Done. %d processed (%d skipped) | %d pages | %d chunks | "
        "%d ocr, %d mixed | %d without a meeting_date",
        stats["docs"], stats["skipped"], stats["pages"], stats["chunks"],
        stats["ocr"], stats["mixed"], stats["undated"],
    )


if __name__ == "__main__":
    main()