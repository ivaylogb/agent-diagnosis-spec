"""Conformance harness.

Parses a sister-tool diagnosis report (vendored parser, lock D5), maps each
Finding's prose into a typed Finding dict, validates it against the normative
schemas, and reports per-Finding violations.

The load-bearing part is the prose -> typed EvidenceItem extraction
(``_extract_evidence``). Per lock D4, citations that do not cleanly map to
one of the five evidence variants surface as conformance failures, not silent
passes — the harness does not force a fit.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .parser import ParsedFinding, ParsedReport, parse_report
from .validators import validate_finding

# (finding_id, rule, human-readable description)
Violation = tuple[str, str, str]

_DASH = r"[-–—]"  # ASCII hyphen, en-dash, em-dash

# A real file citation: a filename WITH an extension, then :N or :N-M.
_FILE_LINE_RE = re.compile(
    r"(?<![\w./-])([\w./-]+\.[A-Za-z0-9]+):(\d+)(?:\s*" + _DASH + r"\s*(\d+))?"
)
# Known virtual artifacts (no real filename). Reference is the range token.
_VIRTUAL_NAMES = ("error catalog", "openapi")
_VIRTUAL_RE = re.compile(
    r"\b(error catalog|openapi)\b\s*:\s*`?\s*(\d+(?:\s*" + _DASH + r"\s*\d+)?)\s*`?",
    re.IGNORECASE,
)
# D4: the specific bare-range idiom — backtick, colon, digits, no filename.
_BARE_RANGE_RE = re.compile(r"`\s*:\s*\d+(?:\s*" + _DASH + r"\s*\d+)?\s*`")
_DEV_ID_RE = re.compile(r"\bdev_[A-Za-z0-9]+\b")
_TRACE_RE = re.compile(r"\btraces?:\s*(\d+)(?:\s*" + _DASH + r"\s*(\d+))?")
_ALLCAPS_RE = re.compile(r"\b([A-Z][A-Z0-9_]{3,})\b")
_BOLD_LABEL_RE = re.compile(r"\*\*\s*([A-Za-z][A-Za-z /]*?)\s*:\*\*")
_SCENARIO_RE = re.compile(r"^[-*]\s*Scenario:\s*(.+?)\s*$", re.MULTILINE)
_EXPECTED_RE = re.compile(r"^[-*]\s*Expected:\s*(.+?)\s*$", re.MULTILINE)
_PREDICTED_RE = re.compile(r"^[-*]\s*Predicted:\s*(.+?)\s*$", re.MULTILINE)

_EVIDENCE_LABELS = {"evidence", "trace evidence", "product evidence"}
_CLAIM_LABELS = {"claim", "pattern claim"}
_VERIFY_LABELS = {"how to verify", "verification"}


@dataclass
class ConformanceReport:
    """Per-report conformance outcome."""

    source: str
    findings_validated: int = 0
    violations: list[Violation] = field(default_factory=list)

    @property
    def passing(self) -> bool:
        return self.findings_validated > 0 and not self.violations

    def __bool__(self) -> bool:
        return self.passing


# --------------------------------------------------------------------------
# Prose segmentation
# --------------------------------------------------------------------------


def _segments(body: str) -> dict[str, str]:
    """Split a Finding body into {bold-label-lower: text} segments."""
    labels = list(_BOLD_LABEL_RE.finditer(body))
    out: dict[str, str] = {}
    for i, m in enumerate(labels):
        key = m.group(1).strip().lower()
        start = m.end()
        end = labels[i + 1].start() if i + 1 < len(labels) else len(body)
        out.setdefault(key, body[start:end].strip())
    return out


def _strip_ticks(s: str) -> str:
    return s.strip().strip("`").strip()


def _expand(start: int, end: Optional[int]) -> list[int]:
    if end is None or end == start:
        return [start]
    lo, hi = (start, end) if start <= end else (end, start)
    return list(range(lo, hi + 1))


# --------------------------------------------------------------------------
# Evidence extraction (the lock-D4 seam)
# --------------------------------------------------------------------------


def _report_eval_reference(markdown: str) -> Optional[dict[str, Any]]:
    """agent-researcher's primary anchor lives in the report header."""
    s = _SCENARIO_RE.search(markdown)
    e = _EXPECTED_RE.search(markdown)
    p = _PREDICTED_RE.search(markdown)
    if not (s and e and p):
        return None
    scenario = _strip_ticks(s.group(1))
    expected = _strip_ticks(e.group(1))
    observed = _strip_ticks(p.group(1).split("(")[0])
    if not (scenario and expected and observed):
        return None
    return {
        "type": "eval_reference",
        "scenario_id": scenario,
        "expected": expected,
        "observed": observed,
    }


def _extract_evidence(
    finding: ParsedFinding,
    segments: dict[str, str],
    report_eval_ref: Optional[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[Violation]]:
    """Map a Finding's prose into typed EvidenceItems.

    Returns (evidence_items, violations). Violations carry the lock-D4
    failures: citations that do not map to any of the five variants.
    """
    items: list[dict[str, Any]] = []
    violations: list[Violation] = []
    seen: set[str] = set()

    def add(item: dict[str, Any]) -> None:
        key = repr(sorted(item.items()))
        if key not in seen:
            seen.add(key)
            items.append(item)

    evidence_text = "\n".join(
        text for label, text in segments.items() if label in _EVIDENCE_LABELS
    )

    # 1. file_line — concrete filename + line range.
    for m in _FILE_LINE_RE.finditer(evidence_text):
        file, start = m.group(1), int(m.group(2))
        end = int(m.group(3)) if m.group(3) else start
        add({"type": "file_line", "file": file, "line_start": start, "line_end": end})

    # 2. virtual_artifact — known virtual name + range token.
    for m in _VIRTUAL_RE.finditer(evidence_text):
        artifact = m.group(1).lower()
        reference = re.sub(r"\s+", "", m.group(2))
        add({"type": "virtual_artifact", "artifact": artifact, "reference": reference})

    # 3. trace_reference — dev id + trace ordinals, paired by proximity.
    dev_ids = list(_DEV_ID_RE.finditer(evidence_text))
    for tm in _TRACE_RE.finditer(evidence_text):
        prior = [d for d in dev_ids if d.start() < tm.start()]
        if not prior:
            continue  # a trace ordinal with no owning developer is not usable
        dev = prior[-1].group(0)
        start = int(tm.group(1))
        end = int(tm.group(2)) if tm.group(2) else None
        add(
            {
                "type": "trace_reference",
                "traces": _expand(start, end),
                "developer_id": dev,
            }
        )

    # 4. data_reference — labelled dropoff signals + the cohort-prevalence field.
    for line in evidence_text.splitlines():
        s = line.strip().lstrip("-* ").strip()
        if re.match(r"(?i)dropoff signal\s*:", s):
            payload = s.split(":", 1)[1].strip()
            code = _ALLCAPS_RE.search(payload)
            add(
                {
                    "type": "data_reference",
                    "schema": "dropoff_signal",
                    "key": code.group(1) if code else "signal",
                    "value": payload or "(unspecified)",
                }
            )
    cohort = segments.get("cohort prevalence")
    if cohort:
        flat = re.sub(r"\s+", " ", cohort).strip()
        code = _ALLCAPS_RE.search(flat)
        add(
            {
                "type": "data_reference",
                "schema": "cohort_prevalence",
                "key": code.group(1) if code else "prevalence",
                "value": flat[:500],
            }
        )

    # 5. eval_reference — report-level anchor, attached to every Finding.
    if report_eval_ref is not None:
        add(report_eval_ref)

    # D4: bare-range citations (backtick-colon-digits, no filename) are not
    # spec-compliant. Surface, do not silently absorb.
    for bm in _BARE_RANGE_RE.finditer(evidence_text):
        violations.append(
            (
                finding.id,
                "citation-precision",
                f"bare-range citation {bm.group(0)!r} has no filename and is not a "
                "known virtual artifact (SPEC §7, lock D4)",
            )
        )

    if not items:
        violations.append(
            (
                finding.id,
                "evidence-missing",
                "no typed evidence item could be extracted from the Finding body",
            )
        )
    return items, violations


# --------------------------------------------------------------------------
# Finding-dict assembly + structured-edit pre-checks
# --------------------------------------------------------------------------


def _structured_edit_prechecks(f: ParsedFinding) -> tuple[Optional[dict], list[Violation]]:
    """Return (block, violations) for issues that block dict assembly."""
    v: list[Violation] = []
    if f.structured_edit_error:
        return None, [(f.id, "structured-edit-json", f.structured_edit_error)]
    block = f.structured_edit
    if block is None:
        return None, [(f.id, "structured-edit-missing", "no fenced ```json block")]
    if "applyable" not in block:
        return block, [(f.id, "applyable-missing", "structured-edit block has no 'applyable' field")]
    if not isinstance(block["applyable"], bool):
        return block, [(f.id, "applyable-type", f"'applyable' must be boolean, got {block['applyable']!r}")]
    return block, v


def _build_finding_dict(
    f: ParsedFinding, segments: dict[str, str], evidence: list[dict[str, Any]], block: Optional[dict]
) -> dict[str, Any]:
    fd: dict[str, Any] = {"id": f.id, "title": f.title, "evidence": evidence}
    if f.layer is not None:
        fd["layer"] = f.layer
    claim = next((segments[k] for k in segments if k in _CLAIM_LABELS), None)
    if claim:
        fd["claim"] = claim.strip()
    verify = next((segments[k] for k in segments if k in _VERIFY_LABELS), None)
    if verify:
        fd["verification"] = verify.strip()
    if isinstance(block, dict) and isinstance(block.get("applyable"), bool):
        fd["applyable"] = block["applyable"]
        if block["applyable"] is True and isinstance(block.get("edits"), list):
            fd["structured_edits"] = block["edits"]
        if block["applyable"] is False and block.get("reason") is not None:
            fd["reason"] = str(block["reason"])
    return fd


def run_conformance_suite(report_markdown_path: str | Path) -> ConformanceReport:
    """Run conformance against one diagnosis report."""
    path = Path(report_markdown_path)
    report = ConformanceReport(source=str(path))
    if not path.is_file():
        report.violations.append(("-", "report-missing", f"no such file: {path}"))
        return report

    markdown = path.read_text()
    parsed: ParsedReport = parse_report(markdown)
    if not parsed.findings:
        report.violations.append(("-", "no-findings", "report contained no parseable Findings"))
        return report

    eval_ref = _report_eval_reference(markdown)

    for f in parsed.findings:
        report.findings_validated += 1
        segments = _segments(f.body)

        block, block_v = _structured_edit_prechecks(f)
        report.violations.extend(block_v)

        evidence, ev_v = _extract_evidence(f, segments, eval_ref)
        report.violations.extend(ev_v)

        fd = _build_finding_dict(f, segments, evidence, block)
        result = validate_finding(fd)
        if not result.valid:
            for err in result.errors:
                report.violations.append((f.id, "finding-schema", err))

    return report


__all__ = ["ConformanceReport", "run_conformance_suite", "Violation"]
