# Decision 0002: Adopt provisional Clara behavioral rules

Date: 2026-09-06. Owner: Eliot. Status: accepted for the demonstration baseline.

The owner accepted the five proposed rules covering grounding/images, online
course availability, sufficient recommendation context, human handover, and
latency/recovery. The authoritative wording is maintained in the
[education behavior contract](../domains/education/contract.md).

This resolves the product-direction ambiguities without requiring a final
production policy. Database evidence governs factual answers; clarification is
judged by decision relevance rather than a fact count; unsupported handovers
must not be claimed; recovery avoids stale output and duplicate actions.

Numerical latency thresholds follow baseline measurement. Clarification quality
will be refined through persona experiments. Severity assignments and release
criteria remain proposed. The agreement does not approve a live deployment or
adjudicate EXP-000's pending human check.

Next: align the runtime prompt and manual expectations with these rules, then
establish isolated fixtures and the Live adapter. Prior run snapshots retain the
contract version they used; do not rewrite historical evidence.
