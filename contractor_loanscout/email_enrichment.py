"""Email-first enrichment for OpenStreetMap discovery CSVs.

Only rows with a publicly listed email are written to the final leads CSV.
This first pass crawls OSM-listed websites; it does not guess domains or emails.
"""
from __future__ import annotations

import csv
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

EMAIL_RE = re.compile(r"(?i)[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+")
CONTACT_HINTS = ("contact", "about", "impressum", "support")
MAX_PAGES_PER_SITE = 6
TIMEOUT = 15
OUTPUT_COLUMNS = [
    "company_name", "email", "email_source_url", "email_status",
    "website", "phone", "category", "address", "city", "state",
    "postcode", "country", "source", "source_url", "osm_type", "osm_id",
]


def _normalize_url(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    if not re.match(r"^https?://", value, re.I):
        value = "https://" + value
    parsed = urlparse(value)
    if not parsed.hostname:
        return ""
    return value


def _extract_emails(text: str) -> list[str]:
    found = []
    for email in EMAIL_RE.findall(text or ""):
        email = email.strip(".,;:()[]{}<>").lower()
        if email not in found and not email.lower().endswith((".png", ".jpg", ".webp")):
            found.append(email)
    return found


def _contact_links(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    base_host = (urlparse(base_url).hostname or "").lower().removeprefix("www.")
    links = []
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        label = " ".join((anchor.get_text(" ", strip=True), href)).lower()
        if not any(hint in label for hint in CONTACT_HINTS):
            continue
        absolute = urljoin(base_url, href)
        parsed = urlparse(absolute)
        host = (parsed.hostname or "").lower().removeprefix("www.")
        if parsed.scheme in ("http", "https") and host == base_host and absolute not in links:
            links.append(absolute)
    return links


def _fetch_page(session: requests.Session, url: str) -> tuple[str, str]:
    response = session.get(url, timeout=TIMEOUT, allow_redirects=True)
    response.raise_for_status()
    content_type = response.headers.get("Content-Type", "").lower()
    if "text/html" not in content_type:
        return "", response.url
    return response.text[:2_000_000], response.url


def enrich_rows(input_csv: str | Path, output_csv: str | Path,
                user_agent: str = "ContractorLoanScoutEmailEnrichment/1.0",
                delay: float = 1.0) -> tuple[int, int]:
    """Enrich a discovery CSV and write only rows with publicly listed emails."""
    source = Path(input_csv)
    with source.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))

    session = requests.Session()
    session.headers.update({"User-Agent": user_agent})
    written, visited_domains = [], set()
    for row in rows:
        emails = _extract_emails(row.get("email", ""))
        email_source = row.get("source_url", "") if emails else ""
        website = _normalize_url(row.get("website", ""))
        if website:
            domain = (urlparse(website).hostname or "").lower().removeprefix("www.")
            if domain and domain not in visited_domains:
                visited_domains.add(domain)
                queue = [website]
                seen_urls = set()
                while queue and len(seen_urls) < MAX_PAGES_PER_SITE and not emails:
                    current = queue.pop(0)
                    if current in seen_urls:
                        continue
                    seen_urls.add(current)
                    try:
                        html, final_url = _fetch_page(session, current)
                    except requests.RequestException:
                        continue
                    page_emails = _extract_emails(html)
                    if page_emails:
                        emails = page_emails
                        email_source = final_url
                        break
                    if len(seen_urls) == 1 and html:
                        queue.extend(_contact_links(html, final_url))
                    time.sleep(max(0.0, delay))
            elif domain and domain in visited_domains:
                # A previously crawled domain is not fetched repeatedly; retain only OSM-tagged email.
                pass

        if not emails:
            continue
        for email in emails:
            result = {key: row.get(key, "") for key in OUTPUT_COLUMNS}
            result.update({
                "email": email,
                "email_source_url": email_source,
                "email_status": "publicly_listed_unverified",
                "website": website or row.get("website", ""),
            })
            written.append(result)

    session.close()
    destination = Path(output_csv)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(written)
    return len(rows), len(written)
