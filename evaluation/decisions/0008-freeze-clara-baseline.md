# Decision 0008: Freeze Clara baseline with documented defects for simulator comparison

Date: 2026-09-10. Owner: Eliot. Status: accepted baseline freeze.

Following the audit of EXP-LIVE-003 (`20260910T103557589618Z-0f739a3a`), the owner directed that Clara's prompts, tool definitions, and runtime code be frozen as-is for the upcoming simulator comparison (EXP-SIM-003).

Two residual defects from the live repair audit remain documented and accepted in this frozen baseline:
1. **Online vs part-time study conflation**: Clara fails to correct the student's assumption that online delivery implies confirmed part-time availability and omits this unknown in the discovery recap (`discovery-skeptical`).
2. **Tool-level degree inference**: Clara passes `has_bachelor_degree=False` to `search_courses` based solely on a student disclosing secondary completion overseas (`discovery-international`).

### Rationale
Freezing Clara at this verified state provides a stable, fixed target for the EXP-SIM-003 model comparison (Gemini 2.5 Flash vs Gemini 3.8 Flash). It isolates the simulator model as the primary independent variable and allows evaluators to determine whether either simulator model reliably uncovers, probes, or handles these known defects during adaptive dialogue.

No further prompt patches or runtime restarts will be applied to Clara prior to the completion and evaluation of EXP-SIM-003.
