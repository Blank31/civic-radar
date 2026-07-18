"""Ask a question of the civic corpus.

Retrieval comes from the Phase 3 semantic search.
Answer generation is performed through the Anthropic API.
"""

import argparse
import logging
import os
import sys
from typing import Any

import anthropic

from prompts import SYSTEM_PROMPT
from search import retrieve


def format_context(rows: list[dict[str, Any]]) -> str:
    """Turn retrieved rows into tagged, metadata-rich excerpts."""
    blocks: list[str] = []

    for i, row in enumerate(rows, start=1):
        meeting_date = row.get("meeting_date")

        if meeting_date is None:
            date = "undated"
        elif hasattr(meeting_date, "isoformat"):
            date = meeting_date.isoformat()
        else:
            date = str(meeting_date)

        meeting_title = row.get("meeting_title") or "Unknown meeting"
        doc_label = row.get("doc_label") or "document"

        page_start = row.get("page_start")
        page_end = row.get("page_end")

        if page_start is None:
            pages = "pages unknown"
        elif page_end is None or page_start == page_end:
            pages = f"page {page_start}"
        else:
            pages = f"pages {page_start}–{page_end}"

        text = row.get("text") or ""

        header = (
            f"[S{i}] {meeting_title} — "
            f"{doc_label}, {date}, {pages}"
        )

        blocks.append(f"{header}\n{text}")

    return "\n\n---\n\n".join(blocks)


def ask(
    question: str,
    k: int = 5,
    model: str = "claude-haiku-4-5",
    max_tokens: int = 600,
) -> str:
    """Retrieve relevant excerpts and ask Claude to answer the question."""
    if not question.strip():
        raise ValueError("Question cannot be empty.")

    if k < 1:
        raise ValueError("k must be at least 1.")

    if max_tokens < 1:
        raise ValueError("max_tokens must be at least 1.")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not loaded. "
            "Run: set -a; source .env; set +a"
        )

    rows = retrieve(question, k)

    if not rows:
        return "No relevant excerpts were found in the civic corpus."

    context = format_context(rows)

    user_message = (
        "Excerpts:\n\n"
        f"{context}\n\n"
        f"Question: {question}"
    )

    client = anthropic.Anthropic()

    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": user_message,
            }
        ],
    )

    answer_parts = [
        block.text
        for block in message.content
        if getattr(block, "type", None) == "text"
    ]

    answer = "\n".join(answer_parts)

    logging.info(
        "tokens: in=%d out=%d",
        message.usage.input_tokens,
        message.usage.output_tokens,
    )
    logging.info(
        "sources sent: %s",
        [row.get("chunk_id") for row in rows],
    )
    logging.info(
        "stop reason: %s",
        message.stop_reason,
    )

    if message.stop_reason == "max_tokens":
        logging.warning(
            "The answer reached the max_tokens limit and may be incomplete."
        )

    return answer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ask a question about the civic-document corpus."
    )

    parser.add_argument(
        "question",
        nargs="+",
        help="Natural-language question to ask.",
    )

    parser.add_argument(
        "-k",
        "--top-k",
        type=int,
        default=5,
        help="Number of source chunks to retrieve; default: 5.",
    )

    parser.add_argument(
        "--model",
        default="claude-haiku-4-5",
        help="Anthropic model name.",
    )

    parser.add_argument(
        "--max-tokens",
        type=int,
        default=600,
        help="Maximum number of output tokens; default: 600.",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show token, source, and stop-reason information.",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    question = " ".join(args.question)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
    )

    try:
        answer = ask(
            question=question,
            k=args.top_k,
            model=args.model,
            max_tokens=args.max_tokens,
        )
    except Exception as exc:
        logging.error("%s", exc)
        return 1

    print(answer)
    return 0


if __name__ == "__main__":
    sys.exit(main())
