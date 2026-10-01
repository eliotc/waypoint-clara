# Decision 0013: Public repository boundary

Date: 2026-09-30. Status: accepted owner direction. Owner: Eliot.
Source: owner interview on publication scope, following an independent publication-inventory critique.

The public repository exists to help people use, understand and contribute to Clara. Absence of credentials is not a reason to publish; each item needs a positive reason to be public.

## Screening rules

| Question | Default |
|---|---|
| Does it help someone use, understand or contribute to Clara? | Candidate for publication. |
| Does it reveal broader platform architecture, commercial plans or agent operating methods? | Keep private. |
| Does it contain benchmark cases or reference answers? | Keep private unless designated development material. |
| Does it make empirical claims? | Publish only with verified provenance, stated limitations and review disposition. |
| Does it name partners or compare vendors? | Keep private unless separately approved. |
| Is it a credential, private trace or recovery artifact? | Never publish. |

## Decisions

1. **Collaboration guidance:** publish a generic contributor guide covering evidence rules, independent review of changes, and preserving others' work. The detailed multi-agent working agreement stays private. Tooling and procedures optimised for the owner's own agent workflow — including repository agent skills and agent implementation handoffs — stay private (added 2026-09-30).
2. **Platform and routing design:** material describing broader platform architecture or agent task routing lives in a separate private repository, not here. Public checkpoints may cite the resulting evaluation principles for Clara without that material.
3. **Benchmark material:** trust families 1–3 are development material and may be published as worked examples. Later families and any held-out cases stay private to preserve their eligibility for future held-out evaluation. Keeping files private does not by itself establish that they were unused during development.
4. **Vendor comparisons:** evaluator and model comparisons naming vendors stay private. Vendor-specific adapters without a public consumer are excluded (added 2026-09-30).
5. **Empirical evidence:** outcome records and experiment reports stay private until provenance is verified and each carries its limitations and review disposition. A recorded review alone does not establish acceptance or publication suitability; each report is reviewed individually. Reports whose findings were not accepted are not published as results. The synthetic harness experiment and fixtures required by public tests may be published, clearly labelled synthetic (added 2026-09-30).
6. **Illustrative records:** records whose provenance fields contain placeholder values are superseded by records explicitly marked illustrative. Neither the illustrative replacements nor their superseded originals contribute to any empirical metric or trend, current or historical. Both may appear in an audit-history view, clearly labelled illustrative or superseded. Originals are preserved, in line with the append-only record policy.
7. **Private preservation:** selected material worth keeping but outside this boundary is preserved in a separate private repository. Recovery artifacts containing material removed from this repository's history stay in local private storage unless separately authorized. An ignore rule is not a preservation strategy.
8. **Attribution:** preserve accurate authorship of records, including AI agents. Call a review independent only where independence is supported, and never imply human review where an agent performed it (added 2026-09-30).
9. **Public summaries:** where supporting evidence is withheld, public documents state that it is withheld and stand on their own; rejected content is not retained merely to keep links working (added 2026-09-30).
10. **Release method:** a release candidate is one curated commit on a review branch based on the public main branch, containing only approved files. Preparation order: assemble the candidate tree, fix links and run tests, scan that exact tree, review the diff, then create the authorized commit. Publishing requires separate approval. Development history is not published. This does not change anything already public.

## Boundaries

This decision sets scope only. It does not authorize a branch, commit, push, deployment, record migration or private-repository creation; each needs separate owner authorization. Publication review does not establish release readiness or evaluation correctness.

Primary owner: repository governance. Related: [Decision 0001](0001-foundation.md) (repository foundation).
