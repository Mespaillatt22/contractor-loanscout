from contractor_loanscout.dedupe import normalize_company, normalize_domain, deduplicate_leads


def test_normalize_company_removes_punctuation_and_legal_suffix():
    assert normalize_company("Example, LLC") == normalize_company("Example LLC")


def test_normalize_domain_removes_scheme_path_and_www():
    assert normalize_domain("https://www.example.com/contact") == "example.com"


def test_dedupe_groups_company_emails_and_excludes_chains(tmp_path):
    source = tmp_path / "leads.csv"
    source.write_text(
        "company_name,email,website,phone,city,state,category,source,source_url,email_source_url,email_status\n"
        "Local Cafe,info@local.test,https://local.test,123,Philadelphia,PA,cafe,OSM,url1,page1,publicly_listed_unverified\n"
        "Local Cafe,owner@local.test,https://local.test,123,Philadelphia,PA,cafe,OSM,url1,page2,publicly_listed_unverified\n"
        "Local Cafe,info@local.test,https://local.test,123,Philadelphia,PA,cafe,OSM,url1,page1,publicly_listed_unverified\n"
        "CVS Pharmacy,store@cvs.test,https://cvs.test,456,Philadelphia,PA,pharmacy,OSM,url2,page3,publicly_listed_unverified\n",
        encoding="utf-8",
    )
    counts = deduplicate_leads(source, tmp_path / "out")
    assert counts["input_rows"] == 4
    assert counts["companies_kept"] == 1
    assert counts["unique_emails_kept"] == 2
    assert counts["excluded_rows"] == 1
    assert counts["duplicate_email_rows"] == 1
