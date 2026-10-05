from app.refinement.entity_resolution import (Claim, EntityRecord, compare, find_conflicts,
                                              near_duplicates, normalize_name, resolve)


def company(id, name, **kwargs):
    return EntityRecord(id=id, name=name, type="Company", **kwargs)


def test_normalization_ignores_case_punctuation_and_legal_form():
    assert normalize_name("ACME, Inc.") == normalize_name("Acme Incorporated") == "acme"
    assert normalize_name("蓝鸟科技有限公司") == "蓝鸟科技"


def test_identifiers_dominate_names():
    same = compare(company("a", "Acme", identifiers={"lei": "L1"}), company("b", "Totally Different", identifiers={"lei": "L1"}))
    different = compare(company("a", "Acme Inc", identifiers={"lei": "L1"}), company("b", "Acme Inc", identifiers={"lei": "L2"}))
    assert same.decision == "merge" and different.decision == "distinct"


def test_same_name_in_different_countries_is_not_merged():
    decision = compare(company("a", "Apple Inc", attributes={"country": "US"}),
                       company("b", "Apple Ltd", attributes={"country": "UK"}))
    assert decision.decision == "distinct"


def test_close_names_with_matching_context_merge_and_weaker_ones_go_to_review():
    merged = compare(company("a", "Acme Inc", attributes={"country": "US"}),
                     company("b", "ACME Incorporated", attributes={"country": "US"}))
    review = compare(company("a", "Bluebird Logistics"), company("b", "Bluebird Logistic Services"))
    assert merged.decision == "merge"
    assert review.decision == "review"


def test_resolve_builds_canonical_entities_with_aliases():
    records = [company("r1", "International Business Machines", authority=2),
               company("r2", "IBM", authority=1),
               company("r3", "Acme Inc", identifiers={"lei": "L1"}),
               company("r4", "ACME Corporation", identifiers={"lei": "L1"})]
    aliases = {"ibm": "ibm", "international business machines": "ibm"}
    result = resolve(records, aliases)
    names = {e["name"]: e["members"] for e in result["entities"]}
    assert names["International Business Machines"] == ["r1", "r2"]
    assert sorted(names) == ["Acme Inc", "International Business Machines"]


def test_transitive_merge_with_conflicting_identifiers_goes_to_review():
    records = [company("a", "Northwind Traders", identifiers={"lei": "L1"}, attributes={"country": "US"}),
               company("b", "Northwind Traders", attributes={"country": "US"}),
               company("c", "Northwind Traders", identifiers={"lei": "L2"}, attributes={"country": "US"})]
    result = resolve(records)
    assert len(result["entities"]) == 2
    assert any("cluster_identifier_conflict" in d["reasons"] for d in result["review"])


def test_near_duplicates_by_shingle_jaccard():
    docs = {"d1": "Full-time employees receive 20 days of annual leave each year.",
            "d2": "Full-time employees receive 20 days of annual leave each year!",
            "d3": "Contract C-101 has counterparty Bluebird."}
    assert near_duplicates(docs, 0.8) == [{"left": "d1", "right": "d2", "jaccard": 1.0}]


def test_conflicts_resolve_by_date_then_authority_else_review():
    claims = [Claim("acme", "ceo", "Ann Lee", "hr", "2025-01-01", 1),
              Claim("acme", "ceo", "Bo Chen", "press", "2026-03-01", 1),
              Claim("acme", "hq", "Boston", "crm", "2026-01-01", 1),
              Claim("acme", "hq", "Austin", "registry", "2026-01-01", 3),
              Claim("acme", "cfo", "Kim", "a", "2026-01-01", 1),
              Claim("acme", "cfo", "Lee", "b", "2026-01-01", 1)]
    result = {c["property"]: c for c in find_conflicts(claims)}
    assert result["ceo"]["resolution"] == "latest_effective_date" and result["ceo"]["winner"] == "Bo Chen"
    assert result["hq"]["resolution"] == "higher_authority" and result["hq"]["winner"] == "Austin"
    assert result["cfo"]["resolution"] == "needs_review" and result["cfo"]["winner"] is None


def test_agreeing_duplicates_do_not_hide_the_real_runner_up():
    claims = [Claim("acme", "ceo", "Bo Chen", "a", "2026-03-01"), Claim("acme", "ceo", "Bo Chen", "b", "2026-03-01"),
              Claim("acme", "ceo", "Ann Lee", "c", "2025-01-01")]
    assert find_conflicts(claims)[0]["resolution"] == "latest_effective_date"
