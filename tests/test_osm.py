from contractor_loanscout import osm


def test_query_includes_selected_category_and_limit():
    query = osm._query(3600000001, "shop", 123)
    assert 'nwr["name"]["shop"](area.searchArea)' in query
    assert "out center tags 123" in query


def test_element_maps_business_tags_to_csv_fields():
    row = osm._to_row({
        "type": "node", "id": 42,
        "tags": {
            "name": "Example Plumbing", "craft": "plumber",
            "contact:email": "info@example.com", "phone": "215-555-0100",
            "website": "example.com", "addr:street": "Market Street",
            "addr:housenumber": "123", "addr:city": "Philadelphia",
            "addr:state": "PA", "addr:postcode": "19107",
        },
    })
    assert row["company_name"] == "Example Plumbing"
    assert row["email"] == "info@example.com"
    assert row["website"] == "https://example.com"
    assert row["address"] == "123 Market Street"
    assert row["source_url"] == "https://www.openstreetmap.org/node/42"


def test_non_business_amenities_are_excluded():
    assert osm._to_row({"type": "node", "id": 9,
                        "tags": {"name": "Central Library", "amenity": "library"}}) is None


def test_missing_name_is_excluded():
    assert osm._to_row({"type": "node", "id": 10, "tags": {"shop": "bakery"}}) is None


def test_same_company_and_postcode_identity_matches():
    a = {"company_name": "Example, LLC", "postcode": "19107"}
    b = {"company_name": "Example LLC", "postcode": "19107"}
    assert osm._identity(a) == osm._identity(b)


def test_location_must_be_administrative_relation():
    try:
        osm._area_id({"osm_type": "way", "osm_id": 123})
    except osm.OSMUnavailable as exc:
        assert "administrative boundary" in str(exc)
    else:
        raise AssertionError("expected OSMUnavailable")
