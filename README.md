# agent-diagnosis-spec

This spec captures the structural opinions that make agent-diagnosis tools'
outputs trustworthy. agent-researcher, funnel-researcher, and
integration-watcher were the first three reference implementations; pluma
was the first orchestrator.

It is not documentation about those tools. It is a **standard**: the JSON
Schemas are normative, the conformance suite is normative, and the prose in
`spec/v0.1/SPEC.md` is the reference reading that explains the model the
schemas encode. The spec was reverse-derived from four independently-built
tools — the shape they converged on without coordinating is the evidence
that the opinions here are load-bearing rather than incidental.

## What the spec governs

- **The Finding object.** What one unit of diagnosis is: a ranked,
  evidence-grounded theory localized to exactly one causal layer, carrying
  either a machine-applyable edit or an honest declaration that the fix is
  not an in-place edit.
- **The four-layer model.** Every cause lives in exactly one of four
  abstract layers — the measurement instrument, the machine-readable
  interface, the context delivered at decision time, or the
  sequence/architecture. The spec mandates the *model*, not just a `layer`
  field; each tool instantiates the four layers for its domain.
- **The structured-edit format.** Four actions (`replace`, `insert_after`,
  `delete`, `move`), a verbatim pre-image guard that makes a stale citation
  fail closed instead of corrupting a file, and an honest applyability
  boundary.
- **Evidence.** A five-variant tagged union (`file_line`,
  `virtual_artifact`, `trace_reference`, `data_reference`,
  `eval_reference`) with a minimum-credibility floor: every Finding carries
  at least one independently verifiable evidence item.
- **Grounding principles.** Chief among them: evidence must *affirmatively*
  support the claim — the existence of a rule does not prove its absence.

## Repository layout

```
spec/v0.1/
  SPEC.md                     prose specification (12 sections)
  finding.schema.json         normative Finding schema (draft-07)
  structured-edit.schema.json normative StructuredEdit schema (draft-07)
src/agent_diagnosis_spec/
  parser.py                   vendored minimal report parser
  schemas.py                  schema loader
  validators.py               validate_finding / validate_structured_edit
  conformance.py              run_conformance_suite (Phase 3 wires the suite)
tests/                        conformance + validator tests (Phase 3)
```

The Python package vendors a ~60-line parser so the spec is self-contained
and does not depend on pluma — which would be circular, since pluma
references the spec.

## Usage

```python
from agent_diagnosis_spec import validate_finding, validate_structured_edit

result = validate_finding(finding_dict)
if not result.valid:
    for err in result.errors:
        print(err)
```

`jsonschema>=4.18` is the only runtime dependency.

## Conformance

A tool conforms if its diagnosis output validates against the schemas,
satisfies the grounding principles, and passes the conformance suite. The
suite runs against the canonical reference outputs of agent-researcher,
funnel-researcher, and integration-watcher. If a canonical output fails, the
failure is triaged — tighten the tool or loosen the spec; reality drives the
call, not the spec's prior. 39 tests; all three canonical examples pass.

During initial conformance testing the suite caught a citation-precision
issue in one of the canonical reference reports — a bare-range citation that
relied on prose context to identify its file, which SPEC §7 (lock D4)
forbids. The fix was a one-line qualification at source
([integration-watcher@ef394aa](https://github.com/ivaylogb/integration-watcher/commit/ef394aa3b178acb87313fdcd006a93054d02a564)).
The spec is doing real work.

## Status

**v0.1 — experimental.** Breaking changes are expected and will be
versioned (`spec/v0.1/SPEC.md` §12). Build against a pinned `v0.x`. The
Pluma cross-tool report shape is out of scope for v0.1.

## Reference implementations

- [agent-researcher](https://github.com/ivaylogb/agent-researcher) — agent
  eval-failure diagnosis. L1 = Evaluation.
- [funnel-researcher](https://github.com/ivaylogb/funnel-researcher) —
  developer-funnel dropoff diagnosis. L1 = Funnel definition.
- [integration-watcher](https://github.com/ivaylogb/integration-watcher) —
  API-trace cohort pattern diagnosis. L1 = Trace definition.
- [pluma](https://github.com/ivaylogb/pluma) — orchestrator and consumer;
  normalizes per-tool outputs into the Finding shape and cross-correlates
  across tools.

## License

MIT — see `LICENSE`.
