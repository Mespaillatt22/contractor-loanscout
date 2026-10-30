from contractor_loanscout.master_leads import update_master


def test_master_keeps_unique_emails_and_merges_new_fields(tmp_path):
    master = tmp_path / "master.csv"
    first = tmp_path / "first.csv"
    first.write_text(
        "company_name,email,website,city,state\n"
        "Local Cafe,INFO@local.test,https://local.test,Miami,FL\n"
        "Local Cafe,owner@local.test,https://local.test,Miami,FL\n",
        encoding="utf-8",
    )
    counts = update_master(first, master)
    assert counts["added"] == 2
    assert counts["master_rows"] == 2

    second = tmp_path / "second.csv"
    second.write_text(
        "company_name,email,first_name,last_name,website\n"
        "Local Cafe,info@local.test,Alex,Smith,https://local.test\n"
        "Local Cafe,owner@local.test,,,\n"
        "Another Shop,info@local.test,Pat,Lee,https://another.test\n",
        encoding="utf-8",
    )
    counts = update_master(second, master)
    assert counts["updated"] == 1
    assert counts["email_company_conflicts"] == 1
    assert counts["master_rows"] == 2
    content = master.read_text(encoding="utf-8-sig")
    assert "Alex" in content and "Smith" in content
    assert content.count("info@local.test") == 1


def test_master_skips_rows_without_email_or_company(tmp_path):
    source = tmp_path / "input.csv"
    source.write_text(
        "company_name,email\n"
        "No Email,,\n"
        ",person@example.test\n",
        encoding="utf-8",
    )
    counts = update_master(source, tmp_path / "master.csv")
    assert counts["added"] == 0
    assert counts["skipped"] == 2
