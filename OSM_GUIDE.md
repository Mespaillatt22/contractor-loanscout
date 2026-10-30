# OpenStreetMap discovery (free)

This adds an optional discovery command. It does **not** change the US DOT
contractor search, its ranking, or its existing CSV.

## Run a search

From the project folder in PowerShell:

```powershell
.venv\Scripts\python -m contractor_loanscout osm-search --location "Philadelphia, PA" --category all --limit 500 --existing out\contractor_leads.csv
```

Other categories: `shop`, `office`, `craft`, `industrial`, `healthcare`,
`tourism`, `leisure`, and `amenity`. Use a city, county, or state per run;
do not request the entire country in one query.

The default output is `out\osm_business_leads.csv`. It is a separate file and
does not overwrite contractor results. Add `--out path\file.csv` to change it.
You can repeat `--existing another.csv` to skip matching company-name/postcode
pairs already in your existing CSV files.

## Important limits

- OSM is a map database, not a complete business directory. Coverage varies
  by location and category.
- Email addresses, phone numbers, websites, and owner names are only included
  when contributors have added those tags. Owner names are generally not
  available; this source does not infer them.
- The first version writes CSV only. The existing contractor workflow remains
  unchanged.
- Public Nominatim and Overpass services have usage limits and can be busy.
  Search one bounded area at a time and avoid repeated automated bulk runs.
- OpenStreetMap data is licensed under the Open Database License (ODbL).
  Retain the source attribution and review OSM's current usage and attribution
  requirements before redistributing a derived database commercially.

For a descriptive user-agent string, set `OSM_USER_AGENT` in your local
`.env` file to identify your application and provide a contact route.
