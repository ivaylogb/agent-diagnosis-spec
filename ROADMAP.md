# Spec roadmap

Future versions of the spec will lift additional input schemas as their
implementations mature across multiple adapters.

## Future schemas

- **FunnelDropoff** — input contract for funnel-researcher. Currently
  implicit in funnel-researcher's loader. Will be lifted into the spec when a
  second adapter (beyond the Stripe worked example) exists to validate the
  shape against.

- **TraceCohort** — input contract for integration-watcher. Currently
  implicit. Lifted when a real-world adapter (Pluma's PostHog or OTel
  integration's output is the current sole example) provides empirical
  grounding.
