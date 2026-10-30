"""CLI for deduplicating and filtering email-first business leads."""
from __future__ import annotations

import argparse
import logging
import sys

from .dedupe import deduplicate_leads


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="contractor_loanscout dedupe",
        description="Group unique companies and emails; flag exclusions and possible duplicates.",
    )
    parser.add_argument("--input", default="out/email_leads.csv", help="email enrichment CSV")
    parser.add_argument("--out-dir", default="out/deduplicated", help="folder for clean outputs")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        counts = deduplicate_leads(args.input, args.out_dir)
    except (OSError, ValueError) as exc:
        logging.error("%s", exc)
        return 2
    logging.info("Input rows: %d", counts["input_rows"])
    logging.info("Unique companies kept: %d", counts["companies_kept"])
    logging.info("Unique email contacts kept: %d", counts["unique_emails_kept"])
    logging.info("Excluded rows: %d", counts["excluded_rows"])
    logging.info("Duplicate email rows removed: %d", counts["duplicate_email_rows"])
    logging.info("Review items: %d", counts["review_rows"])
    logging.info("Files saved in: %s", args.out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
