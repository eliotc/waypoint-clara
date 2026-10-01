# Clara: Gemini 3.8 Live evaluation roadmap

Recorded: 2026-09-15. Owner: Eliot. Status: owner requested capture of the proposed
sequence; no model switch, paid run, deployment or baseline acceptance authorized
by this record. This is a roadmap, not an executable experiment protocol.

## Purpose

Determine whether newer Live models improve grounded, constraint-preserving course
discovery at an acceptable latency and cost. More natural speech or faster first
audio does not establish more dependable advice. Preserve the current failures
as evidence rather than requiring a perfect dialogue baseline before comparison.

## Sequence and prerequisites

1. Complete independent review of the bounded professional IT experience guard.
   The application must not manufacture unsupported values even when the model
   proposes None. Keep deterministic guard correctness separate from model quality.
2. Freeze a reviewed application/data baseline and record residual dialogue failures.
   Record source hashes, instructions, scenario/rubric versions, model identifiers,
   settings and database snapshot. Keep model proposals and effective tool values.
3. Verify Gemini 3.8 Live compatibility in an isolated local target before comparison.
   Check actual Gemini API/Vertex availability, region, SDK/ADK support, auth path,
   tool declarations, session settings and transcript collection. Do not assume
   changing a model string is sufficient or that both deployment paths match.
4. Design a versioned comparison of the current Gemini 3.1 Flash Live baseline and
   standard Gemini 3.8 Live. Keep application facts and behavioural criteria fixed;
   document any necessary adapter differences. Include repeated cases, fresh
   paraphrases and positive controls, with a predeclared budget and stopping rules.
5. Evaluate Gemini 3.8 Live Extended Thinking separately, on cases requiring several
   retrievals and reconciliation of constraints. First validate asynchronous tool
   handling and completion detection in both the application and evaluation runner.
6. Independently review evidence and make a model-selection recommendation. Only
   then consider a controlled staging deployment and browser voice checks before
   public-demo promotion. Preserve a rollback revision.

## Cases to retain

- Online delivery versus unconfirmed part-time workload or campus attendance.
- Unsupported qualification/experience proposals and guarded effective values.
- Rejected alternatives, welcomed alternatives and explicit preference changes.
- Application instructions retained alongside unknown individual eligibility.
- Overseas qualification questions with missing assessment policy; RPL information
  must not be treated as secondary admission procedure.
- Honest no-match stopping and the contrasting case where useful next steps exist.

These evaluate Clara, not the persona simulator. Gemini 3.8 Flash simulator work
in EXP-SIM-003 is a separate model and experiment from the Live models here.

## Measurement and interpretation

Assess factual grounding, constraint preservation, uncertainty, proposed/effective
tool arguments, recap fidelity and useful next steps across all turns. Count
execution failures and incomplete attempts. Separate automatic checks from manual
semantic dispositions; never promote NEEDS_HUMAN implicitly.

Measure time to first audio, time to a substantive evidence-supported answer and
time to interaction completion separately. Record token/audio usage and cost using
verified pricing at execution time. Review intermediate spoken updates as well as
final answers; early reassuring speech may precede the evidence needed to advise.

Repeated synthetic cases support bounded comparisons, not population reliability,
human trust or adoption claims. Microphone recognition, interruptions, reconnects,
playback and perceived latency need additional browser/voice validation. Extended
Thinking may trade latency/cost for better decisions; no improvement is assumed.

## Integration facts to recheck before implementation

Google's documentation reviewed September 15 describes standard 3.8 Live as the
low-latency option and Extended Thinking as supporting background reasoning and
asynchronous tools. Standard Live changes default tool execution behaviour and
has migration-specific configuration requirements. Extended Thinking requires
non-blocking tools; turnComplete can end an utterance while processing continues,
so interaction_status must govern completion. A runner must not score an interim
“checking” message as the final answer or advance to the next case prematurely.

Sources:
- [Standard Live and migration](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-live)
- [Extended Thinking](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-live-extended-thinking)
- [Thinking and lifecycle comparison](https://ai.google.dev/gemini-api/docs/live-api/thinking)

The linked Google blog announcement could not be retrieved during the discussion;
assessment was based on these official technical documents. Availability and API
behaviour must be reverified at implementation time.

## Next action and decisions still open

Immediate next action remains guard correctness review. Before paid comparison,
write the executable protocol, budget, repetitions, acceptable tradeoffs and review
criteria. This record captures direction without choosing a winning model or
relaxing the existing behaviour contract. Update with experiment IDs and dated
findings as work proceeds; preserve earlier evidence and rationale.
