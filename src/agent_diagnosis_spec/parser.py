"""Minimal, vendored diagnosis-report parser (lock D5).

This is the spec's own copy of the normative parsing contract: the entity
header regex, the fenced ```json detection, and the H2 boundary that bounds
the last Finding's body. It is deliberately ~self-contained so the spec
package has no dependency on pluma — which would be circular, since pluma
references the spec. pluma's normalize.py MAY later be refactored to import
from here; that is a future ergonomic improvement, not v0.1 scope.

Scope: this parser splits a *sister-tool* diagnosis report into per-Finding
sections and extracts the structured-edit JSON block. It does NOT parse
pluma's cross-tool report shape (out of scope for v0.1, lock D1), and it
does NOT extract structured EvidenceItems from prose — that domain-specific
step is the conformance harness's job (Phase 3).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional

# `### Hypothesis 1: ...` or `### Finding 1: ...` (case-insensitive).
ENTITY_HEADER_RE = re.compile(
    r"^###\s+(Hypothesis|Finding)\s+(\d+)\s*:?\s*(.*?)\s*$",
    re.MULTILINE | re.IGNORECASE,
)
# First fenced ```json block inside a section.
JSON_FENCE_RE = re.compile(r"```json\s*\n(.*?)\n```", re.DOTALL)
# An h2 boundary: a line starting with exactly `## ` (not `###`). Trailing
# meta sections (e.g. `## What this report is NOT`) bound the last Finding's
# body — it must stop there, not run to EOF.
H2_BOUNDARY_RE = re.compile(r"^##(?!#)", re.MULTILINE)
LAYER_RE = re.compile(r"\(Layer\s+(\d+)\)", re.IGNORECASE)
TOP_TITLE_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


@dataclass
class ParsedFinding:
    """One Finding section, structurally extracted (no evidence parsing)."""

    index: int
    id: str  # origin-prefix + index, e.g. "H1" / "F1"
    term: str  # "Hypothesis" | "Finding" (verbatim from the header)
    title: str  # header title with the trailing "(Layer N)" stripped
    layer: Optional[int]  # parsed from "(Layer N)" in the header, if present
    body: str  # full markdown body of the section, verbatim
    structured_edit: Optional[dict[str, Any]] = None  # parsed first json block
    structured_edit_error: Optional[str] = None  # set if the block is invalid JSON


@dataclass
class ParsedReport:
    """The structural view of a diagnosis report."""

    title: str
    findings: list[ParsedFinding] = field(default_factory=list)


def parse_report(markdown: str) -> ParsedReport:
    """Split a sister-tool diagnosis report into structural Findings."""
    title_m = TOP_TITLE_RE.search(markdown)
    report_title = title_m.group(1).strip() if title_m else "(untitled)"

    headers = list(ENTITY_HEADER_RE.finditer(markdown))
    findings: list[ParsedFinding] = []
    for idx, h in enumerate(headers):
        term = h.group(1)
        number = int(h.group(2))
        raw_title = h.group(3).strip()

        body_start = h.end()
        next_header_start = (
            headers[idx + 1].start() if idx + 1 < len(headers) else len(markdown)
        )
        body_end = next_header_start
        h2 = H2_BOUNDARY_RE.search(markdown, body_start, next_header_start)
        if h2 is not None:
            body_end = h2.start()
        body = markdown[body_start:body_end].strip("\n")

        layer_m = LAYER_RE.search(raw_title)
        layer = int(layer_m.group(1)) if layer_m else None
        clean_title = LAYER_RE.sub("", raw_title).rstrip(" ()").strip()

        prefix = "F" if term.lower() == "finding" else "H"
        edit, edit_err = _extract_structured_edit(body)
        findings.append(
            ParsedFinding(
                index=number,
                id=f"{prefix}{number}",
                term=term,
                title=clean_title,
                layer=layer,
                body=body,
                structured_edit=edit,
                structured_edit_error=edit_err,
            )
        )
    return ParsedReport(title=report_title, findings=findings)


def _extract_structured_edit(
    body: str,
) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    """Return (parsed first json block, error). Both None if no block."""
    m = JSON_FENCE_RE.search(body)
    if m is None:
        return None, None
    try:
        obj = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        return None, f"structured-edit block is not valid JSON: {e}"
    if not isinstance(obj, dict):
        return None, f"structured-edit block must be a JSON object, got {type(obj).__name__}"
    return obj, None
