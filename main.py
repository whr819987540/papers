import argparse
import json
import re
import time
from pathlib import Path

import openreview


def parse_args():
    parser = argparse.ArgumentParser(
        description="Download accepted papers from an OpenReview conference venue."
    )
    parser.add_argument(
        "--conference",
        help="Conference acronym, e.g. ICLR. Case-insensitive.",
        default="ICLR",
        required=False,
    )
    parser.add_argument(
        "--year",
        help="Conference year, e.g. 2026",
        default=2026,
        required=False,
    )
    return parser.parse_args()


def load_dotenv(path=Path(".env")):
    values = {}
    if not path.exists():
        return values

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")

    return values


def create_client():
    client_kwargs = {"baseurl": "https://api2.openreview.net"}

    return openreview.api.OpenReviewClient(**client_kwargs)


def get_value(note, key, default=""):
    item = note.content.get(key, {})
    if isinstance(item, dict):
        return item.get("value", default)
    return item or default


def get_first_value(note, keys, default=""):
    for key in keys:
        value = get_value(note, key, None)
        if value not in (None, "", []):
            return value
    return default


def safe_filename(text, max_len=120):
    text = re.sub(r'[\\/:*?"<>|]+', "_", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len] or "untitled"


def main():
    args = parse_args()
    print(args)
    conference = args.conference.upper()
    year = str(args.year)
    venue_id = f"{conference}.cc/{year}/Conference"
    out_dir = Path("papers", conference, year)

    print(f"Venue ID: {venue_id}")
    print(f"Output directory: {out_dir.resolve()}")
    out_dir.mkdir(parents=True, exist_ok=True)

    client = create_client()
    papers = client.get_all_notes(content={"venueid": venue_id})

    print(f"Found {len(papers)} accepted papers")

    for i, paper in enumerate(papers, 1):
        title = get_value(paper, "title")
        abstract = get_value(paper, "abstract")
        authors = get_value(paper, "authors", [])
        pdf_field = get_value(paper, "pdf", "")

        folder_name = f"{paper.number:04d}_{paper.id}_{safe_filename(title)}"
        paper_dir = out_dir / folder_name
        paper_dir.mkdir(parents=True, exist_ok=True)

        metadata = {
            "id": paper.id,
            "number": paper.number,
            "title": title,
            "authors": authors,
            "abstract": abstract,
            "tldr": get_first_value(paper, [
                "TL;DR",
                "TLDR",
                "tl_dr",
                "tldr",
            ]),
            "primary_area": get_first_value(paper, [
                "primary_area",
                "Primary Area",
                "primary area",
                "area",
            ]),
            "keywords": get_first_value(paper, [
                "keywords",
                "Keywords",
                "keyword",
            ], default=[]),
            "forum_url": f"https://openreview.net/forum?id={paper.id}",
            "pdf_field": pdf_field,
        }

        metadata_path = paper_dir / "metadata.json"
        pdf_path = paper_dir / "paper.pdf"

        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        if pdf_path.exists():
            print(f"[{i}/{len(papers)}] skip PDF: {folder_name}")
            continue

        try:
            pdf_bytes = client.get_attachment(
                id=paper.id,
                field_name="pdf"
            )
            pdf_path.write_bytes(pdf_bytes)
            print(f"[{i}/{len(papers)}] saved: {folder_name}")
            time.sleep(0.2)
        except Exception as e:
            print(f"[{i}/{len(papers)}] failed: {paper.id} - {e}")
    


if __name__ == "__main__":
    main()
