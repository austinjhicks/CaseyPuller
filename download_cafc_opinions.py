#!/usr/bin/env python3
"""
download_cafc_opinions.py

Reads a Federal Circuit "Released Opinions and Orders" .eml file, extracts
case-page links, follows each case page, finds the opinion/order PDF link,
and downloads each PDF into an output folder.

Usage:
    python download_cafc_opinions.py "Released Opinions and Orders.eml"
    python download_cafc_opinions.py "Released Opinions and Orders.eml" --out opinions
    python download_cafc_opinions.py "Released Opinions and Orders.eml" --dry-run

Install dependencies:
    pip install requests beautifulsoup4
"""

from __future__ import annotations

import argparse
import email
import re
import sys
import time
from dataclasses import dataclass
from email import policy
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup


CASE_LINK_RE = re.compile(r"^\s*\d{2}-\d{4}\s*:", re.I)
CAFC_HOST_RE = re.compile(r"(^|\.)cafc\.uscourts\.gov$", re.I)


@dataclass(frozen=True)
class CaseLink:
    title: str
    url: str


@dataclass(frozen=True)
class PdfResult:
    case_title: str
    case_url: str
    pdf_url: str
    file_path: Path | None
    status: str


def unwrap_govdelivery_url(url: str) -> str:
    """
    GovDelivery tracking URLs often look like:
    https://links-2.govdelivery.com/CL0/https:%2F%2Fwww.cafc.uscourts.gov%2F.../1/...

    This extracts and decodes the real target URL.
    """
    parsed = urlparse(url)

    if "govdelivery.com" not in parsed.netloc.lower():
        return url

    # Example path:
    # /CL0/https:%2F%2Fwww.cafc.uscourts.gov%2Fsome-page%2F/1/...
    parts = parsed.path.split("/")
    if len(parts) >= 3 and parts[1].upper() == "CL0":
        target = unquote(parts[2])
        if target.startswith("http:") or target.startswith("https:"):
            return target

    return url


def is_cafc_url(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return bool(CAFC_HOST_RE.search(host))


def safe_filename(name: str, max_len: int = 180) -> str:
    name = re.sub(r"[\\/:*?\"<>|]+", "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    name = name.strip(" ._-")
    if len(name) > max_len:
        name = name[:max_len].rstrip(" ._-")
    return name or "opinion"


def extract_message_bodies(eml_path: Path) -> tuple[str, str]:
    msg = email.message_from_bytes(eml_path.read_bytes(), policy=policy.default)

    html_parts: list[str] = []
    text_parts: list[str] = []

    for part in msg.walk():
        content_type = part.get_content_type()
        if content_type == "text/html":
            html_parts.append(part.get_content())
        elif content_type == "text/plain":
            text_parts.append(part.get_content())

    return "\n".join(text_parts), "\n".join(html_parts)


def extract_case_links_from_html(html: str) -> list[CaseLink]:
    soup = BeautifulSoup(html, "html.parser")
    links: list[CaseLink] = []

    for a in soup.find_all("a"):
        href = a.get("href")
        title = a.get_text(" ", strip=True)

        if not href or not title:
            continue

        unwrapped = unwrap_govdelivery_url(href)

        # The actual opinion entries in the CAFC email are anchor text like:
        # "25-1968: FORAS TECHNOLOGIES LTD. v. BMW OF NORTH AMERICA, LLC [ORDER], Nonprecedential"
        if CASE_LINK_RE.match(title) and is_cafc_url(unwrapped):
            links.append(CaseLink(title=title, url=unwrapped))

    return dedupe_case_links(links)


def extract_case_links_from_text(text: str) -> list[CaseLink]:
    """
    Fallback parser for plain-text emails. It looks for:
        25-1968: CASE NAME
        <https://...>
    """
    links: list[CaseLink] = []
    current_title: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip()

        if CASE_LINK_RE.match(line):
            current_title = line
            continue

        if current_title and line.startswith("<http") and line.endswith(">"):
            url = line[1:-1]
            unwrapped = unwrap_govdelivery_url(url)
            if is_cafc_url(unwrapped):
                links.append(CaseLink(title=current_title, url=unwrapped))
            current_title = None

    return dedupe_case_links(links)


def dedupe_case_links(links: Iterable[CaseLink]) -> list[CaseLink]:
    seen: set[str] = set()
    out: list[CaseLink] = []

    for link in links:
        key = link.url
        if key not in seen:
            seen.add(key)
            out.append(link)

    return out


def find_pdf_url(case_page_html: str, case_page_url: str) -> str | None:
    soup = BeautifulSoup(case_page_html, "html.parser")

    # Preferred: direct PDF links.
    for a in soup.find_all("a"):
        href = a.get("href")
        if not href:
            continue

        absolute = urljoin(case_page_url, href)

        if urlparse(absolute).path.lower().endswith(".pdf"):
            return absolute

    # Fallback: any PDF URL in the raw HTML.
    match = re.search(r"https?://[^\"'<>\s]+?\.pdf", case_page_html, re.I)
    if match:
        return match.group(0)

    return None


def download_file(session: requests.Session, url: str, destination: Path) -> None:
    with session.get(url, timeout=30, stream=True) as response:
        response.raise_for_status()

        content_type = response.headers.get("content-type", "").lower()
        if "pdf" not in content_type and not urlparse(url).path.lower().endswith(".pdf"):
            raise ValueError(f"URL did not look like a PDF: content-type={content_type!r}")

        with destination.open("wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 64):
                if chunk:
                    f.write(chunk)


def process_email(
    eml_path: Path,
    output_dir: Path,
    dry_run: bool = False,
    delay_seconds: float = 0.25,
) -> list[PdfResult]:
    text_body, html_body = extract_message_bodies(eml_path)

    case_links = extract_case_links_from_html(html_body)
    if not case_links:
        case_links = extract_case_links_from_text(text_body)

    if not case_links:
        raise RuntimeError("No Federal Circuit case links found in the email.")

    output_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (compatible; CAFCOpinionDownloader/0.1; "
                "+https://github.com/your-org/your-repo)"
            )
        }
    )

    results: list[PdfResult] = []

    for case in case_links:
        try:
            page = session.get(case.url, timeout=30)
            page.raise_for_status()

            pdf_url = find_pdf_url(page.text, case.url)
            if not pdf_url:
                results.append(PdfResult(case.title, case.url, "", None, "No PDF link found"))
                continue

            filename_from_url = Path(urlparse(pdf_url).path).name
            if filename_from_url.lower().endswith(".pdf"):
                filename = safe_filename(filename_from_url)
            else:
                filename = safe_filename(case.title) + ".pdf"

            destination = output_dir / filename

            if dry_run:
                results.append(PdfResult(case.title, case.url, pdf_url, destination, "Dry run; not downloaded"))
            else:
                download_file(session, pdf_url, destination)
                results.append(PdfResult(case.title, case.url, pdf_url, destination, "Downloaded"))

            time.sleep(delay_seconds)

        except Exception as exc:
            results.append(PdfResult(case.title, case.url, "", None, f"Error: {exc}"))

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Download Federal Circuit PDFs from a Released Opinions and Orders .eml file.")
    parser.add_argument("eml_file", type=Path, help="Path to the .eml file.")
    parser.add_argument("--out", type=Path, default=Path("cafc_opinions"), help="Output folder for downloaded PDFs.")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be downloaded without saving PDFs.")
    args = parser.parse_args()

    results = process_email(args.eml_file, args.out, dry_run=args.dry_run)

    print(f"Found {len(results)} case(s).")
    for result in results:
        print()
        print(result.case_title)
        print(f"Case page: {result.case_url}")
        if result.pdf_url:
            print(f"PDF:       {result.pdf_url}")
        if result.file_path:
            print(f"File:      {result.file_path}")
        print(f"Status:    {result.status}")

    failures = [r for r in results if not r.status.lower().startswith(("downloaded", "dry run"))]
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
