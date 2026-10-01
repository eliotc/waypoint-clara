# CP-014 — Live Repair Audit and Simulator Comparison Completed

Recorded: 2026-09-10. Owner audited EXP-LIVE-003, froze Clara's baseline under Decision 0008, and authorized execution of EXP-SIM-003.

## Before
- Fixed repair run EXP-LIVE-003 had completed execution (run `20260910T103557589618Z-0f739a3a`), but trace-level audit was incomplete.
- EXP-SIM-003 was validated and prepared, but unexecuted.
- Question remained whether Gemini 3.8 Flash provided measurable benefit as an adaptive persona simulator over Gemini 2.5 Flash.

## Evidence
- **EXP-LIVE-003 Audit:** 10/10 transport/isolation checks passed. 3/5 semantic checks passed (`first-time`, `busy`, `honest-stop`), 2/5 failed with confirmed residual defects (online/part-time conflation in `skeptical`; tool-level degree inference in `international`).
- **Owner Decision 0008:** Baseline frozen with documented defects to keep Clara stable as a comparison target.
- **EXP-SIM-003 Execution (`20260910T133505492907Z-adaptive-7067e89f`):** 8 complete sessions, 40 turns, 0 execution errors.
  - Metrics: 2.5 Flash median latency 2,018ms (14,663 tokens); 3.8 Flash median latency 2,605ms (15,225 tokens).
  - Fidelity & Probing: 3.8 Flash staged disclosure more naturally and actively probed Clara's vague claims on part-time delivery in `skeptical`, successfully surfacing the residual counselling defect. 2.5 Flash was overly agreeable and missed the gap.

## Changed thinking
- Model scale/generation in simulators directly impacts defect discovery: compliant/deferential simulators (2.5 Flash) produce false confidence by accepting evasive agent responses. A model capable of reasoning through edge constraints (3.8 Flash) acts as a far more effective red-teaming simulator.

## Next steps
- Adopt Gemini 3.8 Flash for adaptive persona simulation pipelines.
- Return to Clara's prompt/tool layer to resolve the two known defects before any public or production evaluation gates.
