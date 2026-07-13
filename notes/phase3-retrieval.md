## Wins

- Query: "money for parks"
  - Relevant result ranked: 2
  - Why it worked: matched a chunk about recreation funding even though the phrase "money for parks" was absent.
  - Could the top 5 answer the question? Yes.

## Misses

- Query: "Ordinance 2024-17"
  - Correct result ranked: not in top 20
  - Likely reason: dense retrieval is weak at exact identifiers.

## Junk

- Query: "complaints about traffic"
  - Rank 3 was a repeated page header.
  - Likely reason: boilerplate was embedded as content.