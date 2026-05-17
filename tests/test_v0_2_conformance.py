"""v0.2 input-schema conformance.

Drives scripts/validate_v0.2.py (loaded by path; its filename carries a dot
and is not a normal module name). Every authored example MUST validate. The
Pluma golden is a read-only sibling repo: it MUST validate when present and
is skipped when absent, mirroring tests/test_canonical_examples.py.
"""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_VALIDATOR = ROOT / "scripts" / "validate_v0.2.py"

_spec = importlib.util.spec_from_file_location("validate_v0_2", _VALIDATOR)
validate_v0_2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validate_v0_2)


def _results():
    return {label: (status, errors) for label, status, errors in validate_v0_2.run()}


@pytest.mark.parametrize(
    "label",
    [
        "examples/v0.2/minimal-failing-eval-container.json",
        "examples/v0.2/full-failing-eval-container.json",
        "examples/v0.2/failing-eval-single.json",
    ],
)
def test_example_fixture_conforms(label):
    status, errors = _results()[label]
    assert status == "PASS", f"{label}: {errors}"


def test_pluma_golden_conforms_when_present():
    label = "pluma golden (braintrust/fixtures/failing_evals.json)"
    status, errors = _results()[label]
    if status == "SKIP":
        pytest.skip(f"{label} not present (standalone checkout)")
    assert status == "PASS", f"{label}: {errors}"


def test_validator_exit_code_is_zero_when_all_present_pass():
    # main() returns the process exit code; 0 iff no FAIL among present targets.
    assert validate_v0_2.main() == 0
