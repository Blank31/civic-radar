# Phase 4 — Manual RAG vs LangChain

## Setup

Both implementations use:

- Model: `claude-haiku-4-5`
- Embedding model: `all-MiniLM-L6-v2`
- Retrieval count: `k = 5`
- Maximum output tokens: `600`
- The same `SYSTEM_PROMPT`
- The same underlying civic-document corpus

The storage and retrieval paths differ:

| Component | `ask.py` | `ask_lc.py` |
|---|---|---|
| Vector storage | Hand-built `chunks` table | Separate LangChain PGVector collection |
| Retrieval | Explicit pgvector SQL | `PGVector.similarity_search()` |
| Database rows | Psycopg dictionary rows | LangChain `Document` objects |
| Context construction | Custom `format_context()` | Metadata and `page_content` formatting |
| Model call | Anthropic Python SDK | `ChatAnthropic` |
| Source reporting | Custom logging | LangChain document metadata |

## Important limitation

The manual pipeline had a source-row plumbing bug during this comparison.

Its source log repeatedly showed:

```text
['chunk_id', 'chunk_id', 'chunk_id', 'chunk_id', 'chunk_id']
```

The generated answers also described the supplied excerpts as template placeholders rather than substantive text.

The likely cause is that the database connection now returns `dict_row` objects, while part of the manual retrieval code still unpacks rows positionally. Iterating over a dictionary returns its keys, such as `chunk_id` and `text`, rather than the corresponding values.

Therefore, differences in answer quality must not be interpreted as evidence that LangChain is inherently more intelligent. LangChain received valid document content; the manual pipeline did not.

---

# Question 1

**Question:** What did the council decide about parking meters in 2019?

## Manual result

The manual pipeline refused to answer.

It said that the excerpts appeared to be template placeholders and that the available documents covered 2026 rather than 2019.

**Reported sources:**

```text
['chunk_id', 'chunk_id', 'chunk_id', 'chunk_id', 'chunk_id']
```

## LangChain result

The LangChain pipeline also refused.

It identified substantive retrieved material about:

- Common Council meetings from May 2026
- Parking regulations
- ADA-compliant parking access requirements

It correctly stated that these sources did not contain evidence about a council decision made in 2019.

**Sources:**

- `undated_packet-2_16761:p836:c1`
- `undated_packet-3_16770:p70:c3`
- `undated_packet-3_16770:p308:c3`
- `undated_packet-3_16813:p449:c3`
- `undated_packet-3_16813:p323:c3`

## Comparison

Both systems refused correctly.

The important difference was that LangChain received and described real but insufficient evidence. The manual pipeline received malformed placeholder-like context.

**Likely cause:** manual dictionary-row handling bug.

---

# Question 2

**Question:** What tax increase did the council approve in 2018?

## Manual result

The manual pipeline refused because the apparent excerpts covered 2026 rather than 2018.

Its context was again malformed, so it could not inspect substantive retrieved evidence.

**Reported sources:**

```text
['chunk_id', 'chunk_id', 'chunk_id', 'chunk_id', 'chunk_id']
```

## LangChain result

The LangChain pipeline refused.

It found June 2026 material mentioning:

- Senate Enrolled Act 1
- Changes to Local Income Taxes made by the state

It correctly distinguished those references from the requested question and stated that the documents did not identify a tax increase approved by the council in 2018.

**Sources:**

- `undated_packet_16980:p3:c0`
- `undated_packet-3_16960:p5:c0`
- `undated_packet_16987:p26:c1`
- `undated_packet_16987:p19:c1`
- `undated_packet_16980:p3:c2`

## Comparison

Both systems refused.

LangChain produced a more useful explanation because it could describe the nearest related evidence and explain why it did not answer the question.

**Likely cause:** valid LangChain document content versus malformed manual context.

---

# Question 3

**Question:** Which company received the downtown monorail contract in 2020?

## Manual result

The manual pipeline refused.

It reported that the documents covered 2026 and that the supplied context did not contain substantive evidence about a monorail contract.

**Reported sources:**

```text
['chunk_id', 'chunk_id', 'chunk_id', 'chunk_id', 'chunk_id']
```

## LangChain result

The LangChain pipeline refused.

It identified real excerpts covering April through June 2026 and topics including:

- Zoning districts
- Pedestrian mall logistics
- Downtown strategies

It correctly stated that none of those sources contained information about a 2020 monorail contract or a company receiving one.

**Sources:**

- `undated_packet_16709:p42:c1`
- `undated_packet-2_16986:p24:c0`
- `undated_packet-2_16761:p647:c1`
- `undated_packet-3_16770:p515:c1`
- `undated_packet-3_16910:p69:c0`

## Comparison

Both systems refused without inventing a company.

LangChain gave a stronger evidence-based explanation because it could identify what the retrieved documents actually discussed.

**Likely cause:** source-content integrity, not a different generation model.

---

# Question 4

**Question:** What happened with the committee?

## Manual result

The manual answer was limited by the same malformed source-row path.

Because the query was vague, a useful answer required inspecting the actual retrieved committee documents, which the manual context did not reliably provide.

**Reported sources:**

```text
['chunk_id', 'chunk_id', 'chunk_id', 'chunk_id', 'chunk_id']
```

## LangChain result

The LangChain pipeline stated that the question was too broad to answer as a single event, but it summarized several retrieved committee actions from April through June 2026:

- The Special Committee on Council Processes annual report was presented on May 6, 2026. `[S1]`
- Interview Committee Team C held meetings concerning appointments to the Historic Preservation Commission and other boards. `[S2]`, `[S3]`, `[S4]`
- Interview Committee Team B met on June 3, 2026 regarding the Dr. MLK Birthday Celebration Commission. `[S5]`

It then asked for a more specific committee or action.

**Sources:**

- `undated_packet-2_16761:p5:c1`
- `undated_memorandum_16661:p1:c0`
- `undated_memorandum_16744:p1:c0`
- `undated_memorandum_16764:p1:c1`
- `undated_memorandum_16964:p1:c0`

## Comparison

This question shows the largest practical difference.

LangChain used the retrieved evidence to provide a cautious summary while acknowledging that the query was underspecified.

The manual pipeline could not do the same because its source values were malformed.

**Likely cause:** working document metadata and page content in the LangChain path.

---

# Question 5

**Question:** What decisions were made about housing?

## Manual result

The manual result cannot be treated as a reliable comparison because the source-row bug prevented valid excerpts and source IDs from reaching generation.

Any weakness in its answer is therefore primarily a pipeline-integrity failure rather than a retrieval or model-quality result.

## LangChain result

The LangChain pipeline returned a substantive housing-related answer.

It reported that the Plan Commission voted `8–0` to forward a planned unit development petition to the Common Council with a favorable recommendation.

The retrieved evidence described affordable-housing requirements including:

- At least 50% of total dwelling units available to buyers below 100% of Area Median Income
- At least 15% of total dwelling units permanently income-limited to households below 120% of Area Median Income

It also reported approval conditions including:

- Final plan approval for Block 8 remaining with the Plan Commission
- Final plan approval for other phases being delegated to staff

The answer separately noted a Residential Housing Program reference but correctly stated that the supplied excerpt did not provide a detailed decision about that program.

**Sources:**

- `undated_packet-2_16761:p846:c0`
- `undated_packet-2_16761:p821:c1`
- `undated_packet-2_16761:p779:c0`
- `undated_packet_16709:p34:c1`
- `undated_packet-3_16770:p5:c2`

## Comparison

LangChain produced a detailed cited answer because it received valid relevant excerpts.

The manual result is not a fair quality baseline until its source-row handling is corrected.

The claims in the LangChain answer still require citation auditing against the original PDFs before being accepted as fully faithful.

---

# Overall findings

## 1. Refusal behavior was consistent

For the three out-of-coverage questions, both implementations refused rather than inventing:

- A 2019 parking-meter decision
- A 2018 tax increase
- A 2020 monorail contractor

The common system prompt appears to have preserved conservative answer behavior.

## 2. LangChain exposed valid sources

LangChain returned real chunk IDs and substantive document text.

This made its answers:

- More specific
- Easier to audit
- Easier to diagnose
- Better able to explain why evidence was insufficient

## 3. The manual pipeline failed at context plumbing

The manual path did not fail because explicit SQL or the Anthropic SDK are inferior.

It failed because a change to dictionary database rows was not propagated correctly through retrieval and context formatting.

This is exactly the kind of failure hidden by framework abstractions but also made easier to avoid when using a maintained `Document` interface.

## 4. The comparison is not yet a fair retrieval benchmark

The two systems cannot be compared fairly for answer quality until `ask.py` receives actual row values.

At present:

- LangChain is processing real documents.
- The manual pipeline is processing dictionary keys or placeholder-like values.

After fixing the manual path, the five questions should be run again.

## 5. LangChain did not use a mysterious better prompt

Both scripts used the same `SYSTEM_PROMPT`.

The main observed differences came from:

- Source-row representation
- Context integrity
- Retrieval storage path
- Metadata handling
- Source reporting

The results should not be attributed to hidden LangChain intelligence.

---

# Judgment

LangChain compressed several implementation details into maintained abstractions:

- Embedding integration
- PGVector persistence
- Document metadata
- Similarity search
- Prompt composition
- Anthropic model invocation

That reduced custom plumbing and produced valid, auditable source documents.

The manual implementation remains valuable because it exposes every boundary directly:

- Corpus coverage
- Embedding
- Retrieval
- Database representation
- Context formatting
- Prompting
- Generation
- Citation logging

The manual source-row bug demonstrates the central lesson: debugging a framework-based or hand-built RAG system still requires understanding whether a failure came from retrieval, coverage, context construction, or generation.

Both scripts should remain in the repository. Their difference documents what the framework abstracts and what the engineer must still understand.
