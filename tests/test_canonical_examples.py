"""Conformance against the three canonical reference outputs.

These tests CAN fail — that is the methodology gate (SPEC §3). A failure is
triaged (tighten the source tool or loosen the spec), never silently passed.
The assertion message dumps every violation so the triage is concrete.
"""

import pytest

from conftest import CANONICAL
from agent_diagnosis_spec import run_conformance_suite


@pytest.mark.parametrize("tool", sorted(CANONICAL))
def test_canonical_example_conforms(tool):
    path = CANONICAL[tool]
    if not path.is_file():
        pytest.skip(f"canonical example not found: {path}")

    rep = run_conformance_suite(path)

    assert rep.findings_validated > 0, f"{tool}: parser found no Findings in {path}"

    detail = "\n".join(
        f"  [{fid}] {rule}: {desc}" for fid, rule, desc in rep.violations
    )
    assert rep.passing, (
        f"\n{tool} ({path.name}) — {rep.findings_validated} findings, "
        f"{len(rep.violations)} violation(s):\n{detail}"
    )


@pytest.mark.parametrize("tool", sorted(CANONICAL))
def test_canonical_example_parses_expected_finding_count(tool):
    path = CANONICAL[tool]
    if not path.is_file():
        pytest.skip(f"canonical example not found: {path}")
    rep = run_conformance_suite(path)
    # All three reference reports emit 2-3 ranked Findings (SPEC §4).
    assert 2 <= rep.findings_validated <= 3, (
        f"{tool}: expected 2-3 Findings, parser saw {rep.findings_validated}"
    )
