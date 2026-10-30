"""Conservative deduplication and prospect filtering for email leads."""
from __future__ import annotations

import csv
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

# Explicit exclusions based on the initial Philadelphia sample. Keep this list
# conservative and editable as the user reviews additional markets.
EXCLUDED_COMPANIES = {
    "cvs pharmacy": "National pharmacy chain",
    "bank of america": "National bank",
    "td bank": "Large banking chain",
    "chick fil a": "National restaurant chain",
    "wendys": "National restaurant chain",
    "cinemark university city penn 6": "National cinema chain/location",
    "hilton inn at penn": "National hotel brand",
    "rite aid": "Large pharmacy chain",
    "dig": "Multi-location restaurant chain",
    "wills eye hospital": "Large medical institution; not a typical independent SMB prospect",
    "pennsylvania horticultural society": "Nonprofit organization",
    "wyck museum": "Museum/nonprofit; not a typical business prospect",
    "love": "Public artwork, not a business",
}

# These are not automatically excluded: franchise or multi-location ownership
# can vary. They are surfaced for a human decision.
REVIEW_COMPANIES = {
    "saxbys": "Franchise/multi-location ownership should be checked",
    "parc": "Restaurant group/ownership structure should be checked",
    "amada": "Multi-location or group ownership should be checked",
}


def normalize_company(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode()
    value = value.lower().replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    words = [w for w in value.split() if w not in {
        "llc", "inc", "incorporated", "corp", "corporation", "co", "company",
        "limited", "ltd", "lp", "llp"
    }]
    return " ".join(words).strip()


def normalize_email(value: str) -> str:
    return (value or "").strip().lower()


def normalize_domain(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    parsed = urlparse(value if "://" in value else "https://" + value)
    host = (parsed.hostname or "").lower()
    return host.removeprefix("www.")


def _read_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def deduplicate_leads(input_csv: str | Path, output_dir: str | Path) -> dict[str, int]:
    """Write company, contact, and duplicate-review CSVs plus an Excel workbook."""
    rows = _read_csv(input_csv)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    excluded_rows: list[dict] = []
    review_rows: list[dict] = []
    for row in rows:
        name = (row.get("company_name") or "").strip()
        key = normalize_company(name)
        if not key:
            review_rows.append({"record_type": "needs_review", "company_name": name,
                                "email": row.get("email", ""), "website": row.get("website", ""),
                                "reason": "Missing company name; not grouped automatically"})
            continue
        if key in EXCLUDED_COMPANIES:
            excluded_rows.append({"record_type": "excluded_company", "company_name": name,
                                  "email": row.get("email", ""), "website": row.get("website", ""),
                                  "reason": EXCLUDED_COMPANIES[key]})
            continue
        groups[key].append(row)
        if key in REVIEW_COMPANIES:
            review_rows.append({"record_type": "ownership_review", "company_name": name,
                                "email": row.get("email", ""), "website": row.get("website", ""),
                                "reason": REVIEW_COMPANIES[key]})

    company_rows: list[dict] = []
    contact_rows: list[dict] = []
    seen_emails: dict[str, str] = {}
    domains_to_companies: dict[str, set[str]] = defaultdict(set)
    duplicate_email_rows = 0

    for key, company_records in sorted(groups.items()):
        first = company_records[0]
        display_name = (first.get("company_name") or "").strip()
        unique_company_emails: list[str] = []
        for record in company_records:
            email = normalize_email(record.get("email", ""))
            if email and email not in unique_company_emails:
                unique_company_emails.append(email)
            domain = normalize_domain(record.get("website", ""))
            if domain:
                domains_to_companies[domain].add(key)

        company_rows.append({
            "company_name": display_name,
            "website": first.get("website", ""),
            "phone": first.get("phone", ""),
            "city": first.get("city", ""),
            "state": first.get("state", ""),
            "category": first.get("category", ""),
            "emails": "; ".join(unique_company_emails),
            "email_count": len(unique_company_emails),
            "source": first.get("source", ""),
            "source_url": first.get("source_url", ""),
            "company_key": key,
            "source_rows_grouped": len(company_records),
        })

        for record in company_records:
            email = normalize_email(record.get("email", ""))
            if not email:
                continue
            if email in seen_emails:
                duplicate_email_rows += 1
                review_rows.append({
                    "record_type": "duplicate_email",
                    "company_name": record.get("company_name", ""),
                    "email": email, "website": record.get("website", ""),
                    "reason": "Email already retained for " + seen_emails[email],
                })
                continue
            seen_emails[email] = display_name
            contact_rows.append({
                "company_name": record.get("company_name", ""),
                "email": email,
                "website": record.get("website", ""),
                "phone": record.get("phone", ""),
                "email_source_url": record.get("email_source_url", ""),
                "email_status": record.get("email_status", ""),
                "city": record.get("city", ""),
                "state": record.get("state", ""),
                "category": record.get("category", ""),
            })

    for domain, company_keys in domains_to_companies.items():
        if len(company_keys) > 1:
            names = [next((r["company_name"] for r in company_rows if r["company_key"] == k), k)
                     for k in sorted(company_keys)]
            review_rows.append({
                "record_type": "shared_domain",
                "company_name": "; ".join(names),
                "email": "", "website": domain,
                "reason": "Different normalized company names share this domain; review before merging",
            })

    _write_csv(out / "company_master.csv", company_rows, [
        "company_name", "website", "phone", "city", "state", "category", "emails",
        "email_count", "source", "source_url", "company_key", "source_rows_grouped",
    ])
    _write_csv(out / "email_contacts.csv", contact_rows, [
        "company_name", "email", "website", "phone", "email_source_url",
        "email_status", "city", "state", "category",
    ])
    review_rows.extend(excluded_rows)
    _write_csv(out / "duplicate_review.csv", review_rows, [
        "record_type", "company_name", "email", "website", "reason",
    ])

    try:
        from openpyxl import Workbook
        from openpyxl.utils import get_column_letter
        workbook = Workbook()
        sheets = [
            ("Company Master", company_rows, list(company_rows[0]) if company_rows else [
                "company_name", "website", "phone", "city", "state", "category", "emails",
                "email_count", "source", "source_url", "company_key", "source_rows_grouped"]),
            ("Email Contacts", contact_rows, list(contact_rows[0]) if contact_rows else [
                "company_name", "email", "website", "phone", "email_source_url",
                "email_status", "city", "state", "category"]),
            ("Duplicate Review", review_rows, ["record_type", "company_name", "email", "website", "reason"]),
        ]
        for index, (title, data, columns) in enumerate(sheets):
            ws = workbook.active if index == 0 else workbook.create_sheet()
            ws.title = title
            ws.append(columns)
            for item in data:
                ws.append([item.get(col, "") for col in columns])
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
            for col_idx, col in enumerate(columns, 1):
                width = min(max(len(col) + 2, max((len(str(item.get(col, ""))) for item in data), default=0) + 2), 55)
                ws.column_dimensions[get_column_letter(col_idx)].width = width
        workbook.save(out / "lead_deduplication.xlsx")
    except ImportError:
        # CSV deliverables remain available if openpyxl is not installed.
        pass

    return {
        "input_rows": len(rows),
        "companies_kept": len(company_rows),
        "unique_emails_kept": len(contact_rows),
        "excluded_rows": len(excluded_rows),
        "duplicate_email_rows": duplicate_email_rows,
        "review_rows": len(review_rows),
    }
