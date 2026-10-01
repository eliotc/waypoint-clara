# Three layers and where to fix a failure

Status: owner-approved separation principle; current module map and migration
priorities are an implementation assessment. This document describes today's
boundaries honestly; it does not claim that code extraction is complete.
See [Decision 0009](decisions/0009-layer-ownership.md).

## Responsibilities

| Layer | Owns | Must not own |
|---|---|---|
| 1. Application under test | Agent instructions, user context, tools, business rules, source retrieval, user-visible behaviour | Evaluation scores or changes made just to conceal failing evidence |
| 2. Domain evaluation package | Authoritative fixtures, personas, scenarios, expected outcomes, severity and domain interpretation | Production eligibility logic or general run orchestration |
| 3. Evaluation harness | Execution contracts, evidence capture/provenance, generic checks, result states, comparison and review workflow | Embedded admissions policy, invented persona facts or assumptions that every target exposes Clara's tools |

Adapters belong to the harness integration boundary, but are target-specific—not
reusable core. The Clara adapter can know Clara's protocol; the core should depend
on an adapter contract and declared capabilities. A domain is not a target: two
education agents could share scenarios but require different adapters.

Expected dependency direction: harness loads a domain package and invokes a target
adapter; the adapter communicates with the application. The production application
must not import evaluation rules to decide its behaviour. Domain checks may use
independent source fixtures; do not reuse the application's own decision function
as the sole oracle for whether that function is correct.

## Current module map

| Current location | Logical owner | Present boundary / action |
|---|---|---|
| backend/agent.py, tools.py, main.py | Application | Instructions, tool execution and voice/session behaviour |
| backend/degree_status.py, experience_status.py, suitability.py | Application | Education-specific fact interpretation and business rules; not harness features |
| frontend/, data/ | Application | UI, catalogue and knowledge content; selected snapshots become evaluation inputs |
| evaluation/domains/education/ | Domain package | Contract, fixtures, personas and scenarios already grouped |
| evaluation/experiments/ | Evaluation records | Versioned composition of target, domain and protocol; reviews retain evidence, not runtime business logic |
| evaluation/graders.py | Harness core | Generic JSON-pointer/equality checks and manual-review dispositions; semantic counselling is not automated by these primitives |
| evaluation/adapters.py | Harness core contract / fixture adapter | Existing run contract and synthetic trace replay |
| evaluation/contracts.py, schemas/ | Harness validation, inspect before reuse | Contracts are candidates for reuse; do not assume every current schema is domain-neutral |
| evaluation/runner.py | Mixed orchestration / target integration | Explicit clara_live branches remain; move target selection behind a declared adapter boundary when implementing extraction |
| evaluation/live_adapter.py, serve.py | Clara adapter / test-host integration | Clara transport, metadata and server access, not generic core |
| evaluation/local_database.py, event_fixture.py | Clara test-environment integration | Database provisioning/fixtures and target-specific assumptions; keep separate from generic run lifecycle |
| evaluation/persona_simulation.py | Mixed harness + domain + adapter | Student-specific prompts, education contract path and direct ClaraLiveAdapter import remain; extraction candidates, not reusable engine yet |
| evaluation/persona_comparison_summary.py | Reporting candidate | Verify input/protocol assumptions before generalising |
| evaluation/tests/test_degree_status.py, test_experience_status.py, test_experience_binding.py, test_suitability.py, test_discovery_context.py | Application tests despite directory | Keep commands working now; classify by tested component, not folder name |
| evaluation/tests/test_database_integration.py, test_live.py | Integration tests | Cross the target/harness boundary; split by responsibility only when useful |
| evaluation/tests/test_foundation.py, test_persona_metrics.py and other harness tests | Harness tests, with fixtures | Inspect individual assertions; an education example does not itself make an equality checker domain-specific |

This map is not a file-by-file certification. Folder placement alone is not proof
of abstraction. Existing entry points and tests stay operational during later moves.

## Fix-location decision rules

1. If the actual agent makes the wrong decision, retrieves the wrong information,
   corrupts user facts or gives unsupported advice: fix the application. Add domain
   regression evidence and application tests; do not weaken the rubric to pass it.
2. If the expectation, persona, selected authority or severity is wrong: fix the
   domain package or its source data. Record the owner decision where needed.
   Regrade preserved evidence; do not present that as improved agent behaviour.
3. If execution loses events, mishandles completion, misattributes tool results,
   mixes sessions or computes a generic check incorrectly: fix the harness or
   target adapter. Mark affected prior conclusions unreliable where applicable.
4. If the simulator invents personal facts, diagnose separately from Clara:
   persona specification belongs to the domain; generation/enforcement to the
   simulation engine; model performance is an experimental variable.
5. A model upgrade is a target/configuration intervention. Integration changes
   belong in the adapter/application; evaluation criteria remain fixed unless a
   separately justified domain decision changes them.

A finding can require more than one layer. Name a primary root cause and supporting
changes, rather than forcing everything into one bucket.

| Example from Clara | Primary fix | Supporting work |
|---|---|---|
| Experience parser assigns retail years to IT eligibility | Application | Application unit/integration tests; education dialogue regression |
| Rubric requires an action despite a valid honest stopping point | Domain | Owner criterion decision; regrade original run |
| Extended Thinking runner treats intermediate speech as final | Harness adapter/lifecycle | Transport contract tests before interpreting semantic results |
| Persona invents full-time employment | Domain or simulator implementation, diagnose first | Separate simulator-fidelity result; do not blame Clara for an invented input |
| Review labels a local run as production evidence | Review process | Correct dated disposition; preserve the original claim/history |

## Required finding / repair handoff fields

Use [the finding template](finding-template.md) for new repair packages:
primary layer; component; evidence; violated contract; proposed fix; supporting
layers; verification; uncertainty; owner decision if criteria change. A test's
location does not decide which layer owns the defect.

Prefer versioned scenario/check data over one script per defect. Add custom Python
for executable rules, adapters or checks that need it; keep investigations separate
from supported tooling. Skills describe the procedure, while decisions and reviews
carry the product conclusions.

## Bounded separation backlog

1. Apply this classification to the next repair/review; no file moves are required.
2. In a separately scoped extraction, externalise student simulator instructions
   and the education contract reference into the domain package, preserving the
   existing experiment behaviour and provenance. Demonstrate one education scenario
   selecting its domain assets and target adapter explicitly.
3. Isolate Clara-specific execution/session lifecycle behind an adapter capability
   contract. Missing audio, tool or state visibility must be explicit, not fabricated.
4. Validate the interface with a second use case before creating a separate reusable
   package. Keep raw private evidence outside public version control.

Steps 2–4 are proposed work, not completed refactors or authorization to launch runs.
Success means swapping domain assets and target integration without teaching the
core executor new business rules. Reuse is demonstrated by that exercise, not by
renaming directories. No private product or workplace details belong in this map.
