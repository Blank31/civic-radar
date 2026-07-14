#!/usr/bin/env bash
set -euo pipefail

mkdir -p notes/phase4-framework-comparison

questions=(
  "What did the council decide about parking meters in 2019?"
  "What tax increase did the council approve in 2018?"
  "Which company received the downtown monorail contract in 2020?"
  "What happened with the committee?"
  "What decisions were made about housing?"
)

for i in "${!questions[@]}"; do
  n=$((i + 1))
  question="${questions[$i]}"

  echo "Running question $n through ask.py"

  PYTHONPATH=src python src/ask.py \
    --verbose \
    --top-k 5 \
    "$question" \
    > "notes/phase4-framework-comparison/q${n}-manual.txt" 2>&1

  echo "Running question $n through ask_lc.py"

  PYTHONPATH=src python src/ask_lc.py \
    --top-k 5 \
    "$question" \
    > "notes/phase4-framework-comparison/q${n}-langchain.txt" 2>&1
done

echo "Comparison runs complete."
