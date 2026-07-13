"""One-time repair: re-parse year pages and fill missing metadata in the manifest, matching by file_id."""
import json
from pathlib import Path
from ingest import fetch_year_page, parse_meetings, MANIFEST

fresh = {}
for year in (2025, 2026):
    for r in parse_meetings(fetch_year_page(year), year):
        fresh[r["file_id"]] = r

lines = MANIFEST.read_text().strip().splitlines()
repaired, missing = [], 0
for line in lines:
    old = json.loads(line)
    new = fresh.get(old["file_id"])
    if new is None:
        missing += 1
    else:
        for key in ("meeting_date", "meeting_title", "doc_title"):
            old[key] = new[key]
    repaired.append(old)

tmp = MANIFEST.with_suffix(".jsonl.tmp")
tmp.write_text("\n".join(json.dumps(r) for r in repaired) + "\n")
tmp.rename(MANIFEST)
print(f"repaired {len(repaired)} records ({missing} not found on pages)")
