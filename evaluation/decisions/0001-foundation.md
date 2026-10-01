# Decision 0001: Grow the toolkit beside Clara

Date: 2026-09-06. Status: implementation direction authorized by the project owner.

Clara is a demonstration and the first small integration target for capabilities
that may later support other domains. The owner supplies domain judgment.
For real Clara runs, the selected version of the database is authoritative for
university facts; synthetic evidence cannot prove real-world counseling accuracy.

Keep reusable execution and evidence contracts under `evaluation/`, with domain
assets and adapters separated. Keep focused authoring/review skills in the repo.
Begin with an explicitly synthetic offline experiment so correctness of the
harness can be tested independently from model performance. Use JSON Schema and
one evaluation-only dependency rather than a service or broad agent framework.

Alternatives considered: a permanent evaluation branch would drift from the
application; a separate platform/repository now would impose interfaces before
we have a second user; skills alone would not provide independent repeatable runs.

Use short-lived changes and durable experiment IDs. Extract a package when a
second domain establishes a useful shared interface. No automated deployment or
release decision is authorized by this foundation. Proposed success criteria and
severity rules remain provisional until reviewed by the owner.

Public edition: references to broader platform plans are withheld under [Decision 0013](0013-publication-boundary.md).
