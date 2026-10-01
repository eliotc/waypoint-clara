# Contributing

Waypoint is a demonstration voice counsellor ("Clara") for a fictional university, together with the evaluation harness used to test it. Contributions are welcome. This guide covers how changes and evidence are handled.

## Before you start

- Read the [README](README.md) for setup, and [evaluation/README.md](evaluation/README.md) and [evaluation/architecture.md](evaluation/architecture.md) for the evaluation harness.
- The [learning journey](evaluation/journey/README.md) and [decisions](evaluation/decisions/) explain why the project works the way it does. Check them before changing established behaviour.
- All university data is synthetic. Consistency with it shows consistency with the demo data, not real admissions accuracy.

## Making changes

- Decide which layer a fix belongs to: the **application** (instructions, tools, guards), the **domain evaluation criteria** (what counts as correct advice), or the **reusable harness** (execution, records, reporting). See [Decision 0009](evaluation/decisions/0009-layer-ownership.md). Do not change the application to accommodate a grading mistake, or relax a criterion because a defect is hard to fix.
- Keep changes focused, and never overwrite or discard someone else's work to get a clean checkout.
- Every change is reviewed by someone other than its author. Label self-review honestly; it is not independent review.

## Tests

```sh
make eval-test
```

- Default tests must not contact paid models or external services. Mock transports; unsetting credentials alone is not enough.
- Tests that need a database use an isolated evaluation database with restricted, read-only credentials, never the application's write credentials.
- Record fixtures under `evaluation/tests/fixtures/` are labelled synthetic. Keep them that way, and never mix them into empirical results.

## Evidence and claims

- Distinguish implementation, offline verification, live execution, semantic acceptance and release approval. Passing tests do not show that a rubric is correct.
- Report commands, totals, skips, failures and limitations accurately. A planned check is not a completed check.
- Preserve original runs and assessments. Record a regrade or changed interpretation as a new record that names what it supersedes.
- Attribute assessments accurately, including automated and AI reviewers. Do not describe a review as human or independent unless it was.
- Synthetic personas and scripted runs are not evidence of real-user behaviour or acceptance.

## Learning record

At a meaningful learning boundary (a challenged assumption, an unexpected result, an evaluator false positive or negative), add a dated checkpoint using the [template](evaluation/journey/checkpoint-template.md) and link it from the journey index. Preserve earlier reasoning: supersede it with a new record rather than rewriting history.

## Privacy and security

Never commit credentials, `.env` files, private research, connection state, raw audio or unreviewed conversation traces. Generated runs under `evaluation/runs/` are ignored for this reason. Report security issues privately to the maintainer rather than in a public issue.
