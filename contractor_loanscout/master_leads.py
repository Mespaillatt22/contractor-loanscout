"""Append email-qualified prospects to one deduplicated nationwide master CSV."""
from __future__ import annotations

import csv
from pathlib import Path

from .dedupe import EXCLUDED_COMPANIES, normalize_company, normalize_email

MASTER_COLUMNS = [
    "company_name", "email", "first_name", "last_name", "contact_title",
    "phone", "website", "city", "state", "category", "source",
    "source_url", "email_source_url", "email_status", "company_key",
]
FIELD_ALIASES = {
    "email": ("email", "email_address"),
    "company_name": ("company_name", "business_name", "name"),
    "first_name": ("first_name", "contact_first_name", "owner_first_name"),
    "last_name": ("last_name", "contact_last_name", "owner_last_name"),
    "contact_title": ("contact_title", "title", "job_title"),
    "phone": ("phone", "telephone"),
    "website": ("website", "url"),
    "city": ("city",),
    "state": ("state",),
    "category": ("category", "industry"),
    "source": ("source",),
    "source_url": ("source_url",),
    "email_source_url": ("email_source_url",),
    "email_status": ("email_status",),
}


def _read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _pick(row: dict[str, str], field: str) -> str:
    for alias in FIELD_ALIASES[field]:
        value = (row.get(alias) or "").strip()
        if value:
            return value
    return ""


def _write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=MASTER_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def update_master(input_csv: str | Path, master_csv: str | Path) -> dict[str, int]:
    """Merge only rows with company names and public email addresses.

    Email is globally unique. Multiple distinct emails for one company are kept
    as separate contact rows. Existing non-empty values are not overwritten by
    blanks; newly discovered values fill gaps. Company-name matches are
    normalized conservatively; shared domains are never used to merge firms.
    """
    source = Path(input_csv)
    destination = Path(master_csv)
    incoming = _read_rows(source)
    existing = _read_rows(destination)
    by_email: dict[str, dict[str, str]] = {}
    for row in existing:
        email = normalize_email(row.get("email", ""))
        if email and email not in by_email:
            clean = {column: (row.get(column) or "").strip() for column in MASTER_COLUMNS}
            clean["company_key"] = clean["company_key"] or normalize_company(clean["company_name"])
            by_email[email] = clean

    added = updated = skipped = conflicts = 0
    for raw in incoming:
        email = normalize_email(_pick(raw, "email"))
        company = _pick(raw, "company_name")
        company_key = normalize_company(company)
        if not email or not company_key:
            skipped += 1
            continue
        if company_key in EXCLUDED_COMPANIES:
            skipped += 1
            continue
        candidate = {column: _pick(raw, column) for column in FIELD_ALIASES}
        candidate["company_key"] = company_key
        candidate["email"] = email
        if email in by_email:
            current = by_email[email]
            current_key = current.get("company_key") or normalize_company(current.get("company_name", ""))
            if current_key and current_key != company_key:
                conflicts += 1
                # Do not silently attach a shared email address to another firm.
                continue
            changed = False
            for field in MASTER_COLUMNS:
                if field in ("email", "company_key"):
                    continue
                if not current.get(field) and candidate.get(field):
                    current[field] = candidate[field]
                    changed = True
            if changed:
                updated += 1
            else:
                skipped += 1
            continue
        by_email[email] = candidate
        added += 1

    result = sorted(by_email.values(), key=lambda row: (row["company_key"], row["email"]))
    _write_rows(destination, result)
    return {
        "input_rows": len(incoming),
        "master_rows": len(result),
        "added": added,
        "updated": updated,
        "skipped": skipped,
        "email_company_conflicts": conflicts,
    }
