from pathlib import Path
import argparse
import hashlib
import io
import json
import logging
import re

import fitz  # PyMuPDF
import pytesseract
from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]

CHUNK_SIZE = 1000
OVERLAP = 150
SEPARATORS = ["\n\n", "\n", ". ", " "]


logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)


def ocr_page(page) -> str:
    """Render a PDF page to an image and OCR it."""
    pix = page.get_pixmap(dpi=200)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    return pytesseract.image_to_string(img)


def extract_pages_smart(pdf_path: str | Path) -> tuple[list[str], str]:
    """
    Extract text from a PDF.

    If a page has almost no embedded text, OCR that page.

    Returns:
        pages: list of page texts
        mode: 'digital', 'ocr', or 'mixed'
    """
    texts = []
    ocr_count = 0

    with fitz.open(pdf_path) as doc:
        for page in doc:
            text = page.get_text("text")

            if len(text.strip()) < 30:
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


def clean_text(text: str) -> str:
    """Clean extracted PDF text."""
    text = text.replace("\u00ad", "")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_text(text: str, size: int = CHUNK_SIZE) -> list[str]:
    """Recursively split text at the most natural boundary that fits size."""
    if len(text) <= size:
        return [text] if text.strip() else []

    for sep in SEPARATORS:
        parts = text.split(sep)

        if len(parts) == 1:
            continue

        chunks = []
        current = ""

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
                    chunks.extend(split_text(part, size))
                    current = ""

        if current:
            chunks.append(current)

        return [c for c in chunks if c.strip()]

    return [text[i:i + size] for i in range(0, len(text), size)]


def add_overlap(chunks: list[str], overlap: int = OVERLAP) -> list[str]:
    """Prefix each chunk except the first with the tail of its predecessor."""
    out = []

    for i, chunk in enumerate(chunks):
        if i == 0:
            out.append(chunk)
        else:
            tail = chunks[i - 1][-overlap:]
            out.append(tail + " … " + chunk)

    return out


def read_manifest(manifest_path: Path) -> list[dict]:
    """Read a JSONL manifest file."""
    records = []

    with manifest_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if not line:
                continue

            records.append(json.loads(line))

    return records


def safe_file_id(record: dict) -> str:
    """
    Get a stable file_id from a manifest record.

    Prefer record['file_id']. If missing, derive one from the path.
    """
    if "file_id" in record and record["file_id"]:
        return str(record["file_id"])

    source = record.get("path") or record.get("source_path") or record.get("url")

    if not source:
        raise ValueError(f"Manifest record has no file_id or path: {record}")

    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]


def get_pdf_path(record: dict) -> Path:
    """
    Get the PDF path from a manifest record.

    This supports common manifest field names.
    """
    raw_path = (
        record.get("path")
        or record.get("pdf_path")
        or record.get("source_path")
        or record.get("local_path")
    )

    if not raw_path:
        raise ValueError(f"Manifest record has no path field: {record}")

    pdf_path = Path(raw_path)

    if not pdf_path.is_absolute():
        pdf_path = PROJECT_ROOT / pdf_path

    return pdf_path


def process_document(record: dict, output_dir: Path) -> dict:
    """
    Process one PDF manifest record and write one JSON output.

    Chunks are created page by page. This means chunks never span pages.
    That slightly reduces context quality at page boundaries, but greatly
    simplifies page citation metadata.
    """
    file_id = safe_file_id(record)
    pdf_path = get_pdf_path(record)
    output_path = output_dir / f"{file_id}.json"

    if output_path.exists():
        logging.info("Skipping already processed file_id=%s", file_id)
        return {
            "status": "skipped",
            "file_id": file_id,
            "pages": 0,
            "chunks": 0,
            "needed_ocr": False,
        }

    if not pdf_path.exists():
        logging.warning("Missing PDF for file_id=%s path=%s", file_id, pdf_path)
        return {
            "status": "missing",
            "file_id": file_id,
            "pages": 0,
            "chunks": 0,
            "needed_ocr": False,
        }

    pages, mode = extract_pages_smart(pdf_path)

    all_chunks = []

    for page_index, page_text in enumerate(pages, start=1):
        cleaned = clean_text(page_text)
        page_chunks = split_text(cleaned)
        page_chunks = add_overlap(page_chunks)

        for chunk_index, chunk_text in enumerate(page_chunks):
            chunk_id = f"{file_id}:p{page_index}:c{chunk_index}"

            all_chunks.append(
                {
                    "chunk_id": chunk_id,
                    "text": chunk_text,
                    "page_start": page_index,
                    "page_end": page_index,
                }
            )

    output = {
        "file_id": file_id,
        "source_path": str(pdf_path.relative_to(PROJECT_ROOT))
        if pdf_path.is_relative_to(PROJECT_ROOT)
        else str(pdf_path),
        "pages": len(pages),
        "extraction_mode": mode,
        "chunks": all_chunks,
    }

    output_dir.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    logging.info(
        "Processed file_id=%s pages=%s mode=%s chunks=%s",
        file_id,
        len(pages),
        mode,
        len(all_chunks),
    )

    return {
        "status": "processed",
        "file_id": file_id,
        "pages": len(pages),
        "chunks": len(all_chunks),
        "needed_ocr": mode in {"ocr", "mixed"},
    }


def process_manifest(manifest_path: Path, output_dir: Path) -> None:
    """Process all PDFs listed in a manifest.jsonl file."""
    records = read_manifest(manifest_path)

    total_documents = 0
    total_pages = 0
    total_chunks = 0
    total_ocr_docs = 0
    total_skipped = 0
    total_missing = 0

    for record in records:
        result = process_document(record, output_dir)

        if result["status"] == "processed":
            total_documents += 1
            total_pages += result["pages"]
            total_chunks += result["chunks"]

            if result["needed_ocr"]:
                total_ocr_docs += 1

        elif result["status"] == "skipped":
            total_skipped += 1

        elif result["status"] == "missing":
            total_missing += 1

    print()
    print("==== Corpus totals ====")
    print(f"New documents processed: {total_documents}")
    print(f"Skipped existing:        {total_skipped}")
    print(f"Missing PDFs:            {total_missing}")
    print(f"Pages processed:         {total_pages}")
    print(f"Chunks written:          {total_chunks}")
    print(f"Documents needing OCR:   {total_ocr_docs}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract, clean, chunk, and write processed PDF JSON files."
    )

    parser.add_argument(
        "--manifest",
        default="data/raw/bloomington-council/2026/manifest.jsonl",
        help="Path to manifest.jsonl",
    )

    parser.add_argument(
        "--output-dir",
        default="data/processed/bloomington-council/2026",
        help="Directory for processed JSON files",
    )

    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    output_dir = Path(args.output_dir)

    if not manifest_path.is_absolute():
        manifest_path = PROJECT_ROOT / manifest_path

    if not output_dir.is_absolute():
        output_dir = PROJECT_ROOT / output_dir

    process_manifest(manifest_path, output_dir)


if __name__ == "__main__":
    main()