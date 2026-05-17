#!/usr/bin/env python3
"""v0.2 input-schema conformance validator.

Validates the v0.2 example fixtures (and, when present, Pluma's committed
Braintrust golden) against the normative v0.2 input schemas:

  examples/v0.2/minimal-failing-eval-container.json  -> failing-eval-container
  examples/v0.2/full-failing-eval-container.json     -> failing-eval-container
  examples/v0.2/failing-eval-single.json             -> failing-eval
  <pluma>/.../braintrust/fixtures/failing_evals.json -> failing-eval-container

failing-eval-container.schema.json $refs failing-eval.schema.json by a
relative reference; both schemas are registered in a ``referencing`` registry
by their ``$id`` so the cross-reference resolves via base-URI resolution
without network access. This mirrors the v0.1 validator's pattern
(src/agent_diagnosis_spec/validators.py).

Exit status: 0 if every present target validates, 1 otherwise.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft7Validator
from jsonschema.exceptions import best_match
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = ROOT / "spec" / "v0.2"
EXAMPLES_DIR = ROOT / "examples" / "v0.2"

# Pluma's committed Braintrust golden — a sibling repo, read-only. Absent in a
# standalone checkout; validated when present (HARD GUARDRAIL: this MUST pass).
PLUMA_GOLDEN = (
    ROOT.parent
    / "pluma"
    / "src"
    / "pluma"
    / "integrations"
    / "braintrust"
    / "fixtures"
    / "failing_evals.json"
)


def _registry() -> Registry:
    """Register both v0.2 schemas by ``$id`` for relative-$ref resolution."""
    resources = []
    for name in ("failing-eval.schema.json", "failing-eval-container.schema.json"):
        schema = json.loads((SCHEMA_DIR / name).read_text())
        resources.append((schema["$id"], Resource.from_contents(schema)))
    return Registry().with_resources(resources)


def _load_schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text())


def _format_error(err) -> str:
    """Descend into oneOf/anyOf context for an actionable message."""
    if err.context:
        sub = best_match(err.context)
        if sub is not None:
            return _format_error(sub)
    location = "/".join(str(p) for p in err.absolute_path)
    where = f" at /{location}" if location else ""
    return f"{err.message}{where}"


def _validate(instance, schema: dict, registry: Registry) -> list[str]:
    validator = Draft7Validator(schema, registry=registry)
    errors = sorted(
        validator.iter_errors(instance), key=lambda e: list(e.absolute_path)
    )
    return [_format_error(e) for e in errors]


# (label, path, schema-file). Order is the report order.
def _targets() -> list[tuple[str, Path, str]]:
    return [
        (
            "examples/v0.2/minimal-failing-eval-container.json",
            EXAMPLES_DIR / "minimal-failing-eval-container.json",
            "failing-eval-container.schema.json",
        ),
        (
            "examples/v0.2/full-failing-eval-container.json",
            EXAMPLES_DIR / "full-failing-eval-container.json",
            "failing-eval-container.schema.json",
        ),
        (
            "examples/v0.2/failing-eval-single.json",
            EXAMPLES_DIR / "failing-eval-single.json",
            "failing-eval.schema.json",
        ),
        (
            "pluma golden (braintrust/fixtures/failing_evals.json)",
            PLUMA_GOLDEN,
            "failing-eval-container.schema.json",
        ),
    ]


def run() -> list[tuple[str, str, list[str]]]:
    """Validate every target.

    Returns a list of (label, status, errors) where status is one of
    PASS / FAIL / SKIP. SKIP is only used for an absent sibling-repo golden.
    """
    registry = _registry()
    schema_cache: dict[str, dict] = {}
    out: list[tuple[str, str, list[str]]] = []
    for label, path, schema_name in _targets():
        if not path.is_file():
            out.append((label, "SKIP", [f"not present: {path}"]))
            continue
        schema = schema_cache.setdefault(schema_name, _load_schema(schema_name))
        instance = json.loads(path.read_text())
        errors = _validate(instance, schema, registry)
        out.append((label, "PASS" if not errors else "FAIL", errors))
    return out


def main() -> int:
    results = run()
    print(f"v0.2 conformance — schemas: {SCHEMA_DIR}")
    failed = False
    for label, status, errors in results:
        print(f"  [{status}] {label}")
        if status == "FAIL":
            failed = True
            for e in errors:
                print(f"           - {e}")
        elif status == "SKIP":
            for e in errors:
                print(f"           ({e})")
    print("RESULT:", "FAIL" if failed else "PASS")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
