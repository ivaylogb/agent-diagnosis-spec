# Agent Diagnosis Spec — v0.2 (addendum, draft)

**Status:** Draft. Tracks the v0.2 changes additively against v0.1.

---

## What v0.2 adds

v0.1 specified the **output** of a conforming diagnosis tool (`Finding`,
`StructuredEdit`, `EvidenceItem`, the four-layer model, the grounding
principles). It said nothing about the **input** — each tool defined
its own loader contract, and adapters from external platforms
(Braintrust, LangSmith, PostHog, OTel) reverse-engineered the
loader's Python types to know what to emit.

v0.2 lifts those input contracts into the spec. Three new schemas:

| Schema | Consumed by | Adapter sources |
|---|---|---|
| `FailingEval` + `FailingEvalContainer` | `agent-researcher` | Braintrust, LangSmith, Inspect AI, OpenAI Evals, promptfoo, deepeval, in-house eval runners |
| `FunnelDropoff` | `funnel-researcher` | PostHog, Amplitude, Mixpanel, BigQuery analytics tables, Segment |
| `TraceCohort` | `integration-watcher` | OpenTelemetry, PostHog API call events, Datadog APM, Honeycomb, Sentry trace exports |

Lifting these into the spec converts the adapter ecosystem from
"reverse-engineer agent-researcher's loader, hope it doesn't change"
to "write JSON conforming to a documented schema, run any spec-v0.2
diagnosis tool against it." It is the same move v0.1 made for the
output (the Finding shape) — bringing an implicit convention into the
public spec — and it pays off the same way.

## Scope of v0.2

- **Normative:** `failing-eval.schema.json`,
  `failing-eval-container.schema.json`. These are stable enough to
  build adapters against; the conformance suite checks them.
- **Draft-normative:** `funnel-dropoff.schema.json`,
  `trace-cohort.schema.json` (forthcoming). Adapters may target the
  draft shapes; expect minor changes before normative.
- **Unchanged from v0.1:** `Finding`, `StructuredEdit`,
  `EvidenceItem`, the four-layer model, the grounding principles, the
  forbidden-pattern list. v0.2 is additive — every v0.1-conforming
  diagnosis remains conforming under v0.2.

## The `agent_revision` requirement

v0.1 did not name the diagnosis target — the assumption was that the
operator pointed `agent-researcher` at the right source manually. In
practice, the source drifts: an eval ran on Tuesday's deployed code, the
diagnoser runs on Friday against `main`, and the citations land on
lines that have moved.

v0.2 makes the target version a first-class field. Every
`FailingEval` adapter MUST set `metadata.agent_revision` (or
container-level `agent_revision`) when the source platform knows it.
Braintrust experiments can carry a `git_sha` in their metadata;
LangSmith runs can be tagged. Adapters that cannot resolve a revision
SHOULD say so explicitly (`agent_revision: null`) rather than
silently passing through whatever the diagnoser happens to be checked
out against.

A v0.2 conforming diagnosis tool that receives a `FailingEval` with
`agent_revision` set SHOULD verify that the target source is at that
revision before citing into it, and SHOULD refuse to emit a Finding
with a `file:line` citation if it is not.

## Backward compatibility

v0.1 input loaders accepted ad-hoc JSON shapes. v0.2's
`FailingEvalContainer` is the shape `agent_researcher.eval_analyzer.
load_eval_result` already reads — the schema documents the existing
contract, it does not change it. Existing adapters that emit the v0.1
shape continue to work; they will simply not populate the new
optional fields (`scorer_signature`, `spans`, `agent_revision`,
`cluster_size`).

## Reference adapters

- `pluma.integrations.braintrust.experiment_to_failing_evals` —
  Braintrust experiments → `FailingEvalContainer`. Supports
  `scorer_signature`, `spans`, `agent_revision`, optional pre-pass
  clustering.
- `pluma.integrations.langsmith.runs_to_failing_evals` — LangSmith
  runs → `FailingEvalContainer`. Captures the full run tree as
  `spans`.

## Open questions for v0.3

- A `FailingEvalCluster` schema for explicit cluster bundling —
  currently representatives carry `cluster_size` and
  `cluster_member_ids`, which is enough for diagnosis but loses some
  audit information. A first-class cluster object would carry every
  member.
- Cross-experiment regression diagnosis: when comparing experiment B
  (regressed) to experiment A (baseline), the diagnosis input is
  *the diff* — rows that flipped from pass to fail. v0.3 may
  introduce a `FailingEvalDiff` shape.
- A standardized `spans` sub-schema. Currently opaque; a sub-schema
  for OTel-style spans would let the conformance suite check
  span-aware findings.
