"""agent-diagnosis-spec — JSON Schema, prose spec, and conformance harness
for agent-diagnostic tool outputs. v0.1 (experimental)."""

from __future__ import annotations

from .conformance import ConformanceReport, run_conformance_suite
from .parser import ParsedFinding, ParsedReport, parse_report
from .schemas import (
    SPEC_VERSION,
    load_finding_schema,
    load_structured_edit_schema,
)
from .validators import (
    ValidationResult,
    validate_finding,
    validate_structured_edit,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "SPEC_VERSION",
    "parse_report",
    "ParsedReport",
    "ParsedFinding",
    "load_finding_schema",
    "load_structured_edit_schema",
    "ValidationResult",
    "validate_finding",
    "validate_structured_edit",
    "ConformanceReport",
    "run_conformance_suite",
]
