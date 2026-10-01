# Decision 0009: Explicit ownership across three layers

Status: accepted separation principle. Owner: Eliot.
Context: after the experience-guard repairs, the owner requested a clear distinction
between application, domain evaluation package and harness so each fix is placed
consciously. This extends Decision 0001; it does not approve a framework extraction.

Decision: use the [layer map](../architecture.md) and
[finding template](../finding-template.md) for future repair handoffs. Identify the
primary defect layer and supporting changes. Domain-specific application code is
not part of the reusable harness merely because its tests live under evaluation/.

Rationale: preserve useful business-specific checks while preventing the harness
from absorbing education policy. Keep application changes, evaluation-criterion
changes and evidence/measurement fixes distinguishable.

Alternatives: continue an implicit mixed directory; immediately split repositories.
The first obscures ownership; the second imposes interfaces before reuse is proven.
Document current coupling now and perform bounded extraction later with evidence.

No production changes, file reorganisation, paid evaluation or second-domain
integration is authorized by this decision. Existing evidence remains unchanged.
