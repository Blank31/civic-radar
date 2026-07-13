"""
Phase 3 — Embed every processed chunk and load it into Postgres/pgvector.

Reads:  data/processed/**/*.json   (output of Phase 2)
Writes: the `chunks` table in the civic_radar database

Idempotent: chunk_id is the primary key, so re-running inserts 0 new rows.
"""

import argparse
import json
import logging
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

from db import connect

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("load")

MODEL_NAME = "all-MiniLM-L6-v2"
PROCESSED_DIR = "data/processed"
BATCH_SIZE = 64

INSERT_SQL = """
    INSERT INTO chunks (chunk_id, file_id, meeting_date, meeting_title,
                        doc_label, page_start, page_end, text, embedding)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (chunk_id) DO NOTHING
"""


def find_documents(processed_dir: str) -> list[Path]:
    """All processed JSON files, at any depth under processed_dir.

    rglob (recursive glob) means this works whether the files sit directly in
    data/processed/ or under a per-source subfolder like
    data/processed/bloomington-council/ — and keeps working when a second
    source is added later.
    """
    paths = sorted(Path(processed_dir).rglob("*.json"))
    if not paths:
        # A stage that finds zero inputs must shout, not shrug. A silent
        # empty-set "success" is one of the quietest killers in data work.
        raise SystemExit(
            f"No JSON files found under {processed_dir}/ — did Phase 2 run?"
        )
    return paths


def read_document(path: Path):
    """Return (doc, chunks) for one processed file, or (None, None) if unusable."""
    try:
        with open(path) as f:
            doc = json.load(f)
    except json.JSONDecodeError as e:
        log.warning("Skipping %s — invalid JSON: %s", path, e)
        return None, None

    chunks = doc.get("chunks") or []
    if not chunks:
        log.warning("Skipping %s — no chunks", path)
        return None, None
    return doc, chunks


def main():
    parser = argparse.ArgumentParser(description="Embed processed chunks into pgvector.")
    parser.add_argument("--processed-dir", default=PROCESSED_DIR)
    parser.add_argument("--model", default=MODEL_NAME)
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Only process the first N documents (useful for a quick smoke test).",
    )
    args = parser.parse_args()

    paths = find_documents(args.processed_dir)
    if args.limit:
        paths = paths[: args.limit]
    log.info("Found %d processed documents under %s", len(paths), args.processed_dir)

    log.info("Loading embedding model %s ...", args.model)
    model = SentenceTransformer(args.model)

    # Guard against the model/schema mismatch that silently corrupts everything:
    # the `embedding vector(384)` column and the model's output MUST agree.
    dim = model.get_sentence_embedding_dimension()
    log.info("Model output dimension: %d", dim)
    if dim != 384:
        raise SystemExit(
            f"Model outputs {dim}-d vectors but the chunks table declares vector(384). "
            "Change the model or ALTER the column — they must match."
        )

    inserted = skipped = docs_done = 0

    with connect() as conn:
        for path in paths:
            doc, chunks = read_document(path)
            if doc is None:
                continue

            texts = [c["text"] for c in chunks]

            # Batch-encode the whole document at once — far faster than one
            # call per chunk. Normalized so pgvector's cosine operator behaves.
            embeddings = model.encode(
                texts,
                batch_size=args.batch_size,
                normalize_embeddings=True,
                show_progress_bar=False,
            )

            with conn.cursor() as cur:
                for chunk, emb in zip(chunks, embeddings):
                    cur.execute(
                        INSERT_SQL,
                        (
                            chunk["chunk_id"],
                            doc["file_id"],
                            doc.get("meeting_date"),
                            doc.get("meeting_title"),
                            doc.get("doc_label"),
                            chunk.get("page_start"),
                            chunk.get("page_end"),
                            chunk["text"],
                            np.asarray(emb),
                        ),
                    )
                    if cur.rowcount == 1:
                        inserted += 1
                    else:
                        skipped += 1

            # Commit per document: a crash mid-run keeps every completed doc.
            conn.commit()
            docs_done += 1
            log.info(
                "[%d/%d] file_id=%s — %d chunks",
                docs_done, len(paths), doc["file_id"], len(chunks),
            )

    log.info(
        "Done. %d documents | %d new chunks inserted | %d already present.",
        docs_done, inserted, skipped,
    )


if __name__ == "__main__":
    main()