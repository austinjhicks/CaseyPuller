#!/usr/bin/env python3
"""
search_pdf_watchlist.py

Searches PDFs in a folder for patent numbers, application/proceeding numbers,
and party names listed in a CSV.

Example:
    pip install pymupdf
    python search_pdf_watchlist.py patsORparties.csv ./cafc_opinions --out matches.csv

Input CSV examples accepted:

1) No header:
    Bosch, IPR2024-00823

2) One term per line:
    Bosch
    IPR2024-00823

3) Header format:
    party_name,patent_number
    Bosch,IPR2024-00823

Output CSV columns:
    search_term,pdf_filename,pdf_path,page_numbers
"""

import argparse
import csv
import json
import re
from pathlib import Path

import fitz  # PyMuPDF


KNOWN_COLUMNS = {
    "patent", "patent_number", "patent_numbers", "patents",
    "application", "application_number", "application_numbers", "applications",
    "proceeding", "proceeding_number", "ipr", "ipr_number", "ptab_number",
    "party", "party_name", "party_names", "parties",
    "company", "company_name", "company_names", "companies",
    "entity", "entity_name",
    "search_term", "term", "name", "names",
}


def normalize_header(name: str) -> str:
    return name.strip().lower().replace(" ", "_").replace("-", "_")


def split_cell_terms(value: str) -> list[str]:
    """
    Split on separators that are unlikely to appear inside a patent number.
    Deliberately does NOT split on commas because patent numbers use commas.
    """
    if not value:
        return []

    value = value.strip()
    if not value:
        return []

    parts = re.split(r"[;\|\n\t]+", value)
    return [p.strip() for p in parts if p.strip()]


def row_has_known_header(row: list[str]) -> bool:
    normalized = {normalize_header(cell) for cell in row if cell and cell.strip()}
    return bool(normalized & KNOWN_COLUMNS)


def load_search_terms(csv_path: Path) -> list[str]:
    """
    Robust CSV loader.

    Key behavior:
    - If first row contains known column names, treat it as a header.
    - Otherwise, treat every cell in every row as a search term.
    """
    terms: list[str] = []

    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))

    if not rows:
        return []

    # Remove totally empty rows.
    rows = [row for row in rows if any(cell.strip() for cell in row)]
    if not rows:
        return []

    first_row = rows[0]

    if row_has_known_header(first_row):
        headers = [normalize_header(h) for h in first_row]
        data_rows = rows[1:]

        watch_indexes = [
            i for i, h in enumerate(headers)
            if h in KNOWN_COLUMNS
        ]

        for row in data_rows:
            for i in watch_indexes:
                if i < len(row):
                    terms.extend(split_cell_terms(row[i]))
    else:
        # No recognized header, so every cell is a term.
        for row in rows:
            for cell in row:
                terms.extend(split_cell_terms(cell))

    # Deduplicate while preserving order.
    seen = set()
    unique_terms = []
    for term in terms:
        cleaned = term.strip()
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key not in seen:
            seen.add(key)
            unique_terms.append(cleaned)

    return unique_terms


def compact_alnum(term: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", term)


def build_search_patterns(term: str) -> list[re.Pattern]:
    """
    Builds matching patterns.

    Examples:
    - Bosch -> literal case-insensitive search
    - IPR2024-00823 -> matches IPR2024-00823, IPR2024 00823, IPR2024–00823
    - 10,123,456 -> matches 10,123,456 and 10123456
    """
    stripped = term.strip()
    if not stripped:
        return []

    patterns: list[re.Pattern] = []

    # Literal match.
    patterns.append(re.compile(re.escape(stripped), re.IGNORECASE))

    compact = compact_alnum(stripped)

    # Flexible alphanumeric match for patent/proceeding/application numbers.
    # Allows punctuation/spaces between characters.
    if len(compact) >= 6 and any(ch.isdigit() for ch in compact):
        flexible = r"[\W_]*".join(map(re.escape, compact))
        patterns.append(re.compile(flexible, re.IGNORECASE))

    return patterns


def page_contains_term(page_text: str, term: str) -> bool:
    return any(pattern.search(page_text) for pattern in build_search_patterns(term))


def search_pdf(pdf_path: Path, terms: list[str]) -> dict[str, list[int]]:
    matches: dict[str, list[int]] = {term: [] for term in terms}

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"WARNING: Could not open PDF {pdf_path}: {e}")
        return matches

    with doc:
        for page_index in range(len(doc)):
            try:
                text = doc[page_index].get_text("text")
            except Exception as e:
                print(f"WARNING: Could not read page {page_index + 1} of {pdf_path}: {e}")
                continue

            if not text:
                continue

            for term in terms:
                if page_contains_term(text, term):
                    matches[term].append(page_index + 1)

    return matches


def search_folder(csv_path: Path, pdf_folder: Path, output_path: Path) -> None:
    terms = load_search_terms(csv_path)

    if not terms:
        raise ValueError(f"No search terms found in {csv_path}")

    print("Loaded search terms:")
    for term in terms:
        print(f"  - {term}")

    pdfs = sorted(pdf_folder.rglob("*.pdf"))

    if not pdfs:
        raise ValueError(f"No PDFs found in {pdf_folder}")

    rows = []

    for pdf_path in pdfs:
        print(f"Searching {pdf_path.name}...")
        pdf_matches = search_pdf(pdf_path, terms)

        for term, pages in pdf_matches.items():
            if pages:
                rows.append({
                    "search_term": term,
                    "pdf_filename": pdf_path.name,
                    "pdf_path": str(pdf_path),
                    "page_numbers": json.dumps(pages),
                })

    with output_path.open("w", encoding="utf-8", newline="") as f:
        fieldnames = ["search_term", "pdf_filename", "pdf_path", "page_numbers"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nDone. Found {len(rows)} matching term/PDF combinations.")
    print(f"Results written to: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Search PDFs for patent numbers, proceeding numbers, and party names from a CSV watchlist."
    )
    parser.add_argument("csv", help="Path to CSV containing patent numbers, proceeding numbers, or party names.")
    parser.add_argument("pdf_folder", help="Folder containing PDFs to search.")
    parser.add_argument("--out", default="pdf_watchlist_matches.csv", help="Output CSV path.")

    args = parser.parse_args()

    csv_path = Path(args.csv).expanduser().resolve()
    pdf_folder = Path(args.pdf_folder).expanduser().resolve()
    output_path = Path(args.out).expanduser().resolve()

    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    if not pdf_folder.exists() or not pdf_folder.is_dir():
        raise NotADirectoryError(f"PDF folder not found: {pdf_folder}")

    search_folder(csv_path, pdf_folder, output_path)


if __name__ == "__main__":
    main()
