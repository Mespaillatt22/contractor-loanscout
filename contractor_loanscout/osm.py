"""OpenStreetMap business discovery via Nominatim and Overpass.

This is a separate discovery source; it does not change the US DOT workflow.
Use a city, county, or state area per search. Do not repeatedly query the
entire country or run concurrent searches against public OSM infrastructure.
"""
from __future__ import annotations

import csv
import re
import time
from pathlib import Path
from typing import Iterable

import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
TIMEOUT = 60
DEFAULT_LIMIT = 500
DEFAULT_OUT = "out/osm_business_leads.csv"

CATEGORY_KEYS = {
    "all": ("shop", "office", "craft", "industrial", "healthcare", "tourism", "leisure", "amenity"),
    "shop": ("shop",), "office": ("office",), "craft": ("craft",),
    "industrial": ("industrial",), "healthcare": ("healthcare",),
    "tourism": ("tourism",), "leisure": ("leisure",), "amenity": ("amenity",),
}
COLUMNS = [
    "company_name", "category", "email", "phone", "website", "address",
    "city", "state", "postcode", "country", "source", "source_url",
    "osm_type", "osm_id",
]
EXCLUDED_AMENITIES = {
    "school", "kindergarten", "college", "university", "place_of_worship",
    "police", "fire_station", "prison", "courthouse", "townhall",
    "community_centre", "library", "post_box", "recycling",
}


class OSMUnavailable(RuntimeError):
    """Geocoding or Overpass could not complete the search."""


def _clean(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def _first(tags: dict, *keys: str) -> str:
    for key in keys:
        value = _clean(tags.get(key))
        if value:
            return value
    return ""


def _area_id(result: dict) -> int:
    if result.get("osm_type") != "relation":
        raise OSMUnavailable(
            "The location search did not return an administrative boundary. "
            "Try a city, county, or state name."
        )
    try:
        return 3_600_000_000 + int(result["osm_id"])
    except (KeyError, TypeError, ValueError):
        raise OSMUnavailable("The location boundary response was incomplete.") from None


def _query(area_id: int, category: str, limit: int) -> str:
    selectors = "\n".join(
        f'  nwr["name"]["{key}"](area.searchArea);'
        for key in CATEGORY_KEYS[category]
    )
    return (
        "[out:json][timeout:45];\n"
        f"area({area_id})->.searchArea;\n"
        "(\n" + selectors + "\n);\n"
        f"out center tags {limit};"
    )


def _to_row(element: dict) -> dict | None:
    tags = element.get("tags") or {}
    name = _first(tags, "name", "brand", "operator")
    if not name or tags.get("amenity") in EXCLUDED_AMENITIES:
        return None

    category_key = next((key for key in CATEGORY_KEYS["all"] if tags.get(key)), "")
    category = _first(tags, category_key) if category_key else ""
    number, street = _first(tags, "addr:housenumber"), _first(tags, "addr:street")
    address = " ".join(part for part in (number, street) if part)
    osm_type, osm_id = element.get("type", ""), str(element.get("id", ""))
    website = _first(tags, "contact:website", "website", "url")
    if website and not re.match(r"^https?://", website, re.I):
        website = "https://" + website

    return {
        "company_name": name,
        "category": f"{category_key}: {category}" if category else category_key,
        "email": _first(tags, "contact:email", "email"),
        "phone": _first(tags, "contact:phone", "phone", "contact:mobile", "mobile"),
        "website": website,
        "address": address,
        "city": _first(tags, "addr:city", "addr:town", "addr:village", "addr:hamlet", "addr:suburb"),
        "state": _first(tags, "addr:state"),
        "postcode": _first(tags, "addr:postcode"),
        "country": _first(tags, "addr:country"),
        "source": "OpenStreetMap",
        "source_url": f"https://www.openstreetmap.org/{osm_type}/{osm_id}",
        "osm_type": osm_type,
        "osm_id": osm_id,
    }


def _identity(row: dict) -> tuple[str, str]:
    name = re.sub(r"[^a-z0-9]", "", (row.get("company_name") or "").lower())
    postcode = re.sub(r"\s+", "", (row.get("postcode") or "").lower())
    return name, postcode


def _existing_identities(paths: Iterable[str | Path]) -> set[tuple[str, str]]:
    found = set()
    for path in paths:
        try:
            with Path(path).open(newline="", encoding="utf-8-sig") as handle:
                for row in csv.DictReader(handle):
                    name = row.get("company_name") or row.get("legal_name") or ""
                    postcode = row.get("postcode") or row.get("zip") or ""
                    identity = _identity({"company_name": name, "postcode": postcode})
                    if identity[0]:
                        found.add(identity)
        except (OSError, csv.Error):
            continue
    return found


class OpenStreetMapClient:
    """Polite client for Nominatim geocoding and Overpass business discovery."""

    def __init__(self, user_agent: str, session: requests.Session | None = None):
        if not user_agent or len(user_agent.strip()) < 8:
            raise ValueError("Provide a descriptive OSM_USER_AGENT identifying this application.")
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": user_agent})
        self._last_geocode = 0.0

    def _get_area(self, location: str) -> int:
        # Nominatim's public endpoint has a strict one-request-per-second policy.
        wait = 1.0 - (time.monotonic() - self._last_geocode)
        if wait > 0:
            time.sleep(wait)
        try:
            response = self.session.get(
                NOMINATIM_URL,
                params={"q": location, "format": "jsonv2", "limit": 5, "addressdetails": 1},
                timeout=TIMEOUT,
            )
            self._last_geocode = time.monotonic()
            response.raise_for_status()
            results = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise OSMUnavailable(f"OpenStreetMap location lookup failed: {exc}") from exc
        if not results:
            raise OSMUnavailable(f"No OpenStreetMap boundary found for {location!r}.")
        result = next((item for item in results if item.get("osm_type") == "relation"), results[0])
        return _area_id(result)

    def search(self, location: str, category: str = "all", limit: int = DEFAULT_LIMIT,
               stop=None) -> list[dict]:
        location, category = _clean(location), category.lower().strip()
        if not location:
            raise ValueError("Enter a city, county, or state to search.")
        if category not in CATEGORY_KEYS:
            raise ValueError(f"Category must be one of: {', '.join(CATEGORY_KEYS)}.")
        if not 1 <= int(limit) <= 5000:
            raise ValueError("Limit must be between 1 and 5000.")
        if stop is not None and stop.is_set():
            return []

        area_id = self._get_area(location)
        if stop is not None and stop.is_set():
            return []
        try:
            response = self.session.post(
                OVERPASS_URL, data={"data": _query(area_id, category, int(limit))},
                timeout=TIMEOUT + 10,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise OSMUnavailable(
                "OpenStreetMap business search failed. The public Overpass service may be busy; "
                "try again later or search a smaller area."
            ) from exc

        rows, seen = [], set()
        for element in payload.get("elements", []):
            if stop is not None and stop.is_set():
                break
            row = _to_row(element)
            if row is None:
                continue
            key = (row["osm_type"], row["osm_id"])
            if key not in seen:
                seen.add(key)
                rows.append(row)
        return rows

    def close(self) -> None:
        self.session.close()


def search_to_csv(location: str, category: str = "all", limit: int = DEFAULT_LIMIT,
                  out: str | Path = DEFAULT_OUT, user_agent: str = "ContractorLoanScout/1.0 (github.com/Mespaillatt22/contractor-loanscout)",
                  existing_paths: Iterable[str | Path] = (), stop=None) -> tuple[int, int]:
    """Write OSM discovery rows, skipping name/postcode matches in existing lead files."""
    client = OpenStreetMapClient(user_agent)
    try:
        rows = client.search(location, category, limit, stop)
    finally:
        client.close()

    existing = _existing_identities(existing_paths)
    output, seen = [], set()
    for row in rows:
        identity = _identity(row)
        if identity in seen or (identity[0] and identity in existing):
            continue
        seen.add(identity)
        output.append(row)

    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(output)
    return len(rows), len(output)
