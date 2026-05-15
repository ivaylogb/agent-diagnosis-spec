# Agent Diagnosis Spec — v0.1

**Status:** Experimental. Breaking changes expected. See §2 and §12.

This document is the prose specification. Where prose and the JSON Schemas
disagree, **the JSON Schemas are normative** (`finding.schema.json`,
`structured-edit.schema.json`). Where the JSON Schemas are silent, **the
conformance suite is normative**. Prose is reference: it explains intent and
the abstract model the schemas encode.

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL
NOT**, **SHOULD**, **SHOULD NOT**, **MAY**, and **OPTIONAL** are to be
interpreted as in RFC 2119.

---

## 1. Abstract

An *agent-diagnosis tool* reads a system that is behaving in an unwanted way,
plus the artifact of record that *declared* the behavior unwanted (an eval
verdict, a funnel's dropoff data, a cohort's API traces), and emits a
structured **diagnosis**: a small set of ranked, evidence-grounded
**Findings**, each localized to exactly one of four causal layers, each
carrying either a machine-applyable edit specification or an honest
declaration that the fix is not an in-place edit.

This spec captures the structural opinions that make those outputs
trustworthy: what a Finding is, what counts as evidence, what a structured
edit is and when one is honestly impossible, the four-layer causal model,
and the grounding discipline that separates a diagnosis from generic
best-practice advice.

A tool conforms to this spec if its diagnosis output validates against the
schemas, satisfies the grounding principles (§8), and passes the conformance
suite (§3).

## 2. Status

This is **v0.1**. It is explicitly experimental.

- The four-layer model, the Finding shape, the structured-edit format, and
  the five-variant evidence union are considered stable enough to build on
  but **not** frozen.
- Breaking changes are expected and will be versioned (§12). A diagnosis is
  always interpreted against a stated spec version.
- The Pluma cross-tool report shape is **out of scope for v0.1**. Pluma is
  documented here as an orchestrator/consumer (§11); a cross-report object
  is a v0.2-or-later conversation.
- Optional evidence sub-fields (e.g. `confidence`, `notes`) are
  extension-point territory and are deliberately **not** part of v0.1.

Treat anything not pinned by a schema or the conformance suite as subject to
change.

## 3. Conformance

A **conforming diagnosis** is a document that, when parsed by the spec's
reference parser (§ `parser.py`), yields one or more Findings, each of which:

1. validates against `finding.schema.json` (draft-07); and
2. whose every structured edit validates against
   `structured-edit.schema.json`; and
3. satisfies the applyability rule (§6.3): `applyable: true` ⇒ a non-empty
   `structured_edits` array; `applyable: false` ⇒ a non-empty `reason`
   string; and
4. carries at least one evidence item (§7); and
5. does not violate the grounding principles (§8) or emit a forbidden
   pattern (§9) — to the extent these are mechanically checkable; the
   non-mechanical parts are conformance *guidance* a reviewer applies.

A **conforming tool** is one whose emitted diagnoses are conforming
diagnoses, and which assigns every Finding to exactly one of the four layers
(§5) using a domain-specific instantiation of the abstract model.

The conformance suite runs against the canonical
reference outputs:

- `agent-researcher` — `examples/issue_107/report.md`
- `funnel-researcher` — `examples/api_activation/diagnosis.md`
- `integration-watcher` — `examples/agent_platform/findings.md`

These three MUST pass. If a canonical reference output fails conformance,
the failure is a signal to be triaged — either the spec is too tight (loosen
the spec) or the reference tool drifted from the shared opinion (tighten the
tool). The conformance run produces a report surfacing every failure;
reality drives the call, not the spec's prior. Pluma's
`cross_pluma/report.md` is a derived artifact and is **not** in the
conformance set for v0.1.

## 4. The Finding object

A **Finding** is the unit of diagnosis. A diagnosis is an ordered list of
2–3 Findings, ranked (by likelihood, or by breadth of impact — the ranking
basis is the tool's, but the order is meaningful).

A Finding has these fields. Normative types and required/optional status are
in `finding.schema.json`; this section is the reference reading.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | string | **REQUIRED** | Stable identifier within the diagnosis. Convention: a single-letter origin prefix + 1-based index (`H1`, `F1`, `D2`). Pattern: `^[A-Za-z]+[0-9]+$`. |
| `title` | string | **REQUIRED** | One line naming the specific theory/pattern. Not a restatement of the symptom. The `(Layer N)` annotation, if present in source, is lifted into `layer` and stripped from `title`. |
| `layer` | integer 1–4 | **REQUIRED** | Exactly one causal layer (§5). A Finding that spans layers has not been decomposed far enough. |
| `claim` | string | **REQUIRED** | 1–2 sentences stating the mechanism — *what* in the system produces the unwanted behavior, not that it occurs. |
| `evidence` | array of EvidenceItem | **REQUIRED**, `minItems: 1` | Verifiable grounding (§7). At least one item; tools MAY require more for their domain. |
| `applyable` | boolean | **REQUIRED** | Whether the proposed change is expressible as a sequence of in-place structured edits (§6). |
| `structured_edits` | array of StructuredEdit | **REQUIRED iff `applyable: true`**, `minItems: 1` | The machine-applyable change (§6). MUST be absent-or-ignored conceptually when `applyable: false`. |
| `reason` | string | **REQUIRED iff `applyable: false`**, non-empty | Why the change cannot be expressed as in-place edits (§6.3). |
| `verification` | string | **REQUIRED** | The falsifiable prediction: which measured quantity moves, by how much, and/or what would prove the Finding wrong. |

The fields `claim`, `evidence`, and `verification` are conceptually distinct
from the markdown prose a tool emits around them; a conforming tool's output
MUST be parseable into these fields. v0.1 does not standardize the prose
layout beyond what the reference parser (§13) requires:
`### {Hypothesis|Finding} N: {title} (Layer N)` headers, a fenced
` ```json ` structured-edit block, and a trailing `## ` section that bounds
the last Finding's body.

v0.1 defines no optional *core* Finding field — the eight named fields are
required or conditionally required, and the only core shape variability is
the applyable/non-applyable branch. A domain tool MAY carry **additional
first-class fields** as extension points (e.g. integration-watcher's cohort
prevalence) without losing conformance: `finding.schema.json` sets
`additionalProperties: true` deliberately. Conformance checks the core; it
does not reject domain extensions, and it does not let a tool rely on an
extension being present.

## 5. The four-layer model

Every Finding **MUST** be assigned to exactly one of four layers. This is
not merely a `layer` tag — the spec mandates the *model*: every conforming
tool localizes causes into these four abstract layers and instantiates them
for its domain.

The abstract model (this framing is tighter than any single reference tool's
prompt; it is the spec's canonical statement):

| Layer | Abstract role | The question it answers |
|---|---|---|
| **L1 — the measurement instrument** | The artifact that *declared the behavior a failure*: the eval, the funnel definition, the trace/cohort framing. | Is the instrument itself correct, or is the "failure" an artifact of how it measured or framed the behavior? |
| **L2 — the machine-readable interface** | Tool/SDK/API surface: definitions, schemas, signatures, error codes, parameter names. | Does the interface hide a precondition, overlap, mis-name, or fail to name the actionable next step? |
| **L3 — context delivered at decision time** | The information that actually reaches the decider *at the moment of the decision*. | Is the right context present where and when the decision is made — not merely present somewhere? |
| **L4 — sequence / runtime architecture** | The order operations happen in and the gates/branches between them. | Is a precondition introduced after its dependent step? Is a needed gate or branch missing? |

Two reframings carry the model across domains:

- **Subject swap.** L2/L3/L4 read "the model" when the diagnosed system is
  an agent, and "the developer" when it is a product integration. The
  abstract role is unchanged.
- **Instrument swap (L1).** L1 names whatever produced the verdict: an eval
  (agent diagnosis), a funnel definition (funnel diagnosis), a trace/cohort
  framing (integration diagnosis).

Reference instantiations:

| | L1 | L2 | L3 | L4 |
|---|---|---|---|---|
| abstract | Measurement instrument | Machine-readable interface | Context at decision time | Sequence / architecture |
| agent-researcher | Evaluation | Tools | Context | Workflow |
| funnel-researcher | Funnel definition | Product API/SDK surface | Docs/Context at decision time | Onboarding sequence |
| integration-watcher | Trace definition | Product API/SDK surface | Docs/Context at decision time | Integration sequence |

**L1 and applyability.** L1 Findings *frequently* declare `applyable:
false`, because the fix is upstream of any file-edit surface (re-cut the
cohort, correct the eval's expected answer, redefine the funnel step). This
is a strong empirical correlation, **not a rule**. A conforming tool and the
conformance suite **MUST NOT** encode "L1 implies non-applyable". An L1
Finding can be applyable (e.g. tightening a calibration band that the eval
depends on is an in-place edit).

A new domain instantiates the model by stating, for each of L1–L4, what the
measurement instrument / interface / decision-time context / sequence *is*
for that domain. It MUST keep four layers and the abstract roles above.

## 6. Structured edits

When a Finding's fix is expressible as in-place edits, it carries a
`structured_edits` array so a downstream applier can make the change without
re-interpreting prose. `structured-edit.schema.json` is normative for the
edit object; this section is the reference reading.

### 6.1 The four actions

There are exactly four actions. Required field sets are the **intersection**
of the three reference appliers (the common wire format; per-applier
hardening such as transactional snapshots or anchor post-passes is
implementation detail, not part of this format):

| action | required fields |
|---|---|
| `replace` | `file`, `from_line_start`, `from_line_end`, `expected_content`, `new_content` |
| `insert_after` | `file`, `at_line`, `new_content` |
| `delete` | `file`, `from_line_start`, `from_line_end`, `expected_content` |
| `move` | `file`, `from_line_start`, `from_line_end`, `to_line`, `expected_content` |

Semantics:

- `replace` — replace lines `from_line_start..from_line_end` (inclusive,
  1-based) with `new_content`.
- `insert_after` — insert `new_content` after line `at_line`. Touches no
  existing content, so no `expected_content`.
- `delete` — delete lines `from_line_start..from_line_end` (inclusive).
- `move` — delete `from_line_start..from_line_end` and re-insert it
  **verbatim** after `to_line`. `move` does not change wording; if the text
  must also change, emit `delete` + `insert_after` instead.

All line numbers refer to the **ORIGINAL** file as presented to the diagnosis
tool, before any edit in the same spec is applied. A tool MUST NOT compute
post-edit line numbers. `from_line_start <= from_line_end` and a `move`'s
`to_line` MUST NOT fall inside `[from_line_start, from_line_end]`; these
arithmetic constraints are enforced by conformance and appliers, not by JSON
Schema.

### 6.2 `expected_content` semantics — the verbatim pre-image

`expected_content` is the literal text currently at the cited range. It is a
**pre-image guard**: an applier compares it byte-for-byte against the live
file and refuses the entire edit set if it does not match —
character-for-character, including indentation, quotes, punctuation, and
trailing whitespace. No paraphrase, normalization, or escape changes. This
is the spec's central trust mechanism: a stale or hallucinated citation
**fails closed** (nothing is written) rather than corrupting a file. See
GP2 (§8).

`expected_content` is REQUIRED for every action that touches existing
content (`replace`, `delete`, `move`). `new_content` is REQUIRED for every
action that writes new content (`replace`, `insert_after`). `move` carries
no `new_content`; it re-inserts its `expected_content` verbatim.

### 6.3 The applyability boundary

`applyable` is a boolean judgment the diagnosing tool MUST make honestly:

- `applyable: true` ⇒ `structured_edits` is **REQUIRED and non-empty**. The
  change is fully expressible as a sequence of the four actions on existing
  files.
- `applyable: false` ⇒ `reason` is **REQUIRED and non-empty**. The change
  cannot be so expressed — e.g. it requires creating a new file, adding a
  new tool/endpoint, a multi-system rename, a cross-cutting refactor, or (a
  common L1 case) a change to the measurement instrument itself that is
  upstream of any file-edit surface.

Layer does **not** determine `applyable` (see §5, and lock D3). A tool
**MUST NOT** stretch the edit format to cover a change it does not fit. An
honest `applyable: false` with a precise `reason` is more useful than a
misleading edit list (GP4, §8).

## 7. Evidence

Every Finding **MUST** carry at least one evidence item: a verifiable
pointer to a source a reader can independently check. `evidence` is an array
with `minItems: 1`. A tool MAY require more than one, or require specific
variants, for its domain (e.g. integration-watcher requires both a trace
reference and a file-line citation per Finding); the spec's floor is one.

Evidence is a **tagged union** of five variants, discriminated by `type`.
The normative shape is in `finding.schema.json`
(`#/definitions/evidenceItem`):

| `type` | required fields | used by (reference) |
|---|---|---|
| `file_line` | `file` (string), `line_start` (int ≥1), `line_end` (int ≥1) | all three |
| `virtual_artifact` | `artifact` (string), `reference` (string) | funnel, integration (error catalog / openapi) |
| `trace_reference` | `traces` (array of int, ≥1), `developer_id` (string) | integration |
| `data_reference` | `schema` (string), `key` (string), `value` (string) | funnel (dropoff signal), integration (cohort prevalence) |
| `eval_reference` | `scenario_id` (string), `expected` (string), `observed` (string) | agent-researcher (primary anchor) |

`eval_reference` exists because an eval verdict — a scenario, its expected
answer, and the observed answer — is agent-researcher's primary credibility
anchor and does not reduce to any of the other four. Optional sub-fields
such as `confidence` or `notes` are extension-point territory and are **not**
part of v0.1; a v0.1-conforming evidence item neither requires nor is
rejected for omitting them.

**Citation precision (lock D4).** A `file_line` item MUST name a concrete
`file`. A bare line range with no filename that relies on surrounding prose
to identify the file is **NOT spec-compliant**: the spec requires citations
to be unambiguous and verifiable without prose interpretation. A source tool
that emits bare ranges will fail conformance; that is the correct signal,
surfaced by the conformance report, not a spec defect. (A genuinely
file-less artifact such as a virtual error catalog is representable as
`virtual_artifact`, not as a fileless `file_line`.)

**Minimum-credibility rule.** A Finding with zero evidence items, or whose
only evidence is unverifiable (no file, no scenario, no trace, no named data
key), is non-conforming regardless of how plausible its prose is.

## 8. Grounding principles

These are elevated above the operational self-check (§10) because they are
the methodology, not a checklist item. All four were observed as shared
discipline across the reference tools.

### GP1 — Evidence affirmatively supports the claim

The existence of a rule does not prove its absence. Cited evidence MUST
*affirmatively* support the claim, not merely sit near it. If the evidence
shows a rule/field/instruction **exists**, the claim MUST NOT be "it is
missing"; the claim must instead explain why the existing thing fails to
take effect (it is buried, contradicted, unreachable at decision time,
out-scoped). This is the single most important shared rule (universal
self-check #6 across all three reference tools) and the most common failure
mode it guards against is citing a rule's *presence* as evidence of its
*absence*. (Lock D6.)

### GP2 — Verbatim pre-image discipline (fail-closed)

A structured edit's `expected_content` MUST reproduce the cited source
byte-for-byte (§6.2). An edit that cannot reproduce its pre-image MUST be
downgraded to `applyable: false` with a `reason` rather than emitted as a
best-effort guess. Diagnosis output is allowed to be wrong about *why*; it
is not allowed to silently corrupt the system it diagnoses.

### GP3 — One cause, one layer, distinct findings

Each Finding localizes a single cause at a single layer. Findings in a
diagnosis MUST be structurally distinct theories: if two would be fixed by
the same edit, they are one Finding. A Finding that spans layers has not
been decomposed far enough.

### GP4 — Honest non-applyability

An honest `applyable: false` with a precise `reason` is more valuable than a
forced or misleading edit list. A tool MUST NOT widen the edit format to
appear actionable.

A new principle is added only when it is genuinely methodology-level and
observed as shared discipline; v0.1 fixes these four.

## 9. Forbidden patterns

A conforming tool MUST NOT emit Findings that pattern-match generic
best-practice advice without grounding. The spec mandates a **universal
core**; domain categories are **extension points** an implementing tool adds
for its own surface.

### 9.1 Universal core (normative — every conforming tool)

1. **Vague, ungrounded "make X better".** ("Make the prompt clearer" / "The
   docs need to be improved.") Forbidden unless it states *what*, *where*,
   and *which mechanism*.
2. **"Add more examples"** with no specifics about which examples or which
   decision they fix.
3. **Symptom-as-cause.** Restating the failure as if it were its cause
   ("the model didn't follow the instruction" / "the developer experience
   is poor").
4. **Psychologize-the-subject.** Anthropomorphizing the diagnosed subject
   instead of naming a structural cause ("the model is confused" /
   "developers are confused"). The lexical subject (model vs developer) is
   the domain instantiation; a purely structural-framing tool may have no
   subject to psychologize, in which case this category is vacuously
   satisfied.

### 9.2 Extension-point categories (a tool adds those that apply)

- **LLM-knob category** (agent-style domains): "lower the temperature",
  "use a stronger model", "add few-shot examples" — presuppose a model with
  sampling knobs/weights.
- **PLG-surface category** (product-funnel domains): "run an A/B test",
  "add a tutorial video", "improve error messages" (without naming which),
  "add analytics tracking" — presuppose an onboarding/growth surface.

A tool documents which extension categories it enforces. The conformance
suite checks the universal core for all tools and a domain category only for
tools that declare it.

## 10. Self-check discipline

A conforming tool SHOULD run a pre-emission self-check. The **universal
subset** below (the intersection of the reference tools' checks; checks 2–8)
is the normative discipline; GP1–GP4 capture the
principle-level members.

1. Every Finding is structurally distinct (collapse-if-same-edit). [GP3]
2. Every Finding is assigned exactly one layer. [GP3]
3. The proposed change is applyable without further interpretation.
4. No forbidden pattern was emitted. [§9]
5. Evidence affirmatively supports the claim, not mere proximity. [GP1]
6. Every citation's line numbers match the source as presented (read the
   prefix; do not count lines); for multi-file domains, the cited file
   matches the artifact the quoted content came from.
7. Every structured edit's `expected_content` matches the source verbatim;
   if it cannot be made verbatim-verifiable, the Finding is downgraded to
   `applyable: false`. [GP2]
8. The Finding carries ≥1 verifiable evidence item of an allowed variant.
   [§7]

Tool-specific checks (e.g. integration-watcher's denominator/percentage
verification, tied to its quantitative cohort-prevalence field) are valid
extensions but are NOT part of the universal subset.

## 11. Reference implementations

These reference implementations
are the source of truth for what the shared opinion *is*; where the spec and
a reference diverge, the divergence is triaged (§3), not assumed to be the
reference's fault.

- **agent-researcher** — diagnoses why an agent failed an eval scenario.
  L1=Evaluation. Primary evidence anchor: `eval_reference`. First reference
  implementation.
- **funnel-researcher** — diagnoses why developers drop off in a product
  funnel. L1=Funnel definition. Evidence: `file_line` + `data_reference`
  (dropoff signal). Second reference implementation.
- **integration-watcher** — diagnoses growth-relevant patterns across a
  cohort's API traces. L1=Trace definition. Evidence: `trace_reference` +
  `file_line`, plus quantitative cohort prevalence. Third reference
  implementation.
- **pluma** — orchestrator and consumer. Normalizes each tool's output into
  a single Finding shape and cross-correlates Findings across tools. The
  cross-tool report is a *derived artifact downstream of conformance* and is
  out of scope for v0.1 (§2); a `CrossReport` object is a v0.2+
  conversation.

Repository links live in `README.md`.

## 12. Versioning and breaking-change policy

- The spec is versioned `MAJOR.MINOR`. v0.1 is the first published version.
- A diagnosis is always interpreted against a declared spec version. Schemas
  live under `spec/v<MAJOR.MINOR>/`.
- While `MAJOR` is `0`, **any** change MAY be breaking; v0.x is a moving
  target by design (§2). Each minor bump ships its own `spec/v0.x/`
  directory; older versions are retained, not rewritten.
- A change is **breaking** if a previously-conforming diagnosis would no
  longer conform (new required field, narrowed type, removed evidence
  variant, changed action semantics). Breaking changes increment the
  version and ship a migration note.
- Additive, backward-compatible changes (new OPTIONAL evidence sub-field, a
  new extension-point category, clarified prose) MAY land within a version
  as editorial revisions, recorded in a changelog.
- The first `1.0` is cut only when the four-layer model, the Finding shape,
  the structured-edit format, and the evidence union have held stable across
  the reference implementations long enough to be worth freezing. Until
  then, build against a pinned `v0.x`.

## 13. Reference parser

The spec ships a normative reference parser (the `parser.py` module of the
`agent_diagnosis_spec` package). It defines the contract a conforming
diagnosis's prose layout MUST satisfy so Findings can be mechanically
extracted. It is deliberately small and vendored so the spec package has no
dependency on any reference implementation (which would be circular).

The parser recognizes exactly three structural markers:

1. **Entity header.** A Finding begins at a Markdown H3 of the form
   `### Hypothesis N: <title>` or `### Finding N: <title>` — the word is
   case-insensitive, the `:` is optional, and `N` is a 1-based integer. The
   origin word (`Hypothesis`/`Finding`) is recorded verbatim; the Finding
   `id` is the single-letter prefix (`H`/`F`) plus `N`. A trailing
   `(Layer N)` in the title is lifted into `layer` and stripped from
   `title`. Regex: `^###\s+(Hypothesis|Finding)\s+(\d+)\s*:?\s*(.*?)\s*$`
   (multiline, case-insensitive).

2. **Structured-edit block.** The first fenced ` ```json ` block inside a
   Finding's body is that Finding's structured-edit spec. Regex:
   `` ```json\s*\n(.*?)\n``` `` (dot-all). It MUST parse to a single JSON
   object.

3. **Body boundary.** A Finding's body runs from its header to the FIRST
   of: the next entity header, the next Markdown H2 (`^## `, not `###`),
   or end-of-document. The H2 rule stops the last Finding's body at a
   trailing meta section such as `## What this report is NOT`. Inter-Finding
   `---` separators are not boundaries — the next `###`/`##` is.

The parser performs no evidence extraction and no domain interpretation:
mapping a Finding body's prose into typed evidence items (§7) is the
conformance harness's responsibility, not the parser's. The parser does not
read Pluma's cross-tool report shape (out of scope for v0.1, §2).
