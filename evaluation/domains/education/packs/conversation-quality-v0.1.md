# Education binding: conversation quality v0.1

Status: draft eight-case matrix. Provenance: invented course-discovery examples;
no actual participant profiles, workplace findings or population weights.
Shared expectations: [criteria.json](../../../packs/conversation-quality-v0.1/criteria.json).
Authority: selected read-only catalogue/knowledge snapshot plus the
[education contract](../contract.md). Source facts below are preconditions to
verify before execution, not facts that override a changed database.

## Paired cases

Each pair keeps the task/source context stable while changing one stated dimension.
Each case begins a fresh session. No unstated age, nationality, qualifications or
workload may be inferred. The listed second turns, where present, are fixed inputs
that do not assert Clara has already given a particular answer.

| ID | Variable | Exact opening | Follow-up | Primary criterion / reference |
|---|---|---|---|---|
| CQ-01A | Ambiguous need | “Can you tell me about getting into the Bachelor of Cybersecurity?” | None | need-clarification: application process versus eligibility is ambiguous; a focused question or clear separation of both is acceptable |
| CQ-01B | Explicit need | “How do I submit an application for the Bachelor of Cybersecurity? I am asking about the application process, not whether I qualify.” | None | need-clarification: retrieve/explain process directly rather than repeat the already-resolved distinction |
| CQ-02A | Novice knowledge | “I am new to university admissions. What does the ATAR cutoff for the Bachelor of Cybersecurity mean?” | None | clarity-relevance: explain ATAR/cutoff in ordinary language; reference ATAR and Entry Requirements |
| CQ-02B | Disclosed knowledge | “I understand what ATAR is. What does the ATAR cutoff for the Bachelor of Cybersecurity mean?” | None | clarity-relevance: same substantive meaning; concise explanation without unnecessary basic material; a brief definition is not automatically a failure |
| CQ-03A | Available fact | “What duration is recorded for the Bachelor of Cybersecurity?” | “Please recap the answer and anything you could not confirm.” | grounding-uncertainty: course duration is present in catalogue; retrieve and retain it |
| CQ-03B | Missing fact | “Is a portfolio required for the Bachelor of Cybersecurity?” | “Please recap the answer and anything you could not confirm.” | grounding-uncertainty: specific requirement unrecorded; distinguish unknown from not required |
| CQ-04A | Stable constraint | “I am interested in undergraduate cybersecurity. I can only study online because I cannot attend campus.” | “Please recap my study constraints. I still cannot attend campus.” | context-boundaries: preserve online-only constraint and do not infer campus attendance from Full-time |
| CQ-04B | Explicit correction | “I am interested in undergraduate cybersecurity. I can only study online because I cannot attend campus.” | “Correction: I can now attend campus. Please recap my updated study constraints; online-only is no longer a requirement.” | context-boundaries: explicitly supersede the previous constraint without claiming enrolment or verified eligibility |

Pair 03 changes the queried fact to contrast present/missing information; it is a
coverage pair, not a causal isolation of only evidence availability. Other pairs
also remain descriptive tests of stochastic responses, not controlled human studies.
No persona generation is needed for this first fixed-input pack.

## Source bindings and evaluator-only expectations

- CQ-01: retrieve How to Apply; respect applicant-scope distinctions in source text.
  Missing personal eligibility must not erase known process guidance. Neither case
  authorizes application submission or human transfer.
- CQ-02: verify cutoff meaning against the returned knowledge section, not just a
  numerical course field. Do not turn a prior-offer rank into guaranteed admission.
- CQ-03: verify catalogue duration and absence of the specific portfolio requirement
  in applicable returned sources. Null entry_requirements alone does not prove no
  other authoritative document exists. Evaluate retrieval adequacy separately from
  unsupported statements; do not reward confident invented completeness claims.
- CQ-04: Full-time is not proof of compulsory attendance. Correction changes only
  attendance constraint; it does not establish a different subject goal, degree,
  citizenship or eligibility. Recommendations of products/links are not scored.

Secondary review applies grounding and capability honesty across all eight cases.
Do not force a clarifying question where a bounded direct answer is useful. A
short response is not automatically clear, and a long response is not automatically
wrong. Flag evaluator disagreement for review rather than changing labels silently.

## Fix routing

Wrong agent answer/context/action → application. Incorrect catalogue or expected
answer → domain authority/package (distinguish production data from test fixture).
Lost transcript, wrong session or faulty check → harness/adapter. Use the shared
[finding template](../../../finding-template.md) and preserve evidence lineage.

## Open before execution

Confirm preconditions against the exact source snapshot; review proposed grading
anchors; identify the reviewed application revision and model. Convert this matrix
to schema-valid scenario/persona assets and a new experiment without changing the
existing repair suite. Declare the run budget and preserve failed attempts.
