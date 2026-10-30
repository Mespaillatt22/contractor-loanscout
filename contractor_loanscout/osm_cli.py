"""Command-line interface for the standalone OpenStreetMap discovery source."""
from __future__ import annotations

import argparse
import logging
import os
import sys

from .osm import DEFAULT_LIMIT, DEFAULT_OUT, OSMUnavailable, search_to_csv


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="contractor_loanscout osm-search",
        description="Discover named businesses in OpenStreetMap and export public tags to CSV.",
    )
    parser.add_argument("--location", required=True,
                        help="city, county, or state, e.g. Philadelphia, PA")
    parser.add_argument("--category", choices=("all", "shop", "office", "craft", "industrial",
                                                "healthcare", "tourism", "leisure", "amenity"),
                        default="all")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                        help="maximum raw OSM objects requested (1-5000; default 500)")
    parser.add_argument("--out", default=DEFAULT_OUT, help="output CSV path")
    parser.add_argument("--existing", action="append", default=[],
                        help="existing CSV to deduplicate against; may be repeated")
    parser.add_argument("--user-agent", default=os.getenv(
        "OSM_USER_AGENT", "ContractorLoanScout/1.0 (https://github.com/Mespaillatt22/contractor-loanscout)"
    ), help="descriptive application identifier; set OSM_USER_AGENT in .env")
    parser.add_argument("--verbose", "-v", action="store_true")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s %(message)s")
    try:
        found, written = search_to_csv(
            location=args.location, category=args.category, limit=args.limit,
            out=args.out, user_agent=args.user_agent, existing_paths=args.existing,
        )
    except (ValueError, OSMUnavailable) as exc:
        logging.error("%s", exc)
        return 2
    logging.info("OpenStreetMap objects returned: %d", found)
    logging.info("New businesses written: %d -> %s", written, args.out)
    logging.info("OSM tags often omit email, phone, and website; missing fields are left blank.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
