"""Load the normative v0.1 JSON Schemas into Python.

The schemas under ``spec/v0.1/`` are the normative artifacts; this module is
just the loader + a small cross-reference store so finding.schema.json's
``$ref`` to structured-edit.schema.json resolves.

Spec-directory resolution order:
  1. ``AGENT_DIAGNOSIS_SPEC_DIR`` env var (points at the ``spec/`` root).
  2. A packaged ``_spec`` dir shipped inside the wheel (see pyproject
     force-include), if present.
  3. A repo-root walk from this file (the expected mode for v0.1, which is a
     spec repo run from a checkout / editable install).
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

SPEC_VERSION = "0.1"

FINDING_SCHEMA_ID = (
    "https://ivaylogb.github.io/agent-diagnosis-spec/v0.1/finding.schema.json"
)
STRUCTURED_EDIT_SCHEMA_ID = (
    "https://ivaylogb.github.io/agent-diagnosis-spec/v0.1/structured-edit.schema.json"
)


def _candidate_spec_roots() -> list[Path]:
    roots: list[Path] = []
    env = os.environ.get("AGENT_DIAGNOSIS_SPEC_DIR")
    if env:
        roots.append(Path(env))
    here = Path(__file__).resolve()
    # Packaged location (wheel force-include maps spec/ -> _spec/).
    roots.append(here.parent / "_spec")
    # Repo-root walk: find a parent containing spec/v0.1/finding.schema.json.
    for parent in here.parents:
        roots.append(parent / "spec")
    return roots


@lru_cache(maxsize=1)
def spec_dir() -> Path:
    """Absolute path to ``spec/v0.1`` containing the normative schemas."""
    for root in _candidate_spec_roots():
        candidate = root / f"v{SPEC_VERSION}"
        if (candidate / "finding.schema.json").is_file():
            return candidate
    raise FileNotFoundError(
        "Could not locate spec/v0.1/finding.schema.json. Set "
        "AGENT_DIAGNOSIS_SPEC_DIR to the directory containing v0.1/."
    )


def _load(name: str) -> dict[str, Any]:
    return json.loads((spec_dir() / name).read_text())


@lru_cache(maxsize=1)
def load_finding_schema() -> dict[str, Any]:
    """The normative Finding schema (draft-07)."""
    return _load("finding.schema.json")


@lru_cache(maxsize=1)
def load_structured_edit_schema() -> dict[str, Any]:
    """The normative StructuredEdit schema (draft-07)."""
    return _load("structured-edit.schema.json")


def schema_store() -> dict[str, dict[str, Any]]:
    """Map of ``$id`` -> schema, for cross-``$ref`` resolution."""
    return {
        FINDING_SCHEMA_ID: load_finding_schema(),
        STRUCTURED_EDIT_SCHEMA_ID: load_structured_edit_schema(),
    }
