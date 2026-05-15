"""Schema-validator tests: happy path + one failing fixture per rule."""

import json

import pytest

from conftest import FIXTURES
from agent_diagnosis_spec import validate_finding, validate_structured_edit


def _load(name):
    return json.loads((FIXTURES / name).read_text())


# ---------------------------------------------------------------- findings


def test_canonical_finding_is_valid():
    r = validate_finding(_load("canonical_finding.json"))
    assert r.valid, r.errors
    assert r.errors == []
    assert bool(r) is True


@pytest.mark.parametrize(
    "fixture,needle",
    [
        ("non_compliant_missing_claim.json", "claim"),
        ("non_compliant_layer_out_of_range.json", "layer"),
        ("non_compliant_applyable_true_no_edits.json", "structured_edits"),
        ("non_compliant_applyable_false_no_reason.json", "reason"),
        ("non_compliant_bad_id.json", "id"),
        ("non_compliant_empty_evidence.json", "[]"),
        ("non_compliant_unknown_evidence_type.json", "type"),
        ("non_compliant_evidence_missing_field.json", "line_end"),
    ],
)
def test_non_compliant_fixtures_fail(fixture, needle):
    r = validate_finding(_load(fixture))
    assert not r.valid, f"{fixture} should have failed"
    assert any(needle in e for e in r.errors), (fixture, r.errors)


def test_each_evidence_variant_validates():
    base = _load("canonical_finding.json")
    variants = [
        {"type": "file_line", "file": "a.py", "line_start": 1, "line_end": 2},
        {"type": "virtual_artifact", "artifact": "error catalog", "reference": "17-18"},
        {"type": "trace_reference", "traces": [1, 2, 3], "developer_id": "dev_a8f3"},
        {"type": "data_reference", "schema": "dropoff_signal", "key": "MISSING_AGENT_ID", "value": "31%"},
        {"type": "eval_reference", "scenario_id": "issue 107", "expected": "unknown", "observed": "bug"},
    ]
    for v in variants:
        f = dict(base)
        f["evidence"] = [v]
        r = validate_finding(f)
        assert r.valid, (v["type"], r.errors)


def test_evidence_extension_field_is_allowed():
    base = _load("canonical_finding.json")
    f = dict(base)
    f["evidence"] = [
        {"type": "file_line", "file": "a.py", "line_start": 1, "line_end": 1, "confidence": 0.9}
    ]
    assert validate_finding(f).valid


def test_finding_domain_extension_field_is_allowed():
    base = _load("canonical_finding.json")
    f = dict(base)
    f["cohort_prevalence"] = "1 of 5 developers; 4 of 200 calls"
    assert validate_finding(f).valid


def test_evidence_variant_wrong_field_type_fails():
    base = _load("canonical_finding.json")
    f = dict(base)
    f["evidence"] = [{"type": "trace_reference", "traces": "1-4", "developer_id": "dev_a8f3"}]
    assert not validate_finding(f).valid


# ----------------------------------------------------------- structured edits


@pytest.mark.parametrize(
    "edit",
    [
        {"action": "replace", "file": "a.j2", "from_line_start": 1, "from_line_end": 2,
         "expected_content": "x", "new_content": "y"},
        {"action": "insert_after", "file": "a.j2", "at_line": 4, "new_content": "z"},
        {"action": "delete", "file": "a.j2", "from_line_start": 5, "from_line_end": 6,
         "expected_content": "old"},
        {"action": "move", "file": "a.j2", "from_line_start": 7, "from_line_end": 8,
         "to_line": 2, "expected_content": "blk"},
    ],
)
def test_each_action_validates(edit):
    r = validate_structured_edit(edit)
    assert r.valid, r.errors


def test_unknown_action_fails():
    r = validate_structured_edit({"action": "rewrite", "file": "a.j2"})
    assert not r.valid


def test_replace_missing_new_content_fails():
    r = validate_structured_edit(
        {"action": "replace", "file": "a.j2", "from_line_start": 1,
         "from_line_end": 1, "expected_content": "x"}
    )
    assert not r.valid
    assert any("new_content" in e for e in r.errors)


def test_replace_with_stray_field_fails():
    # additionalProperties:false on each action branch is intentional.
    r = validate_structured_edit(
        {"action": "replace", "file": "a.j2", "from_line_start": 1, "from_line_end": 1,
         "expected_content": "x", "new_content": "y", "at_line": 9}
    )
    assert not r.valid


def test_insert_after_does_not_require_expected_content():
    r = validate_structured_edit(
        {"action": "insert_after", "file": "a.j2", "at_line": 1, "new_content": "n"}
    )
    assert r.valid, r.errors


def test_line_numbers_must_be_positive_integers():
    r = validate_structured_edit(
        {"action": "insert_after", "file": "a.j2", "at_line": 0, "new_content": "n"}
    )
    assert not r.valid
