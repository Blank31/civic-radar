"""Ask the civic corpus using LangChain end to end."""

import argparse

from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_postgres import PGVector

from prompts import SYSTEM_PROMPT


CONNECTION = "postgresql+psycopg://civic:civic@localhost:5433/civic_radar"
COLLECTION = "civic_radar_langchain"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("-k", "--top-k", type=int, default=5)
    args = parser.parse_args()

    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        encode_kwargs={"normalize_embeddings": True},
    )
    store = PGVector(
        embeddings=embeddings,
        collection_name=COLLECTION,
        connection=CONNECTION,
        use_jsonb=True,
    )
    docs = store.similarity_search(args.question, k=args.top_k)

    context = "\n\n---\n\n".join(
        f"[S{i}] {d.metadata.get('meeting_title') or 'Unknown meeting'} — "
        f"{d.metadata.get('doc_label') or 'document'}, "
        f"{d.metadata.get('meeting_date') or 'undated'}, "
        f"pages {d.metadata.get('page_start')}–{d.metadata.get('page_end')}\n"
        f"{d.page_content}"
        for i, d in enumerate(docs, 1)
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            ("human", "Excerpts:\n\n{context}\n\nQuestion: {question}"),
        ]
    )
    model = ChatAnthropic(
        model="claude-haiku-4-5",
        max_tokens=600,
    )
    answer = (prompt | model).invoke(
        {"context": context, "question": args.question}
    )

    print(answer.content)
    print("\nSources:", [d.metadata.get("chunk_id") for d in docs])


if __name__ == "__main__":
    main()
