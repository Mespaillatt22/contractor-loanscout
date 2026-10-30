"""Command-line interface for email-only website enrichment."""
from __future__ import annotations

import argparse
import logging
import os
import sys

from .email_enrichment import enrich_rows


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="contractor_loanscout email-enrich",
        description="Crawl OSM-listed business websites and export only publicly listed emails.",
    )
    parser.add_argument("--input", default="out/osm_business_leads.csv",
                        help="OSM discovery CSV")
    parser.add_argument("--out", default="out/email_leads.csv",
                        help="email-only output CSV")
    parser.add_argument("--user-agent", default=os.getenv(
        "EMAIL_CRAWLER_USER_AGENT",
        "ContractorLoanScoutEmailEnrichment/1.0 (https://github.com/Mespaillatt22/contractor-loanscout)"
    ))
    parser.add_argument("--delay", type=float, default=1.0,
                        help="seconds to wait between page requests (default: 1)")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s %(message)s")
    try:
        total, saved = enrich_rows(args.input, args.out, args.user_agent, args.delay)
    except (OSError, ValueError) as exc:
        logging.error("%s", exc)
        return 2
    logging.info("Businesses read: %d", total)
    logging.info("Rows with public email addresses saved: %d -> %s", saved, args.out)
    logging.info("Businesses without a discovered email were excluded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
