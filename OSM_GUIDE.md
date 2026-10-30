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


## Email-only lead enrichment

After an OSM search, run:

```powershell
.\.venv\Scripts\python.exe -m contractor_loanscout email-enrich --input out\osm_business_leads.csv --out out\email_leads.csv
```

This first enrichment version crawls only official website URLs already present in the OSM CSV. It checks the homepage and same-domain contact/about pages, and writes only rows where it finds a publicly listed email. Businesses without an OSM-listed website are skipped for now; automatic website discovery for those businesses is a separate next step.

The email status is `publicly_listed_unverified`: the address was visible on a public page, but mailbox deliverability has not been tested. The email source URL is retained. Use a descriptive `EMAIL_CRAWLER_USER_AGENT` environment variable, crawl politely, and respect website terms, robots guidance, and applicable privacy/marketing laws.

## Deduplicate and filter email leads

After email enrichment, run:

```powershell
.\\.venv\\Scripts\\python.exe -m contractor_loanscout dedupe --input out\\email_leads.csv --out-dir out\\deduplicated
```

This creates `company_master.csv` (one row per normalized company, with its unique emails grouped), `email_contacts.csv` (one row per unique email), `duplicate_review.csv` (excluded businesses, duplicate email rows, shared domains, and ownership-review flags), and `lead_deduplication.xlsx` (the same three views in workbook tabs).

The initial exclusion list is deliberately explicit and editable in `contractor_loanscout/dedupe.py`. It includes large chains/institutions and non-business/nonprofit entries identified in the initial Philadelphia sample. Saxbys, Parc, and Amada are flagged for ownership review rather than automatically excluded. Shared website domains are flagged, not merged, because different businesses can share a web domain. Company-name normalization groups punctuation and common legal-suffix variants; inspect the review report before treating the output as a verified list of independent owners. The original enrichment CSV is never overwritten.
