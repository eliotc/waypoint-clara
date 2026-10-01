# CP-018 — Evaluate outcomes, preserve uncertainty, and separate model effects

Recorded on: 2026-09-21. Period covered: September 21 discussions and reviews.
Provenance: contemporaneous synthesis. Author: Codex, evaluation reviewer.
Predecessor: [CP-017](CP-017-live38-ordinary-pilot.md). This checkpoint does not reconstruct every intervening task.
Sources: independent Live 3.8 review *(withheld)*, regrade review *(withheld)*, [Decision 0010](../../decisions/0010-clarify-professional-experience.md), and the owner's September 21 discussion of a Turn 2 search flag and learning capture. That pasted two-turn example has no independently verified run ID here.

## Before

The showcase prescribed narrow tool paths, including context lookup for the online-only turn. Early model-comparison interpretations suggested newer-model caution might eliminate overclaims. Aggregate supported findings risked being read as coverage of the whole conversation. Fixed questions provided repeatability, but their limits as simulated student behaviour needed to be explicit.

## Evidence and limitations

- In the owner-supplied example, Alex introduced online-only study and Clara searched with that constraint. Tool telemetry flagged search_courses, although the spoken answer confirmed online delivery and retained unknown eligibility. Reusing earlier evidence would also have been reasonable. Full tool evidence for that specific example was not independently reviewed.
- In the same example, Clara asked about professional experience and the next scripted message did not answer. In the independently executed six-turn run, the script later supplied a correction without Clara eliciting it. These are properties of fixed scripts, not demonstrated adaptive student behaviour.
- Run showcase-daa7650462130b2e completed six turns on gemini-3.8-live with text input and captured audio. The opening avoided confirming eligibility, but the model proposed three professional years and the guard converted that to unknown. No workload overclaim appeared; however, the retrieved payload did not expose the audience-description phrase implicated in earlier failures. This is one run, not a controlled paired comparison, browser test, or human study.
- Its recap said no matching options were found despite a retrieved online alternative with unknown eligibility. No confirmed match and no potentially relevant options are different conclusions.
- The saved calibration regrade caught the audience/workload defect but still labelled the initial eligibility claim supported, left all 14 claim evidence lists empty, and returned an unexplained facts-preservation validation failure. Citation-span validity alone did not establish semantic support or complete coverage.

## Changed thinking

1. Judge outcomes and evidence use, allowing multiple valid tool paths. A repeat search may be an efficiency cost without being an advice defect. Nondeterminism does not itself make a legitimate alternative path wrong.
2. Fixed scripts test repeatability and specified corrections; they do not establish that Clara can elicit the missing information or handle an adaptive student's replies. Use a separate adaptive track for that question, with its own fidelity limits.
3. Attribute results across model proposals, guarded values, retrieved evidence, and spoken answers. A safe application result is not proof of native model restraint. A model not encountering a trigger is not evidence it has learned to handle it.
4. Preserve both kinds of uncertainty: unknown eligibility is neither confirmed eligibility nor confirmed exclusion. Caution can still produce an unsupported negative conclusion.
5. Evaluate the evaluator. Distinguish a verified agent defect, an unassessed claim, a citation failure, and incomplete coverage. A reassuring aggregate label must not conceal omitted assertions.

## Dispositions

Owner direction: capture evolving learnings in the journey as work progresses; implemented in the project working agreement (not published). The owner also requested broader evaluation instructions for the implementing agent. No model migration or general reliability acceptance was made.

AI recommendation: permit a new constraint-filtered search or reuse of sufficient prior evidence, with repeat lookups as separate efficiency telemetry. Hermes's handoff reports this adjustment implemented and comparison preparation underway; this checkpoint does not independently accept that implementation or its reported test receipts.

No new domain-policy decision is established by this checkpoint. Existing accepted clarification direction remains in Decision 0010. Model conclusions remain provisional.

## Next and revisit trigger

Review the bounded evaluator repairs and proposed comparison before interpreting aggregate scores. Compare frozen application/data/scenarios across repeated model runs; distinguish natural retrieval from controlled evidence exposure. Include unsupported-positive and unsupported-negative conclusions in calibration. Assess targeted clarification resolution separately with adaptive replies.

Reconsider the tool-path recommendation if repeated lookups materially increase latency/cost or introduce conflicting advice. Reconsider model-improvement hypotheses after repeated matched-evidence tests. Reconsider persona realism after comparison with actual user behaviour; synthetic agreement alone cannot establish adoption value.
