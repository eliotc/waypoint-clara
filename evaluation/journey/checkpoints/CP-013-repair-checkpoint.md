# CP-013 — Discovery repairs and comparison prepared

Recorded:2026-09-10. Owner approved repairs, fixed retesting, then a simulator
comparison; later requested a logical stopping point due to token budget.

Implemented: fuller retrieved knowledge and course descriptions; explicit evidence
limits/date; removal of forced follow-up instructions; bounded session-only user
message evidence before recaps. This preserves source messages without inferring
facts or persisting a student profile. It is not a complete structured fact engine.

EXP-LIVE-003 *(withheld)* preserves a completed
transitional run and a final bounded regression run. Final run
`20260910T103557589618Z-0f739a3a` was still running at checkpoint, with two saved
five-turn cases; review its report first on resumption. Early evidence improves
missing-requirement/date handling, but the part-time unknown still disappears
from a recap. Defects are not all resolved; do not claim a semantic pass.

EXP-SIM-003 *(withheld)* is validated and ready,
not executed. Both model metadata lookups succeeded; no3.8 generation-quality or
adoption claim. Comparison uses balanced model order and records different
supported thinking configurations, latency and usage. No change to Clara's Live
model or authoritative database.65 repair tests plus2 metrics tests passed.

Next: inspect/review final fixed evidence, address remaining critical gaps, then
freeze Clara and execute the already approved bounded comparison. The owner asked
to wrap this turn, not to abandon that plan. No push/deploy or shared DB mutation.
