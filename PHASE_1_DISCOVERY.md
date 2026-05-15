# Phase 1 — Discovery Report

**Scope:** Extract every structural opinion currently implicit across
`agent-researcher`, `funnel-researcher`, `integration-watcher`, and `pluma`.
This document records what exists, where it lives, and where the tools
diverge. **No spec is written here.** This is the input to Phase 2.

**Sources read (14 files):**

| Tool | System prompt | Applier | Agent caller | Example output |
|---|---|---|---|---|
| agent-researcher | `prompts/hypothesis_system.md` (226 ln) | `applier.py` (478 ln) | `hypothesis_agent.py` | `examples/issue_107/report.md` |
| funnel-researcher | `prompts/hypothesis_system.md` (157 ln) | `applier.py` (636 ln) | `hypothesis_agent.py` | `examples/api_activation/diagnosis.md` |
| integration-watcher | `prompts/findings_system.md` (186 ln) | `applier.py` (633 ln) | `findings_agent.py` | `examples/agent_platform/findings.md` |
| pluma | — | — | — | `src/pluma/normalize.py` (339 ln) + `examples/cross_pluma/report.md` |

**One-line orientation.** Three tools each run a single Claude call whose
system prompt forces the model to emit a markdown report of 2–3 ranked
diagnostic entries; each entry carries a machine-readable structured-edit
block. A separate `applier.py` per tool mechanically applies one chosen
entry's edits with a verbatim pre-image check. `pluma` is the orchestrator:
it parses each tool's markdown into a single normalized `Finding` dataclass
and cross-correlates findings across tools. The three system prompts and the
three appliers are near-clones with deliberate, traceable divergences. The
shape they all converge on is the latent specification this repo will
externalize.

---

## 1. Finding object shape

There is no literal JSON "finding object" emitted by the tools. The finding
is a **markdown sub-section** with a fixed set of labelled fields, mandated
by each system prompt's "Output structure". `pluma`'s `normalize.py` is the
only place a finding becomes an actual typed object — the `Finding`
dataclass. The table maps each conceptual field across all four.

| Conceptual field | agent-researcher (Hypothesis) | funnel-researcher (Hypothesis) | integration-watcher (Finding) | pluma `Finding` dataclass (normalized) |
|---|---|---|---|---|
| **entity term** | `Hypothesis` | `Hypothesis` | `Finding` | unified to `Finding`; original preserved in report metadata (`original_term`) |
| **index / id** | `### Hypothesis N:` (1-indexed; N int) | `### Hypothesis N:` | `### Finding N:` | `index: int` (required) + `id: str` (`"H1"`/`"F1"`, required) |
| **title / name** | short descriptive name in header (str, required) | one-line summary in header (str, required) | one-line pattern summary in header (str, required) | `title: str` (required; `(Layer N)` stripped) |
| **layer** | `(Layer N)` in header, N ∈ 1–4 (required) | `(Layer N)`, N ∈ 1–4 (required) | `(Layer N)`, N ∈ 1–4 (required) | `layer: Optional[int]` (None if header has no `(Layer N)`) |
| **claim** | `**Claim:**` 1–2 sentences (required) | `**Claim:**` 1–2 sentences (required) | `**Pattern claim:**` 1–2 sentences (required) | folded into `body` (no separate field) |
| **cohort prevalence** | — (not emitted) | — (not emitted) | `**Cohort prevalence:**` count + fraction of calls (required) | folded into `body` |
| **evidence** | `**Evidence:**` — `file:line` citations into agent source / failing transcript (required) | `**Evidence:**` — `file:line` into product artifacts **AND** a dropoff-data signal; **both required** | split: `**Trace evidence:**` (developer_id + call sequence) **AND** `**Product evidence:**` (`file:line`); **both required** | `citations: list[Citation]` extracted mechanically from `body` (defaults `[]`) |
| **proposed change (prose)** | `**Proposed change:**` prose (required) | `**Proposed change:**` prose (required) | `**Proposed change:**` prose (required) | folded into `body` |
| **structured edit spec** | fenced ` ```json ` block: `{applyable:true, edits:[…]}` **or** `{applyable:false, reason:…}` (required) | same (required) | same (required) | `applyable: Optional[bool]` parsed from the json block; `edits`/`reason` **not** retained |
| **verification** | `**How to verify:**` which eval metric moves, by how much (required) | `**How to verify:**` which step's pass-rate moves + which dropoff signal disappears (required) | `**How to verify:**` which trace pattern disappears + the expected replacement pattern + the failure condition (required) | folded into `body` |
| **full verbatim body** | — | — | — | `body: str` (required; entity markdown verbatim, `(Layer N)`-suffix retained inside body) |

**Pluma `Citation` sub-shape** (the only sub-object): `file: str`,
`line_start: Optional[int]`, `line_end: Optional[int]`, `raw: str`. A
file-only citation has `line_start = None`. `line_end == line_start` for
single-line citations. `Citation.overlaps()` is the mechanical cross-tool
matcher: same file + intersecting line ranges (file-only matches on file
equality alone).

**Required-vs-optional reading.**

- In the three tools, *every* field listed by that tool's "Output structure"
  is **mandated** — the system prompts use "MUST have all five of these"
  (agent-researcher, funnel-researcher) / "MUST have all six of these"
  (integration-watcher). There is no optional finding field; the only
  variability is the two-shape structured-edit block (`applyable:true` with
  a non-empty `edits` array vs `applyable:false` with a `reason` string).
- In `pluma`'s dataclass, `index`/`id`/`title`/`body` are always populated
  by the parser (required by construction); `layer` and `applyable` are
  `Optional` (None when the source lacks a `(Layer N)` header or a parseable
  json block); `citations` defaults to `[]`.

**Common core (present in all four):** index, title, layer, claim,
evidence-with-citations, proposed-change, structured-edit `applyable` flag,
verification.

**Field-level divergences:**

- **integration-watcher has six finding fields, not five** — it adds
  `Cohort prevalence` as a first-class required field, and it *splits*
  Evidence into two separately-required sub-fields (`Trace evidence` +
  `Product evidence`). agent-researcher and funnel-researcher have a single
  `Evidence` field.
- **Evidence content type differs by tool.** agent-researcher: `file:line`
  in agent source + a failing transcript/scenario reference. funnel-researcher:
  `file:line` in product artifacts + a quantitative dropoff signal.
  integration-watcher: `file:line` in product artifacts + trace evidence
  (developer_id + call ordinal/timestamp) + cohort prevalence.
- **pluma flattens the typed fields.** Only `layer` and `applyable` survive
  as structured fields; claim/evidence-prose/proposed-change/verification all
  collapse into `body`. `pluma` re-derives `citations` by regex over `body`
  (`_CITATION_RE`) rather than reading a structured evidence field — i.e.
  pluma treats citations as the load-bearing cross-tool key and everything
  else as opaque prose.

---

## 2. The four-layer model

Every tool mandates that each finding picks **exactly one** of four layers,
`(Layer N)`, N ∈ {1,2,3,4}, and cites evidence specific to that layer. "Two
[findings] that would be fixed by the same edit get collapsed" appears in all
three. The four layers are the single most divergent surface — each tool
re-instantiates the same abstract pattern for its domain. Definitions below
are **verbatim** from each system prompt.

### Abstract pattern (the latent invariant)

| Layer | Abstract role | One-sentence test |
|---|---|---|
| **L1 — the measurement instrument** | Is the thing that *declared this a failure* itself correct, or is the "failure" an artifact of how it was measured/framed? | Does the instrument's own definition match what the artifacts actually require/show? If not → L1. |
| **L2 — the machine-readable interface** | Tool/SDK/API surface: definitions, schemas, signatures, error codes, parameter names. | Does the interface hide a precondition, overlap, mis-name, or fail to name the actionable next step? |
| **L3 — context delivered at decision time** | What information actually reaches the decider at the moment of the decision. | Is the right context present *where and when* the decision is made, or is it buried / off-page / crowded out? |
| **L4 — sequence / runtime architecture** | The order operations happen in and the gates/branches between them. | Is a precondition introduced after its dependent step? Is a needed gate/branch missing? |

The two structural reframings that produce the divergence:

1. **Subject swap.** agent-researcher's subject is *the target agent / the
   model*. funnel-researcher's and integration-watcher's subject is *the
   developer integrating against a product*. So L2/L3/L4 read "model" in one
   tool and "developer" in the other two.
2. **Instrument swap (L1).** L1 names whatever produced the verdict: the
   *eval* (agent-researcher) → the *funnel definition* (funnel-researcher) →
   the *trace definition / cohort framing* (integration-watcher).

### Verbatim definitions, side by side

**Layer 1**

- **agent-researcher — "Evaluation":** "Compare the eval's expected answer
  against the rules the agent has actually been given (prompts, manifest
  thresholds, calibration bands). If the agent followed its documented rules
  and the eval still marks it wrong, the eval's expected answer is the most
  likely defect, not the agent. Specifically check: does any explicit
  threshold or confidence band in the agent's code support the eval's
  expected outcome given the observed prediction? If not, you may be looking
  at an L1 failure."
- **funnel-researcher — "Funnel definition itself":** "Is the funnel
  measuring the right outcome? Are step success criteria realistic given the
  product? Is the 'dropoff' actually a dropoff, or is it a measurement
  artifact (e.g., the success criterion is unobservable for developers who
  actually succeeded, or developers who reach the step's stated success
  criterion don't actually have the underlying capability)? Specifically
  check: does any explicit definition in the funnel match what the product
  artifacts actually require of the developer at that step? If not, you may
  be looking at a Layer 1 failure."
- **integration-watcher — "Trace definition itself":** "Is the trace
  measuring the right thing for the watch question? Are integrations being
  characterized correctly by what we captured, or is the pattern an artifact
  of what's *missing* from the traces (e.g., we see HTTP responses but not
  the developer-side stack trace; we see API call ordering but not the
  inter-call thinking)? Specifically check: does the watch question
  reference behavior that the traces *can* show, or does it depend on
  signals the trace stream doesn't include? If the latter, you may be
  looking at a Layer 1 finding."

**Layer 2**

- **agent-researcher — "Tools":** "Tool definitions, descriptions, schemas.
  Is a tool missing? Is its description weak? Does it overlap with another
  tool? Does it lack `when_not_to_use` guidance?"
- **funnel-researcher — "Product API/SDK surface":** "Tool definitions,
  schemas, error codes, parameter requirements. Is a required parameter
  named confusingly? Does the SDK method signature hide a precondition? Are
  error messages technically correct but missing the developer-actionable
  next step?"
- **integration-watcher — "Product API/SDK surface":** "Tool definitions,
  schemas, error codes, parameter requirements, SDK signatures. Is an error
  code returned in cases the message doesn't name? Does an SDK method
  signature hide a precondition the trace shows developers tripping on? Is a
  required parameter named confusingly such that the traces show repeated
  bad attempts before success?"

**Layer 3**

- **agent-researcher — "Context":** "What information reaches the model at
  decision time. Is the right context loaded? Is stale context crowding it
  out? Is a critical instruction buried?"
- **funnel-researcher — "Docs/Context delivered at decision time":** "What
  information does the developer see when they're about to make a decision
  (sign up, install, write their first call)? Is the right context
  delivered? Is critical setup information buried below example code? Does
  the developer have to leave the page they're on to discover a required
  step?"
- **integration-watcher — "Docs/Context delivered at decision time":**
  "What information does a developer encounter when they're integrating? Is
  critical setup buried below example code in the quickstart? Does an error
  catalog entry name the cause but not the fix? Are concepts (e.g., scoped
  keys, streaming) introduced in places the trace shows developers don't
  reach before they need them?"

**Layer 4**

- **agent-researcher — "Workflow":** "The runtime architecture. Is
  classification firing before tool calls? Is there a gate that should exist
  but doesn't? Is the dispatch logic wrong?"
- **funnel-researcher — "Workflow/Onboarding sequence":** "The order of
  steps the developer is asked to do. Is something a precondition for a
  later step but introduced after it? Is the sequence assumed-linear when it
  requires a branch? Is a critical setup step left implicit?"
- **integration-watcher — "Integration sequence":** "The order developers'
  integrations do things in, and what they skip or repeat. Is a setup step a
  precondition for a later step but introduced as optional? Are developers
  retrying the same broken call instead of changing the request shape? Are
  they not using an affordance (streaming, polling, cancel) the product
  provides because they don't know it exists from their entry point?"

### Per-tool layer name table

| | L1 | L2 | L3 | L4 |
|---|---|---|---|---|
| **abstract** | Measurement instrument | Machine-readable interface | Context at decision time | Sequence / architecture |
| **agent-researcher** | Evaluation | Tools | Context | Workflow |
| **funnel-researcher** | Funnel definition itself | Product API/SDK surface | Docs/Context delivered at decision time | Workflow/Onboarding sequence |
| **integration-watcher** | Trace definition itself | Product API/SDK surface | Docs/Context delivered at decision time | Integration sequence |

### Layer-model observations relevant to spec design

- **L1 is structurally the odd layer.** In the examples, L1 findings are
  almost always `applyable:false` — the fix is upstream of the file-edit
  surface (re-cut the cohort, fix the eval's expected answer, redefine the
  funnel step). See integration-watcher Finding 1 and pluma's `F1`, both
  `applyable:false` with reason "Layer 1 finding about the cohort
  definition itself, not a docs/spec edit." agent-researcher's issue_107
  Hypothesis 2 is the counter-example: an L1 finding that *is* applyable
  (tighten a confidence band in the prompt). The spec should not assume
  "L1 ⇒ non-applyable" but should note the strong correlation.
- **funnel & integration share L2/L3 wording almost verbatim** ("Product
  API/SDK surface", "Docs/Context delivered at decision time"). They diverge
  only at L1 (funnel vs trace definition) and L4 (onboarding vs integration
  sequence). agent-researcher's L2/L3/L4 are the outliers because its
  subject is the agent, not a developer.
- **The mandate is the four-layer *model*, not merely a `layer` field.**
  All three prompts: "every [finding] must pick **exactly one** layer". The
  spec's locked decision ("MANDATES the four-layer model … with
  domain-specific instantiations") is faithful to what already exists — the
  abstract pattern above is genuinely the common denominator, not a
  retrofit.

---

## 3. Structured edit format

Every finding's proposed change carries a fenced ` ```json ` block. It is
one of two shapes:

```json
{ "applyable": true,  "edits": [ { …edit… }, … ] }
{ "applyable": false, "reason": "why this can't be expressed as in-place edits" }
```

`applyable` must be exactly boolean `true` or `false` (all three appliers
reject any other value); `applyable:true` requires a **non-empty** `edits`
list; `applyable:false` falls back to `reason = "(no reason given)"` if
omitted. The block is matched by an identical regex in all three appliers
*and* in pluma: `` ```json\s*\n(.*?)\n``` `` (pluma uses a slightly
narrower `` ```json\s*\n(\{.*?\})\s*\n``` `` to grab only the object).

### The four edit actions and their required field sets

`_REQUIRED_FIELDS_BY_ACTION` is **byte-identical** across all three
appliers:

| action | required fields | semantics |
|---|---|---|
| **replace** | `file`, `from_line_start`, `from_line_end`, `expected_content`, `new_content` | Replace lines `from_line_start..from_line_end` (inclusive) with `new_content`. |
| **insert_after** | `file`, `at_line`, `new_content` | Insert `new_content` after line `at_line`. No existing content touched ⇒ no `expected_content`. |
| **delete** | `file`, `from_line_start`, `from_line_end`, `expected_content` | Delete lines `from_line_start..from_line_end` (inclusive). |
| **move** | `file`, `from_line_start`, `from_line_end`, `to_line`, `expected_content` | Delete `from_line_start..from_line_end`, re-insert *verbatim* after `to_line`. If wording must also change, use `delete` + `insert_after` instead. |

### Type rules (verbatim from agent-researcher's prompt — the canonical source)

1. **All line numbers refer to the ORIGINAL file** as shown to the model,
   before any edit in the spec is applied. Models must not compute post-edit
   line numbers.
2. The applier resolves shifts by a per-original-line plan (each original
   line independently "keep"/"drop"; inter-line slots collect inserts) — not
   a sequential bottom-up loop. (The prompt phrases this as "sorted
   bottom-up"; the implementation is the equivalent per-line plan.)
3. `expected_content` is **required** for every action that touches existing
   content (`replace`, `delete`, `move`); it is the applier's drift check.
4. `new_content` is **required** for every action that writes new content
   (`replace`, `insert_after`). `move` re-inserts the original
   `expected_content` verbatim and takes no `new_content`.
5. `expected_content` and `new_content` must match the file **VERBATIM** at
   the cited line range — character-for-character including indentation,
   quotes, punctuation, and trailing whitespace. No paraphrase, no
   normalization, no escape changes.
6. Line numbers are read off the displayed line-number prefix, not counted
   by the model.

### `expected_content` verbatim semantics

`_check_expected` (identical logic in all three): `actual =
"\n".join(original_lines[from_line_start-1 : from_line_end])`; if
`actual != (expected_content or "")` the applier raises and **no file is
written**. The check is exact-string, not normalized. Line addressing is
`str.splitlines()`-based; the original's trailing-newline state is
preserved. This is the spec's central trust mechanism: an edit that cannot
reproduce the pre-image verbatim is refused, so a stale or hallucinated
citation fails closed rather than corrupting a file.

### Overlap / applyability rules

- **Drop conflict (all three):** two edits cannot `delete`/`replace`/`move`
  the same original line. `_claim_drop` raises `OverlappingEdits`
  (agent-researcher: plain `ValueError`) on the second claim.
- **`move` destination guard (all three):** `to_line` must not fall inside
  `[from_line_start, from_line_end]`; must be within `1..n`.
- **Range guard (all three):** `from_line_start ≥ 1`, `from_line_end ≤ n`,
  `from_line_start ≤ from_line_end`.
- **`insert_after` anchor guard (funnel + integration ONLY):** a post-pass
  checks that every `insert_after`/`move` anchor line was not dropped by
  another edit; if it was, `OverlappingEdits` ("the insertion would have no
  anchor in the post-edit output"). **agent-researcher's applier has no such
  post-pass** — this is a real divergence (see below).
- **`replace` insert position (all three):** new content for a `replace` is
  scheduled to appear *before* the replaced range's start line
  (`_record_insert_before`; `emit_at_top` when the range starts at line 1).

### Applyability boundary (when the model emits `applyable:false`)

From agent-researcher's prompt (the fullest statement): emit
`applyable:false` when the change "cannot be expressed as a sequence of the
above actions on existing files (e.g., 'create a new file with this
function', 'add a new tool implementation', 'refactor across many call
sites')." "Do not stretch the edit format to cover changes it wasn't
designed for. An honest `applyable: false` is more useful than a misleading
edit list." funnel-researcher's examples: "redesign the agent_id concept",
"add a new endpoint". integration-watcher adds the structurally important
case: a **Layer 1 cohort/trace-definition finding** is non-applyable by
nature because the fix is upstream of the file-edit surface (see its
Finding 1 / pluma `F1`).

### Per-applier divergences (this matters for the conformance suite)

| Property | agent-researcher | funnel-researcher | integration-watcher |
|---|---|---|---|
| Entity term / id prefix | `Hypothesis` | `Hypothesis` | `Finding` |
| Parse entrypoint | `parse_hypothesis_report(Path, int)` | `parse_hypothesis_edits(str\|Path, int\|"1"\|"H1")` | `parse_finding_edits(str\|Path, int\|"1"\|"F1")` |
| Exception model | plain `ValueError` everywhere | typed: `ApplyError`/`ExpectedContentMismatch`/`UnknownAction`/`OverlappingEdits`/`NonApplyable` | same typed hierarchy as funnel |
| Virtual file names | none | `"error catalog"`, `"openapi"` → candidate paths | same as funnel |
| Snapshot/restore on failure | none (validate-first, write per-file if hash differs) | full transactional snapshot + restore-all-on-any-failure | same as funnel |
| `insert_after`-into-dropped-line post-pass | **absent** | present | present |
| Return type | `list[FileChange]` (path + before/after sha256) | `list[AppliedEdit]` (per-edit before/after + file hashes) | `list[AppliedEdit]` (same as funnel) |
| File resolver | literal join → unique rglob basename | + virtual-name resolution before basename | + virtual-name resolution (identical to funnel) |

`integration-watcher/applier.py` states in its own module docstring:
"Algorithm and discipline ported from funnel-researcher's applier — same
four edit actions, same overlap-detection post-pass …, same expected-content
verbatim discipline, same transactional snapshot/restore on failure." It is
functionally a rename of funnel's applier. **agent-researcher's applier is
the older/leaner sibling** (no typed exceptions, no snapshot/restore, no
insert-anchor post-pass, no virtual names). The *normative* shape — what the
spec must capture — is the **intersection**: the four actions, their
required-field sets, the `applyable` two-shape block, the verbatim
`expected_content` discipline, the drop-conflict rule, and original-line
addressing. Everything funnel/integration add (typed exceptions, snapshot,
insert-anchor post-pass, virtual names) is implementation hardening, not
part of the wire format the model emits.

---

## 4. Forbidden patterns

Each system prompt has an explicit forbidden list ("Forbidden hypotheses" /
"Forbidden findings"). Verbatim:

### agent-researcher — "Forbidden hypotheses" (7)

- "Make the prompt clearer" — too vague. What specifically is unclear,
  where, and why does that cause this specific failure?
- "Add more examples" — too vague. Which examples, drawn from what kind of
  failure, addressing which decision the model is getting wrong?
- "Add few-shot examples" — same problem, different framing. Specify which
  examples and what the model is currently getting wrong without them.
- "Lower the temperature" — almost never the root cause. Don't propose this
  unless you have evidence the failure is variance-driven.
- "Use a stronger model" — not a hypothesis about the agent's design.
- "The model is confused" — anthropomorphizing isn't a hypothesis. Identify
  what in the code is causing the confusion.
- "The model didn't follow the instruction" — a description of the failure,
  not a hypothesis about the cause. Why didn't it? Was the instruction
  salient? Buried? Contradicted? Identify the structural reason.

### funnel-researcher — "Forbidden hypotheses" (7)

- "The docs need to be improved" — too vague. What specifically, where, and
  what dropoff signal does that explain?
- "Add more examples" — too vague. Examples of what, addressing which
  specific confusion the dropoff data points at?
- "The developer experience is poor" — descriptive, not a hypothesis.
- "Run an A/B test on the onboarding flow" — that's the *next step* after a
  hypothesis, not a hypothesis itself.
- "Add a tutorial video" — generic content recommendation, not grounded in
  observed dropoff mechanism.
- "Improve error messages" — say which error, where in the catalog, and what
  developer behavior the current message produces vs. what you'd want.
- "Add analytics tracking" — meta-recommendation about measurement, not
  about why the funnel dropoff happens.

### integration-watcher — "Forbidden findings" (8)

- "The docs need to be improved" — too vague. What specifically, where, and
  what trace pattern does that explain?
- "Add more examples" — too vague. Examples of what, addressing which
  specific call sequence the traces reveal?
- "The developer experience is poor" — descriptive, not a finding.
- "Run an A/B test on the onboarding flow" — that's the *next step* after a
  finding, not a finding itself.
- "Add a tutorial video" — generic content recommendation, not grounded in
  observed call sequence.
- "Improve error messages" — say which error code, where in the catalog,
  what call sequence the current message produces vs. what you'd want.
- "Add analytics tracking" — meta-recommendation about measurement, not
  about what the existing traces reveal.
- "Developers are confused" — psychologize-the-user framing. Stay on
  observable call sequences and named product artifacts.

### Universal vs domain-specific split

**Universal (semantically present in all three; the spec's normative
forbidden subset):**

1. **The "vague, ungrounded best-practice" pattern.** Instantiated as
   "Make the prompt clearer" (agent-researcher) / "The docs need to be
   improved" (funnel + integration). Same shape — "make X better" with no
   *what / where / which mechanism* — different domain noun.
2. **"Add more examples"** — verbatim in all three.
3. **The "describe the symptom, not the mechanism" pattern.** "The model
   didn't follow the instruction" (agent-researcher) / "The developer
   experience is poor" (funnel + integration) — both forbid restating the
   failure as if it were a cause.

**Shared by exactly two of three — the anthropomorphize-the-subject
pattern.** agent-researcher forbids "The model is confused"; integration-
watcher forbids "Developers are confused". Each tool forbids
psychologizing *its own subject* (model / user). funnel-researcher omits
this one entirely. The spec should treat "do not psychologize the subject"
as a universal *principle* whose lexical instantiation depends on the
domain's subject (model vs developer) — and note that a structural-framing
tool (funnel-researcher) may legitimately not need it.

**Domain-specific to LLM-agent diagnosis (agent-researcher only):** "Add
few-shot examples", "Lower the temperature", "Use a stronger model". These
presuppose an LLM with sampling knobs and weights — meaningless for a
developer-funnel tool.

**Domain-specific to product-growth diagnosis (funnel + integration only):**
"Run an A/B test on the onboarding flow", "Add a tutorial video", "Improve
error messages", "Add analytics tracking". These presuppose a developer
funnel / PLG surface — meaningless for an agent-eval tool (no error
catalog, no onboarding flow, no A/B harness).

**Spec implication:** the forbidden-patterns section should publish the
universal core (vagueness, "add more examples", symptom-as-cause,
psychologize-the-subject) as normative, and explicitly mark the LLM-knob and
PLG-surface lists as **extension points** an implementing tool adds for its
domain.

---

## 5. Self-check discipline

Each system prompt ends with a pre-emission self-check walk. Counts:
agent-researcher 8, funnel-researcher 8, integration-watcher 9.

| # | agent-researcher | funnel-researcher | integration-watcher |
|---|---|---|---|
| 1 | every hypothesis cites specific `file:line` evidence | cites `file:line` **AND** specific dropoff signals | cites trace evidence (developer_id + call seq) **AND** `file:line` |
| 2 | hypotheses structurally distinct (collapse if same edit) | same | same (findings) |
| 3 | every hypothesis assigned a specific layer | exactly one layer | exactly one layer |
| 4 | a reader could apply the proposed change without further interpretation | same (structured edit spec) | same |
| 5 | avoided the forbidden list | same | same |
| 6 | evidence **affirmatively supports** the claim, doesn't merely sit nearby — *don't cite a rule's presence as evidence it's absent* | same — *if info EXISTS in docs/SDK, claim can't be "it's missing"* | same — *if product evidence shows info exists, claim can't be "missing"* |
| 7 | every `file:line`: cited number matches the displayed line-number prefix (don't count lines) | (a) file path matches the `####` header **and** (b) line matches the prefixed numbers | (a) `####` header match **and** (b) prefixed-number match |
| 8 | every structured edit: `expected_content` matches VERBATIM; else switch to `applyable:false`; paths/line numbers consistent with prose | same | same |
| 9 | — | — | **any percentage in cohort prevalence: verify the denominator against actual error/call totals; recompute; if mismatch, fix the denominator or restate as a bare count** |

### Universal vs tool-specific

**Universal (checks 2–8 are semantically identical across all three — the
spec's normative self-check subset):**

- **#2 structural distinctness / collapse-if-same-edit** — verbatim across
  all three.
- **#3 exactly one layer per finding.**
- **#4 applyable-without-further-interpretation.**
- **#5 forbidden-list compliance.**
- **#6 the "presence ≠ absence" trap** — the strongest shared discipline:
  evidence must *affirmatively* support the claim; you may not cite the
  existence of a rule/doc/field as proof of its absence. Domain-specialized
  wording (rule exists / info exists in docs/SDK / product evidence shows it
  exists) but identical logic.
- **#7 citation line-number verification against the displayed prefix.**
  Universal in intent; funnel & integration add a second clause (file path
  must match the `####` artifact header) because they cite across many
  product files, whereas agent-researcher cites one agent's tree.
- **#8 structured-edit verbatim check, else downgrade to
  `applyable:false`.**

**Universal in intent but divergent in content — #1.** All three require
every finding to be evidence-grounded, but the *evidence kind* differs:
agent-researcher = `file:line`; funnel = `file:line` + dropoff signal;
integration = trace evidence + `file:line`. The spec should state the
universal rule ("every finding must carry evidence sufficient to verify the
claim against a named source") and treat the *source types* as the
per-domain instantiation (see §6).

**Tool-specific:** integration-watcher's **#9** (denominator/percentage
verification) exists only because integration-watcher is the only tool with
a quantitative `Cohort prevalence` field. It is an extension point tied to
that field, not part of the universal subset.

---

## 6. Evidence rules

What each tool requires as the minimum credibility source(s) per finding,
and what `pluma` does with it.

| Tool | Required evidence per finding | Verification anchor |
|---|---|---|
| **agent-researcher** | `file:line` citation into the **target agent's source** (prompts/code) **or the failing transcript**, tied to a specific **scenario / eval failure** (the report header records scenario_id, expected vs predicted intent, eval notes). | A named **eval metric** must move by a stated amount (e.g. "issue 107 predicted_intent `bug`→`unknown`, pass_rate 6/7→7/7"). |
| **funnel-researcher** | **Both required:** (a) `file:line` into product artifacts (docs, SDK source, error catalog, OpenAPI); (b) a specific **dropoff-data signal** (e.g. "31% `MISSING_AGENT_ID`, median 4 calls"). A hypothesis with only one kind is ungrounded (self-check #1). | A named **funnel step's pass rate** moves + the cited dropoff signal disappears. |
| **integration-watcher** | **Both required:** (a) **Trace evidence** — `developer_id` + call sequence with timestamps/ordinal so a reader can locate it; (b) **Product evidence** — `file:line` into product artifacts. **Plus** `Cohort prevalence` — count of integrations + fraction of calls, with **denominator-verified** percentages (self-check #9). | A named **trace pattern disappears**, a stated **replacement pattern** appears, and an explicit **failure condition** is given (what would prove the finding wrong). |
| **pluma** (orchestrator) | Does not *require* evidence — it **extracts** `file:line` / `file:line-line` citations from each finding's body via `_CITATION_RE`, normalizes them (`normalize_citation`), and uses citation **overlap** as the cross-tool match key. | Cross-tool matches are typed: **Mechanical** (overlapping/identical citation, e.g. "both cite `docs/quickstart.md:23-30`") or **Categorical** (same layer + shared surface, e.g. "same Layer 2, shared surface `sdk/agents.py`"). |

**Citation grammar (pluma `_CITATION_RE`, the de-facto normative form):**
`file.ext:start` or `file.ext:start-end` / `file.ext:start–end` (ASCII
hyphen *or* en-dash accepted). Filename must contain an extension; a
left-boundary lookbehind prevents matching inside paths/URLs. `end < start`
is auto-swapped. File-only citations (no `:line`) are representable in the
`Citation` dataclass (`line_start=None`) but are *not* produced by
`_CITATION_RE` (which requires `:digits`). The three tools' prompts also use
a *virtual-name* citation idiom — `` error catalog:`17-18` `` and
`` `:43-44` `` (catalog/openapi without a real filename) — which the
appliers' resolvers map to real files but which `_CITATION_RE` will
**not** capture as a `file:line` Citation. This is a known fidelity gap
(see Risks).

**Cross-tool evidence shape (from `cross_pluma/report.md`):** the rendered
Pluma report does **not** use `### Hypothesis N:` / `### Finding N:`. It
emits `### Cross-match N — <Mechanical|Categorical> match`, embeds each
sister finding as **bold inline text** (`**funnel-researcher — H1: … [Layer
3]**`, note `[Layer N]` in *brackets* and an em-dash title separator), and
lists uniques under `### Finding F1 — title [Layer N] _(from tool)_`. This
is the shape `normalize.py`'s `_render_pluma_markdown` produces, not the
shape `_extract_findings` consumes.

---

## 7. Cross-cutting observations & risks for Phase 2 / Phase 3

These are not new opinions — they are convergences and hazards the spec
author needs on the table.

**Shared conventions all four already depend on (safe to make normative):**

- `### {Entity} N: {title} (Layer N)` header. Pluma's `_entity_header_re`,
  all three appliers' header regexes, and the examples all rely on it.
- The fenced ` ```json ` structured-edit block, regex-identical everywhere.
- A trailing `## What this report is NOT` H2 that bounds the last finding's
  body. All three appliers' section-slicers *and* pluma's
  `_H2_BOUNDARY_RE` stop a finding body at the first `^## ` (not `###`).
  Any conformance parser must replicate this boundary rule.
- `---` separators between findings in funnel/integration/pluma outputs
  (agent-researcher omits them); parsers must not treat `---` as a body
  boundary (none currently do — boundary is the next `###`/`##`).
- 2–3 ranked entries per report (agent/funnel: "ranked by likelihood";
  integration: "ranked by how broadly the pattern affects the cohort").

**Risks / open questions to resolve in Phase 2 before Phase 3:**

1. **Pluma's own example is a different shape.** `cross_pluma/report.md` is
   a *rendered Pluma report*, not a sister-tool report. `normalize.py`
   parses sister → Pluma; it has **no** Pluma-report-back parser. The Phase
   3 brief says all four examples must pass conformance. The conformance
   harness must therefore either (a) parse the Pluma report with a new
   Pluma-aware reader (handles `### Cross-match`, bold-inline embedded
   findings, `[Layer N]` brackets, `### Finding F1 — … _(from tool)_`), or
   (b) run conformance on the sister findings *as embedded in* the Pluma
   report. **Decision needed in Phase 2.** Recommend a thin Pluma-report
   reader rather than overloading `_extract_findings`.
2. **Virtual-name citations vs `file:line`.** `error catalog:17-18`,
   `` `:43-44` ``, `openapi` are valid evidence the appliers resolve, but
   `_CITATION_RE` won't extract them as Citations. If the Finding schema
   requires a structured `file:line` citation, several real reference
   findings (funnel H3, integration F3) cite the catalog by virtual name and
   would fail. The schema must allow a citation `source` taxonomy
   (file:line | virtual-artifact | trace-ref | dropoff-signal | scenario-
   ref) rather than only `file:line`. This is the single biggest
   schema-design decision and directly drives whether the four examples
   pass.
3. **`pluma` as a dependency of the conformance harness.** The Phase 3
   brief flags the choice: import `pluma.normalize` as a dev dependency vs
   extract its parsing into the spec package. Recommendation to record now:
   **extract a minimal vendored parser** into `agent_diagnosis_spec` (the
   header/JSON-fence/H2-boundary logic is ~60 lines and is the normative
   parsing contract — owning it makes the spec self-contained and avoids a
   circular dependency where pluma references the spec and the spec depends
   on pluma). Pluma can later be updated to import the spec's parser.
4. **L1 ⇄ applyability.** Evidence shows L1 findings are usually (not
   always) `applyable:false`. The schema must *not* hard-require
   `structured_edits` for any layer, and must require `reason` exactly when
   `applyable:false`. agent-researcher's issue_107 H2 (applyable L1) proves
   the rule can't be "L1 ⇒ non-applyable".
5. **Evidence-kind is per-domain.** A single rigid `evidence` schema will
   reject 3 of 4 examples. The schema needs evidence as a tagged union
   keyed by source type, with the *minimum-credibility* rule ("≥1 verifiable
   source; the source types accepted are the domain's instantiation")
   stated in prose and enforced by per-layer/per-domain conformance checks,
   not by one frozen JSON shape.

---

## Phase 1 conclusion

The latent specification is real and consistent. The four-layer model, the
finding field set, the two-shape structured-edit block, the verbatim
`expected_content` discipline, the universal forbidden/self-check cores, and
the citation grammar are genuine shared opinions — not coincidences. The
divergences are traceable and almost entirely **domain instantiations of one
abstract pattern** (subject swap: model ↔ developer; instrument swap: eval ↔
funnel ↔ trace) plus **implementation hardening** in the two newer appliers.
The principal Phase 2 design tension is **evidence modelling**: a single
frozen `file:line` schema will fail the funnel/integration/pluma examples;
the spec needs a tagged evidence union with a prose minimum-credibility rule
and per-domain conformance checks. Resolve risks 1–5 before writing
`finding.schema.json`.

**Stopping here per the Phase 1 guardrail. Awaiting review before Phase 2.**
