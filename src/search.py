import sys
import numpy as np
from sentence_transformers import SentenceTransformer
from db import connect

MODEL_NAME = "all-MiniLM-L6-v2"
_model = None


def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def search(query: str, k: int = 5):
    """Embed the query and return the k nearest chunks by cosine distance."""
    q = get_model().encode(query, normalize_embeddings=True)

    with connect() as conn:
        rows = conn.execute(
            """
            SELECT chunk_id, meeting_date, doc_label, page_start, page_end,
                   text,
                   1 - (embedding <=> %s) AS similarity
            FROM chunks
            ORDER BY embedding <=> %s
            LIMIT %s
            """,
            (np.asarray(q), np.asarray(q), k),
        ).fetchall()
    return rows


def main():
    query = " ".join(sys.argv[1:]) or input("Query: ")
    for chunk_id, date, label, p0, p1, text, sim in search(query):
        pages = f"p.{p0}" if p0 == p1 else f"pp.{p0}-{p1}"
        print(f"\n[{sim:.3f}] {date} · {label} · {pages} · {chunk_id}")
        print(text[:300].strip().replace("\n", " ") + "…")


if __name__ == "__main__":
    main()