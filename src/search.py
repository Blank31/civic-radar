import sys
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer

from db import connect


MODEL_NAME = "all-MiniLM-L6-v2"
_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    """Load the embedding model once and reuse it."""
    global _model

    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)

    return _model


def search(query: str, k: int = 5) -> list[dict[str, Any]]:
    """Embed the query and return the k nearest chunks by cosine distance."""
    if not query.strip():
        raise ValueError("Query cannot be empty.")

    if k < 1:
        raise ValueError("k must be at least 1.")

    q = get_model().encode(
        query,
        normalize_embeddings=True,
    )

    embedding = np.asarray(q)

    with connect() as conn:
        rows = conn.execute(
            """
            SELECT
                chunk_id,
                meeting_date,
                meeting_title,
                doc_label,
                page_start,
                page_end,
                text,
                1 - (embedding <=> %s) AS similarity
            FROM chunks
            ORDER BY embedding <=> %s
            LIMIT %s
            """,
            (
                embedding,
                embedding,
                k,
            ),
        ).fetchall()

    return [dict(row) for row in rows]


def retrieve(question: str, k: int = 5) -> list[dict[str, Any]]:
    """Return retrieved chunks as dictionaries for ask.py."""
    return search(question, k)


def main() -> None:
    query = " ".join(sys.argv[1:]) or input("Query: ")

    for row in search(query):
        chunk_id = row["chunk_id"]
        meeting_date = row["meeting_date"]
        meeting_title = row["meeting_title"]
        doc_label = row["doc_label"]
        page_start = row["page_start"]
        page_end = row["page_end"]
        text = row["text"]
        similarity = row["similarity"]

        if page_start is None:
            pages = "pages unknown"
        elif page_end is None or page_start == page_end:
            pages = f"p.{page_start}"
        else:
            pages = f"pp.{page_start}-{page_end}"

        title = meeting_title or "Unknown meeting"
        label = doc_label or "document"

        print(
            f"\n[{similarity:.3f}] "
            f"{meeting_date} · "
            f"{title} · "
            f"{label} · "
            f"{pages} · "
            f"{chunk_id}"
        )

        preview = (text or "")[:300].strip().replace("\n", " ")
        print(preview + "…")


if __name__ == "__main__":
    main()