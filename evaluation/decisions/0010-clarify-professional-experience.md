# Decision 0010: Clarify ambiguous professional experience

Date: 2026-09-16. Status: accepted product direction. Owner: Eliot.

The owner chose clarification over inferred experience. Clara may use a positive
professional IT work duration only from a clear first-person work/professional
disclosure. Generic IT experience, coursework, personal projects and partial
duration refinements remain unknown. Explicit no experience remains zero.

When that unknown materially affects suitability, ask one focused clarification.
Use already clear disclosures; respect uncertainty, refusal and stopping. An
unresolved answer must not cause repeated questioning or verified eligibility.
A suggested question is: “How many years have you worked professionally in IT,
excluding study and personal projects?”

This deliberately trades broader language coverage for fewer unsupported facts.
The bounded parser currently needs a complete work disclosure to resolve a
positive value; fragment-only answers may stay unknown. Structured conversational
capture is a possible later improvement, requiring its own evidence-binding design.

Primary owner: application (guard, tool response and agent instructions).
Application regression tests enforce the changed contract. The shared harness
and conversation-quality pack do not acquire education business logic.

The implementation retains proposed/effective values and unresolved message
evidence, and returns a clarification signal. That signal is conditional guidance,
not proof the Live agent asks appropriately. Offline passing results do not close
the Live behavioural review or demonstrate real-user acceptance.

Earlier reviews remain historical evidence under their original contracts.
Positive-control fixtures now explicitly disclose professional work; generic
forms remain tested as unknown. No prior run is regraded by this decision.
