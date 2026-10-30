"""Command-line interface for the nationwide email lead master."""
from __future__ import annotations

import argparse
import logging
import sys

from .master_leads import update_master


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="contractor_loanscout master-update",
        description="Merge email-qualified leads into one deduplicated master CSV.",
    )
    parser.add_argument("--input", required=True, help="new email leads or legacy email contacts CSV")
    parser.add_argument("--master", default="out/master_email_leads.csv",
                        help="nationwide master CSV; created if it does not exist")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        counts = update_master(args.input, args.master)
    except (OSError, ValueError) as exc:
        logging.error("%s", exc)
        return 2
    logging.info("Input rows: %d", counts["input_rows"])
    logging.info("Master contact rows: %d", counts["master_rows"])
    logging.info("New email contacts added: %d", counts["added"])
    logging.info("Existing contacts enriched: %d", counts["updated"])
    logging.info("Rows skipped (no email/name, excluded, or already present): %d", counts["skipped"])
    logging.info("Email/company conflicts held back: %d", counts["email_company_conflicts"])
    logging.info("Master saved: %s", args.master)
    return 0


if __name__ == "__main__":
    sys.exit(main())
