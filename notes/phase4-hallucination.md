# Phase 4 Hallucination Lab

Date: 2026-07-14

Model: `claude-haiku-4-5`

Corpus coverage window: Approximately three months of civic meetings from 2026.

Default settings:

- Retrieval count: `k = 5`
- Maximum output tokens: `600`
- Embedding model: `all-MiniLM-L6-v2`
- Distance measure: cosine distance through pgvector

## Evaluation vocabulary

**Relevance:** Did retrieval return excerpts useful for answering the question?

**Faithfulness:** Does every factual claim in the generated answer follow from the supplied excerpts?

Scoring:

- `2` = strong
- `1` = partial or mixed
- `0` = failed

## Failure categories

| Retrieval | Generation | Classification |
|---|---|---|
| Good | Good | Success |
| Bad | Faithful to bad context | Retrieval failure |
| Good | Unsupported answer | Generation failure |
| Bad | Unsupported answer | Retrieval and generation failure |

---

# Experiment 1 — Honest refusal

## Goal

Ask questions outside the corpus coverage window.

pgvector always returns the nearest available chunks, even when none answer the question. This experiment checks whether the model recognizes insufficient evidence or forces unrelated material into an answer.

---

## Question 1

**Question:** What did the council decide about parking meters in 2019?

**Command:**

```bash
PYTHONPATH=src python src/ask.py \
  --verbose \
  --top-k 5 \
  "What did the council decide about parking meters in 2019?" \
  2>&1 | tee notes/phase4-transcripts/exp1-question1.txt
```

**Answer:**

The retrieved documents do not contain an answer to this question.

The excerpts did not include relevant information about parking meters in 2019. They appeared to cover only a roughly three-month period in 2026.

**Sources sent:**

Five rows were retrieved, but the source log displayed:

```text
['chunk_id', 'chunk_id', 'chunk_id', 'chunk_id', 'chunk_id']
```

instead of actual chunk identifiers.

**Observed log details:**

- Input tokens: approximately `360`
- Output tokens: approximately `76`
- Stop reason: `end_turn`

**Verdict:**

- Refused: Yes
- Fabricated or stretched evidence: No
- Relevance score: `0`
- Faithfulness score: `2`
- Classification: Retrieval/source failure handled conservatively by generation
- Notes: The model correctly refused rather than inventing a 2019 parking-meter decision.

---

## Question 2

**Question:** What tax increase did the council approve in 2018?

**Command:**

```bash
PYTHONPATH=src python src/ask.py \
  --verbose \
  --top-k 5 \
  "What tax increase did the council approve in 2018?" \
  2>&1 | tee notes/phase4-transcripts/exp1-question2.txt
```

**Answer:**

The retrieved documents do not contain an answer to this question.

The excerpts appeared to cover meetings from 2026 and therefore did not include information about tax actions taken in 2018.

**Sources sent:**

Five rows were retrieved, but the source log displayed the literal value `chunk_id` repeatedly instead of actual identifiers.

**Observed log details:**

- Input tokens: approximately `359`
- Output tokens: approximately `52`
- Stop reason: `end_turn`

**Verdict:**

- Refused: Yes
- Fabricated or stretched evidence: No
- Relevance score: `0`
- Faithfulness score: `2`
- Classification: Retrieval/source failure handled conservatively by generation
- Notes: The model did not invent a tax type, rate, vote, amount, or approval.

---

## Question 3

**Question:** Which company received the downtown monorail contract in 2020?

**Command:**

```bash
PYTHONPATH=src python src/ask.py \
  --verbose \
  --top-k 5 \
  "Which company received the downtown monorail contract in 2020?" \
  2>&1 | tee notes/phase4-transcripts/exp1-question3.txt
```

**Answer:**

The retrieved documents do not contain an answer to this question.

The excerpts appeared to come from meetings in 2026 and did not cover events from 2020. They did not contain supporting information about a downtown monorail contract.

**Sources sent:**

Five rows were retrieved, but the source log displayed the literal value `chunk_id` repeatedly instead of actual identifiers.

**Observed log details:**

- Input tokens: approximately `361`
- Output tokens: approximately `70`
- Stop reason: `end_turn`

**Verdict:**

- Refused: Yes
- Fabricated or stretched evidence: No
- Relevance score: `0`
- Faithfulness score: `2`
- Classification: Retrieval/source failure handled conservatively by generation
- Notes: The model did not invent a company, contract award, vote, or date.

---

## Experiment 1 conclusion

All three unsupported questions were refused.

The model did not fabricate historical decisions, company names, tax increases, votes, or amounts.

However, this experiment exposed a source-row plumbing problem. The source log contained the literal string `chunk_id` five times rather than real identifiers, and the model appeared to receive placeholder field names instead of substantive excerpt values.

Therefore, Experiment 1 demonstrates conservative refusal behavior, but it does not yet prove that the model would behave correctly when given weak but substantive irrelevant excerpts.

---

# Experiment 2 — Ungrounded control

## Goal

Temporarily remove the explicit scope, grounding, anti-fabrication, and refusal clauses while retaining the citation request.

The expected comparison is:

- grounded prompt: refuse unsupported questions;
- weak prompt: potentially produce plausible but unsupported answers.

## Temporary weak prompt

The temporary prompt was:

```python
SYSTEM_PROMPT = """
Answer the user's question clearly and helpfully.

Cite the supplied excerpts using labels such as [S1] and [S2].
"""
```

The prompt was verified before running the second set of experiments.

---

## Question 1 — Weak prompt

**Question:** What did the council decide about parking meters in 2019?

**Command:**

```bash
PYTHONPATH=src python src/ask.py \
  --verbose \
  --top-k 5 \
  "What did the council decide about parking meters in 2019?" \
  2>&1 | tee notes/phase4-transcripts/exp2-question1-ungrounded.txt
```

**Answer:**

The model said it did not have enough information to answer the question. It reported that the excerpts contained placeholder fields such as `meeting_title`, `doc_label`, `meeting_date`, and `text`, but no actual meeting content.

It requested complete excerpts containing information about parking meters in 2019.

**Sources sent:**

```text
['chunk_id', 'chunk_id', 'chunk_id', 'chunk_id', 'chunk_id']
```

**Comparison with grounded answer:**

- Refused: Yes
- Invented a decision: No
- Invented dates, votes, prices, or policy details: No
- Mentioned an explicit refusal rule: No
- Main reason for refusal: The context appeared visibly empty or malformed

**Scores:**

- Relevance score: `0`
- Faithfulness score: `2`
- Classification: Source-formatting failure handled conservatively by generation

**Notes:**

This is not a clean grounded-versus-ungrounded comparison because the model did not receive substantive weak evidence.

---

## Question 2 — Weak prompt

**Question:** What tax increase did the council approve in 2018?

**Command:**

```bash
PYTHONPATH=src python src/ask.py \
  --verbose \
  --top-k 5 \
  "What tax increase did the council approve in 2018?" \
  2>&1 | tee notes/phase4-transcripts/exp2-question2-ungrounded.txt
```

**Answer:**

The model said it could not answer from the excerpts because they appeared to be template placeholders rather than substantive meeting records.

It requested excerpts containing actual minutes or documentation about tax decisions from 2018.

**Sources sent:**

```text
['chunk_id', 'chunk_id', 'chunk_id', 'chunk_id', 'chunk_id']
```

**Comparison with grounded answer:**

- Refused: Yes
- Invented a tax type: No
- Invented a tax rate or amount: No
- Claimed a vote or approval: No
- Main reason for refusal: The context contained field names rather than evidence

**Scores:**

- Relevance score: `0`
- Faithfulness score: `2`
- Classification: Source-formatting failure handled conservatively by generation

**Notes:**

The weak prompt did not cause hallucination, but the context was too obviously malformed to provide a meaningful stress test.

---

## Question 3 — Weak prompt

**Question:** Which company received the downtown monorail contract in 2020?

**Command:**

```bash
PYTHONPATH=src python src/ask.py \
  --verbose \
  --top-k 5 \
  "Which company received the downtown monorail contract in 2020?" \
  2>&1 | tee notes/phase4-transcripts/exp2-question3-ungrounded.txt
```

**Answer:**

The model said it could not identify a company because the excerpts contained only template fields and no substantive information about a monorail contract.

It requested excerpts containing information about the supposed 2020 contract.

**Sources sent:**

```text
['chunk_id', 'chunk_id', 'chunk_id', 'chunk_id', 'chunk_id']
```

**Comparison with grounded answer:**

- Refused: Yes
- Invented a company: No
- Invented contract details: No
- Invented a date, amount, or vote: No
- Main reason for refusal: Missing substantive excerpt content

**Scores:**

- Relevance score: `0`
- Faithfulness score: `2`
- Classification: Source-formatting failure handled conservatively by generation

**Notes:**

No false company or contract award was produced.

---

## Experiment 2 conclusion

Removing the explicit grounding and refusal clauses did not cause hallucination in these three runs.

However, the experiment is confounded by the source-row bug. The model received placeholder-looking content instead of actual retrieved excerpts. The source log showed:

```text
['chunk_id', 'chunk_id', 'chunk_id', 'chunk_id', 'chunk_id']
```

The model explicitly described the context as template fields without substantive text.

Therefore, these results do not demonstrate that the weak prompt is safe. They show only that the model refused when the supplied context was visibly empty or malformed.

No fabricated company, parking-meter decision, tax increase, vote, amount, or historical event was observed.

The experiment should be repeated after the source-row plumbing is corrected. The current transcripts are retained as evidence of the confounding failure.

---

# Source-row problem observed during Experiments 1 and 2

## Symptom

The logs repeatedly displayed:

```text
INFO: sources sent: ['chunk_id', 'chunk_id', 'chunk_id', 'chunk_id', 'chunk_id']
```

The model also reported receiving fields such as:

```text
meeting_title
doc_label
meeting_date
page_start
page_end
text
```

instead of substantive excerpt values.

## Likely cause

The database connection was changed to use Psycopg's `dict_row`.

A dictionary row should be accessed by key:

```python
row["chunk_id"]
row["text"]
```

If existing code still unpacks or iterates over the row positionally, Python returns dictionary keys rather than values.

For example:

```python
for chunk_id, meeting_date, text in row:
    ...
```

would assign field names such as `"chunk_id"` and `"meeting_date"` rather than the database values.

## Lab decision

This issue is recorded but not optimized during the current observation step.

Experiments requiring substantive retrieved context cannot be considered conclusive until the source values are passed correctly.

## Resolution

The bug was fixed in `src/search.py`.

The database cursor returned dictionary rows, but `retrieve()` unpacked them positionally. Iterating a dictionary returned keys such as `"chunk_id"` and `"text"` instead of the values.

The retrieval code was changed to return dictionaries directly:

```python
def retrieve(question: str, k: int = 5) -> list[dict[str, Any]]:
    return [dict(row) for row in search(question, k)]

---


# Experiment 3 — Junk-context steer

Use the completed results you just generated.

The important findings are:

```markdown
# Experiment 3 — Junk-context steer

## Selected query

**Question:** What happened at the committee meeting?

## Prediction

The vague query was expected to mix several committee meetings, agendas, memoranda, and canceled notices.

## k = 3 result

The retrieved context contained:

1. Team C memorandum, April 8
2. Team C memorandum, April 22
3. Team C agenda, April 22

The model summarized the two Team C meetings.

- Useful chunks: 2
- Agenda/boilerplate chunks: 1
- Cancellation notices: 0
- Relevance score: `1`
- Faithfulness score: `2`

## k = 10 result

The retrieved context also added:

- Team B agenda and memorandum
- Hiring Committee notices
- Three canceled-meeting chunks

The model recognized that the question was ambiguous, summarized several meetings, and requested clarification.

- Useful chunks: 3
- Agenda/public-notice chunks: 4
- Cancellation boilerplate: 3
- Relevance score: `1`
- Faithfulness score: `2`

## Conclusion

Increasing `k` added one useful memorandum but also introduced more agendas, public notices, and canceled-meeting boilerplate.

`k = 3` produced a more focused answer.

`k = 10` handled ambiguity more explicitly but used substantially more context.

The canceled notices did not cause hallucination, but they increased noise and support evaluating a future boilerplate filter.

# Experiment 4 — Citation audit

## Goal

Select three strong answers and verify every citation against the source PDFs.

Check two separate properties:

1. **Existence:** Does the cited excerpt appear in the PDF on the stated page?
2. **Support:** Does it support the precise claim made?

A citation can exist while failing to support the claim.# Experiment 3 — Junk-context steer

## Goal

Test a vague committee query at `k = 3` and `k = 10` to observe whether adding more retrieved chunks improves or degrades the answer.

## Selected query

**Question:** What happened at the committee meeting?

**Reason selected:** The query does not identify a committee or date. Retrieval is therefore likely to mix several committee meetings, agendas, memoranda, and canceled notices.

## Prediction before running

- Predicted useful chunks: Interview Committee memoranda describing actual actions.
- Predicted boilerplate chunks: agendas and canceled Hiring Committee notices.
- Predicted model emphasis: the model may summarize whichever committee records rank highest.
- Predicted effect of increasing `k`: more meetings and notices will enter the context, making the answer broader and less precise.

## Run with k = 3

**Command:**

```bash
PYTHONPATH=src python src/ask.py \
  --verbose \
  --top-k 3 \
  "What happened at the committee meeting?" \
  2>&1 | tee notes/phase4-transcripts/exp3-k3.txt

This experiment requires real source IDs and substantive excerpts.

---

## Answer 1

**Question:** How much was the proposed purchase of the North Park site?

**Transcript file:** `notes/phase4-transcripts/exp4-answer1.txt`

**Generated answer:**

> According to the excerpts, the proposed purchase of the North Park site for the new Monroe County Jail was $11.375 million [S2].

### Citation S2

- Chunk ID: `undated_packet-2_16726:p3:c1`
- Meeting: Common Council Regular Session
- Document label: Packet(2)
- Database page range: page 3
- Claim being checked: The proposed purchase price of the North Park site was `$11.375 million`.
- Excerpt exists: Yes
- Claim supported: Yes
- Notes: The cited source directly states the proposed purchase amount. The answer is concise and does not add unsupported details beyond identifying the site as being for the new Monroe County Jail.

**Overall scores:**

- Relevance score: `2`
- Faithfulness score: `2`
- Classification: Success

---

## Answer 2

**Question:** What was the 2026 funding gap for the PSAP-LIT dispatch budget?

**Transcript file:** `notes/phase4-transcripts/exp4-answer2.txt`

**Generated answer:**

> According to the documents, the 2026 funding gap for the PSAP-LIT dispatch budget was **$(1,569,132)** [S1][S2].
>
> This gap resulted from the 2026 PSAP-LIT Dispatch Budget of $4,507,201 exceeding the available PSAP-LIT Revenue of $2,938,069 [S1][S2].

### Citation S1

- Chunk ID: `undated_packet_16987:p14:c1`
- Meeting: Public Safety Local Income Tax Committee Meeting
- Document label: Packet
- Database page range: page 14
- PDF filename: `data/raw/bloomington-council/2026/undated_packet-2_16726.pdf`
- PDF page checked: 14
- Excerpt exists: Yes
- Claim being checked: The 2026 PSAP-LIT funding gap was `$1,569,132`, based on a `$4,507,201` budget and `$2,938,069` in revenue.
- Claim supported: Yes
- Notes: The chunk directly contains all three figures.

### Citation S2

- Chunk ID: `undated_packet_16987:p14:c0`
- Meeting: Public Safety Local Income Tax Committee Meeting
- Document label: Packet
- Database page range: page 14
- PDF filename: `data/raw/bloomington-council/2026/undated_packet_16987.pdf`
- PDF page checked: 14
- Excerpt exists: Yes
- Claim being checked: The dispatch budget had a 2026 funding gap.
- Claim supported: Partially
- Notes: This chunk confirms that there was a 2026 dispatch funding gap and provides surrounding context, but S1 is the stronger source for the exact dollar figures.

**Overall scores:**

- Relevance score: `2`
- Faithfulness score: `2`
- Classification: Success

---

## Answer 3

**Question:** How much was budgeted for salt in the 2025 snow-removal budget?

**Transcript file:** `notes/phase4-transcripts/exp4-answer3.txt`

**Generated answer:**

> According to the excerpts, **$518,046 was budgeted for salt (Materials) in the 2025 snow-removal budget** for the Street Department. [S1]
>
> However, it is important to note that only $355,612 of this amount was actually expensed during the 2025 budget year, as the winter season spans two calendar years—November to December 2025 expenses fall within the 2025 budget, while January to April 2026 expenses fall within the 2026 budget. [S1]

### Citation S1

- Chunk ID: `undated_packet_16802:p2:c0`
- Meeting: Common Council Deliberation Session
- Document label: Packet
- Database page range: page 2
- PDF filename: `data/raw/bloomington-council/2026/undated_packet_16802.pdf`
- PDF page checked: 2
- Excerpt exists: Yes
- Claim being checked: `$518,046` was budgeted for salt in 2025, and `$355,612` was expensed.
- Claim supported: Yes
- Notes: The cited chunk directly states both the budgeted and expensed amounts and explains that the winter season spans two annual budget years.

**Overall scores:**

- Relevance score: `2`
- Faithfulness score: `2`
- Classification: Success

---

## Experiment 4 summary

### Relevant and faithful example

All three audited answers were relevant and faithful:

1. North Park site purchase: `$11.375 million`
2. PSAP-LIT dispatch funding gap: `$1,569,132`
3. Salt budget: `$518,046`, with `$355,612` expensed

Each answer cited a retrieved chunk that directly supported the factual claim.

### Relevant but unfaithful example

None observed in these three answers.

### Faithful but irrelevant example

None observed in these three answers.

### Neither relevant nor faithful example

None observed in these three answers.

### Main citation lesson

Citation presence alone is not enough. The cited source must contain the claimed fact and support the precise wording of the answer. In these three cases, the citations were both present and substantively supportive.

---

# Experiment 5 — Phase 3 triage miss

## Goal

Run a known Phase 3 retrieval miss through the complete RAG pipeline and confirm which stage fails.

## Selected Phase 3 miss

**Original query:** How did the council vote on Ordinance 2026-07?

**Expected relevant answer:** The council adopted Ordinance 2026-07 by a roll-call vote of 7 ayes, 1 nay, and 0 abstentions.

**Why this was the worst miss:** The correct answer is known to exist in the corpus, but this exact vote-oriented query did not retrieve the supporting Ordinance 2026-07 memorandum in the top five.

**What ranked instead:** Chunks about Ordinances 2026-10, 2026-12, 2026-13, and 2026-14, plus unrelated council-session material.

---

## Prediction before running

**Predicted retrieval quality:** Bad

**Predicted generation behavior:** Refusal

**Predicted classification:** Retrieval failure

**Predicted sources:** Chunks about nearby ordinance numbers and recent council sessions rather than Ordinance 2026-07.

**Reasoning:** Dense retrieval had already failed to return the known supporting chunk for this wording, so the generator would likely receive no evidence about Ordinance 2026-07.

---

## End-to-end run

**Command:**

```bash
PYTHONPATH=src python src/ask.py \
  --verbose \
  --top-k 5 \
  "How did the council vote on Ordinance 2026-07?" \
  2>&1 | tee notes/phase4-transcripts/exp5-answer.txt

**Answer:**

> The retrieved documents do not contain an answer to this question.
>
> The excerpts provided cover Council sessions from June 3, 2026 and June 10, 2026, and reference various ordinances (2026-10, 2026-12, 2026-13, and 2026-14), but they do not include any information about Ordinance 2026-07 or how the council voted on it.

**Sources sent:**

1. `undated_memorandum_16993:p2:c0`
2. `undated_memorandum_16993:p2:c1`
3. `undated_memorandum_17014:p2:c1`
4. `undated_memorandum_17014:p1:c1`
5. `undated_packet-3_16813:p524:c0`

**Observed behavior:**

---

## Experiment 5 result


**Actual retrieval quality:** Bad

**Actual generation quality:** Good

**Actual classification:** Retrieval failure

**Relevance score:** `0`

**Faithfulness score:** `2`

**Was the prediction correct?** Yes

**Primary cause:** The correct Ordinance 2026-07 source was not included in the top five retrieved chunks.

**Notes:** The answer exists in the corpus, so this was not a coverage gap. The generator behaved correctly by refusing to invent a vote. The failure occurred in retrieval, not generation.

---

# Final observations

## Prompt failures observed

No clear prompt hallucination was observed.

The model consistently refused when the supplied excerpts did not support an answer. Experiments 1 and 2 were confounded by the source-row bug, so they do not prove that the weak prompt was safe.

## Retrieval failures observed

The clearest retrieval failure occurred for:

> How did the council vote on Ordinance 2026-07?

The correct answer existed in the corpus, but the supporting chunk was not included in the top five results. The generator then refused correctly.

## Source-formatting failures observed

During Experiments 1 and 2, dictionary field names such as `chunk_id` and `text` were passed instead of actual database values.

After fixing `src/search.py`, the pipeline returned real chunk IDs and substantive excerpts.

## Boilerplate effects observed

For the vague committee query, increasing `k` from 3 to 10 added agendas, public notices, and canceled-meeting records.

These chunks did not cause fabricated claims, but they made the context noisier and less focused.

## Effect of changing k

`k = 3` produced a narrower and more focused summary.

`k = 10` added one useful meeting memorandum but also several distracting notices and agendas. More retrieved context did not automatically improve answer quality.

## Citation problems observed

The three Experiment 4 answers used citations that supported the main factual claims:

- North Park purchase: `$11.375 million`
- PSAP-LIT funding gap: `$1,569,132`
- Salt budget: `$518,046`

No unsupported cited claim was observed in those three answers.

## Triage prediction skill

The Experiment 5 prediction was correct.

The expected source was absent from the top five results, so retrieval failed. Generation remained faithful and refused to invent the vote.

## Main lesson

The system’s most important observed weakness was retrieval, not generation.

The generator was generally conservative when evidence was missing or irrelevant. The next phase should focus on improving retrieval for exact identifiers, reducing boilerplate, and measuring whether the correct source appears in the top `k` results.

---

# Lab discipline

Do not silently discard failed or confounded experiments.

Keep the transcripts.

Record the source-row bug as part of the evidence.

Do not claim that the weak prompt is safe based on Experiment 2.

Complete Experiments 3–5 only when actual excerpt values and real chunk IDs are reaching the generation step.
MD