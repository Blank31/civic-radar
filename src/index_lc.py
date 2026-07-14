"""Copy civic chunks into LangChain's separate PGVector collection."""

from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_postgres import PGVector

from db import connect


LC_CONNECTION = (
    "postgresql+psycopg://civic:civic@localhost:5433/civic_radar"
)
LC_COLLECTION = "civic_radar_langchain"
BATCH_SIZE = 128


def main() -> None:
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        encode_kwargs={
            "normalize_embeddings": True,
            "batch_size": 32,
        },
    )

    store = PGVector(
        embeddings=embeddings,
        collection_name=LC_COLLECTION,
        connection=LC_CONNECTION,
        use_jsonb=True,
    )

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
                text
            FROM chunks
            WHERE text IS NOT NULL
              AND text <> ''
            ORDER BY chunk_id
            """
        ).fetchall()

    total = len(rows)
    print(f"Found {total} source chunks.")

    for start in range(0, total, BATCH_SIZE):
        batch_rows = rows[start:start + BATCH_SIZE]

        documents = [
            Document(
                page_content=row["text"],
                metadata={
                    "chunk_id": str(row["chunk_id"]),
                    "meeting_date": (
                        row["meeting_date"].isoformat()
                        if row["meeting_date"]
                        else None
                    ),
                    "meeting_title": row["meeting_title"],
                    "doc_label": row["doc_label"],
                    "page_start": row["page_start"],
                    "page_end": row["page_end"],
                },
            )
            for row in batch_rows
        ]

        ids = [doc.metadata["chunk_id"] for doc in documents]

        store.add_documents(
            documents=documents,
            ids=ids,
        )

        completed = min(start + len(documents), total)
        print(f"Indexed {completed}/{total}")

    print(
        f"Finished indexing {total} chunks into "
        f"{LC_COLLECTION!r}."
    )


if __name__ == "__main__":
    main()
