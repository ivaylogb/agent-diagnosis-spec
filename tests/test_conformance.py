"""Conformance-harness tests on synthetic reports + the prose->evidence seam."""

import textwrap

import pytest

from agent_diagnosis_spec import run_conformance_suite
from agent_diagnosis_spec.conformance import _extract_evidence, _segments
from agent_diagnosis_spec.parser import parse_report


def _write(tmp_path, text):
    p = tmp_path / "report.md"
    p.write_text(textwrap.dedent(text).lstrip("\n"))
    return p


WELL_FORMED = """
    # Hypothesis report: demo / issue 9

    ## Failure summary

    - Scenario: issue 9
    - Expected: `unknown`
    - Predicted: `bug` (confidence 0.7)

    ## Hypotheses

    ### Hypothesis 1: A buried tie-break rule (Layer 3)

    **Claim:** The rule exists at classification.j2:44 but is unreachable at
    decision time because it sits below the signal lists.

    **Evidence:**
    - classification.j2:44: the mixed-signals rule
    - classification.j2:10: the bug signal list

    **Proposed change:** Promote the rule.

    ```json
    {"applyable": true, "edits": [{"file": "classification.j2", "action": "insert_after", "at_line": 4, "new_content": "check first"}]}
    ```

    **How to verify:** issue 9 flips bug->unknown; pass_rate 6/7 -> 7/7.

    ## What this report is NOT

    - Not verified fixes.
    """


def test_well_formed_report_passes(tmp_path):
    rep = run_conformance_suite(_write(tmp_path, WELL_FORMED))
    assert rep.findings_validated == 1
    assert rep.violations == [], rep.violations
    assert rep.passing


def test_missing_report_file():
    rep = run_conformance_suite("/no/such/report.md")
    assert not rep.passing
    assert rep.violations[0][1] == "report-missing"


def test_report_with_no_findings(tmp_path):
    rep = run_conformance_suite(_write(tmp_path, "# Just a title\n\nNo findings here.\n"))
    assert not rep.passing
    assert any(r == "no-findings" for _, r, _ in rep.violations)


def test_applyable_true_without_edits_is_flagged(tmp_path):
    text = WELL_FORMED.replace(
        '```json\n    {"applyable": true, "edits": [{"file": "classification.j2", "action": "insert_after", "at_line": 4, "new_content": "check first"}]}\n    ```',
        '```json\n    {"applyable": true, "edits": []}\n    ```',
    )
    rep = run_conformance_suite(_write(tmp_path, text))
    assert not rep.passing
    assert any("structured_edits" in d for _, _, d in rep.violations), rep.violations


def test_applyable_false_without_reason_is_flagged(tmp_path):
    text = WELL_FORMED.replace(
        '{"applyable": true, "edits": [{"file": "classification.j2", "action": "insert_after", "at_line": 4, "new_content": "check first"}]}',
        '{"applyable": false}',
    )
    rep = run_conformance_suite(_write(tmp_path, text))
    assert not rep.passing
    assert any("reason" in d for _, _, d in rep.violations), rep.violations


def test_missing_claim_is_flagged(tmp_path):
    text = WELL_FORMED.replace(
        "**Claim:** The rule exists at classification.j2:44 but is unreachable at\n    decision time because it sits below the signal lists.",
        "",
    )
    rep = run_conformance_suite(_write(tmp_path, text))
    assert not rep.passing
    assert any(r == "finding-schema" and "claim" in d for _, r, d in rep.violations)


def test_bare_range_citation_is_a_d4_violation(tmp_path):
    text = WELL_FORMED.replace(
        "- classification.j2:10: the bug signal list",
        "- the timeout entry at `:43-44` in the error catalog",
    )
    rep = run_conformance_suite(_write(tmp_path, text))
    assert any(r == "citation-precision" for _, r, _ in rep.violations), rep.violations
    assert not rep.passing


# ---- direct extraction-seam unit tests --------------------------------------


def _finding(md):
    return parse_report(textwrap.dedent(md).lstrip("\n")).findings[0]


def test_extract_file_line_and_virtual_artifact():
    f = _finding(
        """
        ### Hypothesis 1: x (Layer 2)
        **Claim:** c
        **Evidence:**
        - docs/quickstart.md:21-30: the run block
        - error catalog:`17-18`: the MISSING_AGENT_ID entry
        **How to verify:** v
        ## What this report is NOT
        """
    )
    items, viol = _extract_evidence(f, _segments(f.body), None)
    types = {i["type"] for i in items}
    assert "file_line" in types and "virtual_artifact" in types
    fl = next(i for i in items if i["type"] == "file_line")
    assert fl == {"type": "file_line", "file": "docs/quickstart.md", "line_start": 21, "line_end": 30}
    va = next(i for i in items if i["type"] == "virtual_artifact")
    assert va == {"type": "virtual_artifact", "artifact": "error catalog", "reference": "17-18"}
    assert viol == []


def test_extract_trace_reference_pairs_dev_with_traces():
    f = _finding(
        """
        ### Finding 1: stall (Layer 1)
        **Pattern claim:** c
        **Trace evidence:**
        - dev_b2k7 succeeds then fails: traces:37–44, then polls traces:45-47
        **Cohort prevalence:** 1 of 5 developers; 12 of 200 calls
        **How to verify:** v
        ## What this report is NOT
        """
    )
    items, _ = _extract_evidence(f, _segments(f.body), None)
    traces = [i for i in items if i["type"] == "trace_reference"]
    assert traces, items
    assert all(i["developer_id"] == "dev_b2k7" for i in traces)
    assert [37, 38, 39, 40, 41, 42, 43, 44] in [i["traces"] for i in traces]
    assert any(i["type"] == "data_reference" and i["schema"] == "cohort_prevalence" for i in items)


def test_extract_dropoff_signal_data_reference():
    f = _finding(
        """
        ### Hypothesis 1: x (Layer 3)
        **Claim:** c
        **Evidence:**
        - docs/quickstart.md:21-30: the block
        - Dropoff signal: 31% `MISSING_AGENT_ID` with median 4 calls before quit
        **How to verify:** v
        ## What this report is NOT
        """
    )
    items, _ = _extract_evidence(f, _segments(f.body), None)
    dr = [i for i in items if i["type"] == "data_reference" and i["schema"] == "dropoff_signal"]
    assert dr, items
    assert dr[0]["key"] == "MISSING_AGENT_ID"
    assert "31%" in dr[0]["value"]


def test_eval_reference_attached_from_report_header(tmp_path):
    # A finding whose only inline evidence is prose still gets the eval anchor.
    text = """
        # Hypothesis report: demo / issue 9
        ## Failure summary
        - Scenario: issue 9
        - Expected: `unknown`
        - Predicted: `bug` (confidence 0.7)
        ## Hypotheses
        ### Hypothesis 1: a theory (Layer 1)
        **Claim:** the eval expected answer is itself wrong.
        **Evidence:**
        - the documented calibration band permits 0.7 here
        **Proposed change:** widen the band.
        ```json
        {"applyable": false, "reason": "changing the eval's expected answer is upstream of any file edit"}
        ```
        **How to verify:** re-score; scenario passes.
        ## What this report is NOT
        - x
    """
    rep = run_conformance_suite(_write(tmp_path, text))
    assert rep.findings_validated == 1
    assert rep.passing, rep.violations  # eval_reference satisfies the evidence floor
