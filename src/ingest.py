import argparse
import hashlib
import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup


BASE = "https://bloomington.in.gov"
USER_AGENT = "civic-radar-learning-project/0.1"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data/raw/bloomington-council"
MANIFEST = DATA_DIR / "manifest.jsonl"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("ingest")


def fetch_year_page(year: int) -> str:
    """Download the meeting documents page for one year."""
    url = f"{BASE}/council/meetings?year={year}"
    log.info("Fetching %s", url)

    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    response.raise_for_status()

    return response.text


def parse_meetings(html: str, year: int) -> list[dict]:
    """Extract one record per document link from a year page's HTML."""
    soup = BeautifulSoup(html, "html.parser")
    records = []

    for link in soup.find_all(
        "a",
        href=re.compile(r"/onboard/meetingFiles/\d+/download"),
    ):
        row = link.find_parent("tr")

        if row is None:
            continue

        first_cell = row.find(["th", "td"])
        row_text = first_cell.get_text(" ", strip=True) if first_cell else ""

        m = re.match(
            r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})",
            row_text,
        )

        meeting_date = None

        if m:
            month_num = [
                "January",
                "February",
                "March",
                "April",
                "May",
                "June",
                "July",
                "August",
                "September",
                "October",
                "November",
                "December",
            ].index(m.group(1)) + 1

            meeting_date = f"{year}-{month_num:02d}-{int(m.group(2)):02d}"

        file_id = int(
            re.search(r"/meetingFiles/(\d+)/download", link["href"]).group(1)
        )

        records.append(
            {
                "file_id": file_id,
                "url": BASE + link["href"] if link["href"].startswith("/") else link["href"],
                "meeting_date": meeting_date,
                "meeting_title": re.sub(r"^[A-Z][a-z]+ \d{1,2}\s+\d{1,2}:\d{2}\s*[ap]\.?m\.?\s*", "", row_text).strip(),
                "doc_label": link.get_text(strip=True),
                "doc_title": (link.get("title") or "")
                .replace("Download '", "")
                .rstrip("' PDF"),
            }
        )

        undated = sum(1 for r in records if r["meeting_date"] is None)
    if records and undated > len(records) / 2:
        raise RuntimeError(
            f"Parser tripwire: {undated}/{len(records)} records have no meeting_date — "
            "the page structure has probably changed. Refusing to write bad metadata."
        )
    if undated:
        log.warning(f"{undated}/{len(records)} records have no meeting_date")
        
    return records


def load_seen_ids() -> set[int]:
    """Read the manifest and return the set of file_ids we already have."""
    if not MANIFEST.exists():
        return set()

    with MANIFEST.open() as f:
        return {json.loads(line)["file_id"] for line in f if line.strip()}


def download_new(records: list[dict], year: int) -> None:
    seen = load_seen_ids()

    outdir = DATA_DIR / str(year)
    outdir.mkdir(parents=True, exist_ok=True)

    new = [r for r in records if r["file_id"] not in seen]

    log.info("%s documents on page; %s are new", len(records), len(new))

    for r in new:
        resp = requests.get(
            r["url"],
            headers={"User-Agent": USER_AGENT},
            timeout=60,
        )
        resp.raise_for_status()

        label = re.sub(
            r"[^a-z0-9]+",
            "-",
            r["doc_label"].lower(),
        ).strip("-")

        path = outdir / f"{r['meeting_date'] or 'undated'}_{label}_{r['file_id']}.pdf"

        path.write_bytes(resp.content)

        r["saved_path"] = str(path)
        r["sha256"] = hashlib.sha256(resp.content).hexdigest()
        r["downloaded_at"] = datetime.now(timezone.utc).isoformat()

        with MANIFEST.open("a") as f:
            f.write(json.dumps(r) + "\n")

        log.info("saved %s", path.name)

        time.sleep(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Ingest Bloomington council meeting documents"
    )
    parser.add_argument(
        "--year",
        type=int,
        default=2026,
        help="which year page to ingest",
    )

    args = parser.parse_args()

    html = fetch_year_page(args.year)
    records = parse_meetings(html, args.year)

    if not records:
        log.error("Parsed 0 records for year %s. The site structure may have changed.", args.year)
        raise SystemExit(1)

    download_new(records, args.year)