# Public showcase UX/UI specification

> Superseded direction (2026-09-18): see [live showcase v2](public-showcase-live-v2.md). Recorded-first navigation and static-only scope below are historical; retain artifacts, but implement the two-branch live direction.

Date: 2026-09-17. Design proposal for Eliot and implementation reference for Hermes.
Companion: public-showcase-v1.md. This document refines layout and navigation;
it does not authorize implementation beyond the handoff's review checkpoints.

## Main design decision

Two distinct page experiences, never four simultaneous panels:
- /: existing live conversation and Research Panel.
- /showcase: recorded conversation and findings about that recording.

Do not put personas above the live chat, evaluations below the Research Panel,
or introduce a third sidebar. Do not make the existing Under the hood toggle
switch to evaluation: it explains live tool activity and retains that meaning.
A showcase is a separate activity with its own page and URL, not a modal covering
an active conversation. No live agent/session runs on the showcase page.

## Entry from the live page

Use one quiet text link: 'Recorded examples'.
Place it in the existing bottom 'Waypoint / For Universities' footer, with wrapping
on narrow widths. No new header icon, navigation bar, permanent banner or toolbar.
Do not add it to the expanded risk/limitations text; this is navigation, not a warning.
A richer introductory entry can be designed later if a separate landing page emerges.

Navigate in the same tab, to /showcase. The current page establishes a connection
automatically; changing pages must close its live connection and stop microphone,
screen sharing and playback via verified teardown. Reuse existing cleanup methods.
Do not assume selecting the link is safe merely because the student hasn't spoken.
When a live connection is present, show one explicit navigation confirmation:
'Leave this conversation to view recorded examples? Returning starts a new conversation.'
Buttons: 'Stay here' and 'View examples'. Never claim the conversation is saved.
This is the only new confirmation and protects the existing session. A dialog must
have proper keyboard focus, Escape/cancel, and focus return. If there is no active
connection, navigate directly. Do not open a second competing microphone session.
Do not add this Kingsford-specific entry to /demo/<id> in v1.

The showcase CTA is 'Start your own conversation', leading to /. It starts the
existing fresh-session flow and does not carry student/scenario facts.
Pause recorded playback before navigation. Browser Back into a recording must
not automatically resume audio or open a model session.

## Screen 1: browse recorded examples

A compact ordinary document, maximum width approximately 1120px, centred:
- Small Waypoint brand/back navigation.
- H1: 'See how Clara is tested'.
- Lead: 'Explore recorded conversations with fictional students. See what Clara
  answered, the evidence behind it, and what remained uncertain.'
- Small label: 'Recorded examples · Gemini Live 3.1'. Avoid status-dot styling.
- Three scenario cards in a row on wide screens, stacked on mobile.
- One short footer note on fictional data and that results apply to each recording.

Cards:
- Returning to study / 'Work experience, no bachelor's degree'
- Online-only study / 'A course goal with a firm attendance constraint'
- Unsure what counts / 'Mixed work and study experience'
Each has a two-line maximum goal, captured duration when available and
'View example'. Use scenario-first labels, not fictitious portraits or biographies.
Do not decorate the cards with PASS badges or aggregate scores.

On first visit show this selection view, not an automatically playing example.
Support direct links /showcase?example=<id> to a valid example; invalid IDs show a
useful not-found message and scenario chooser. Query parameters select static
assets from the allowlisted catalogue, never arbitrary paths/URLs.

## Screen 2: selected recording (desktop)

+-----------------------------------------------------------------------+
| Waypoint   Recorded examples                                          |
| < All examples                         Returning to study v            |
| Returning to study                                                    |
| Work experience, no bachelor's degree                                  |
| Recorded example · Live 3.1 · [actual duration]                         |
| Student goal: explore cloud study while keeping eligibility uncertain. |
+------------------------------------------+----------------------------+
| CONVERSATION                             | WHAT WE CHECKED            |
| Scripted student text, recorded replies  | 1. Disclosed facts         |
|                                          | 2. Grounded course advice  |
| Student                                  | 3. Honest uncertainty      |
| [Complete opening message]               |                            |
|                                          | WHAT WE OBSERVED           |
| Clara                                    | [observation + short       |
| [Native play / seek / volume]             | explanation]               |
| [Complete captured transcript]           | [See supporting turn]      |
|                                          | > View source evidence     |
| Student                                  |                            |
| ...remaining turns...                    | [next observation...]      |
+------------------------------------------+----------------------------+
| > How this example was evaluated                                      |
| > Limits of this example                                              |
| Want to explore your own situation? [Start your own conversation]      |
+-----------------------------------------------------------------------+

Desktop content proportion approximately 64% conversation / 36% findings.
Use one normal page scroll, not separate scroll boxes. The findings column can be
position: sticky only when its full content fits the viewport; default non-sticky.
Do not reproduce the live Research Panel in the showcase. Relevant catalogue
facts appear only as evidence within a finding. No charts, gauges or running score.

'All examples' returns to the chooser without loading the live app. The small
scenario select permits switching while reviewing; it replaces, rather than adds
to, the three large chooser cards. Pause current audio before changing examples.
Use a native select with an accessible label, not a custom dropdown in v1.

Criteria are visible before findings. Results do not need to wait for playback:
this is a reviewed recording, not a test happening now. Do not show fake progress,
typing, 'judging...' animations or a 'Live' indicator.

## Mobile

Below approximately 800px, one column in DOM reading order:
1. Example title, goal and recorded/model label.
2. Three short criteria.
3. 'Jump to observations' anchor.
4. Full conversation with per-turn playback.
5. Findings and evidence accordions.
6. Method/limits and own-conversation CTA.

No narrow desktop sidebar, horizontal carousel, nested tabs or sticky bottom panel.
Audio controls must fit without horizontal scrolling. Minimum 44px touch targets
for scenario selection, playback surroundings, evidence links and navigation.
Evidence jump links move keyboard focus appropriately and respect reduced motion.
Provide a 'Back to observation' link when jumping into a supporting turn.
Transcript text should remain comfortably readable at 200% zoom.

## Findings hierarchy and interaction

Use a plain heading and subtle icon + text:
- 'Supported in this recording'
- 'Issue observed'
- 'Not assessed'

Each finding: criterion name, status, one or two explanatory sentences, and a
'See turn N' link. Exact quote may appear inline if short; tool/source excerpts
are in a native details/summary disclosure labelled 'View source evidence'.
Keep evidence adjacent to its finding; never introduce another panel or modal.

Example presentation only (not publishable findings until reviewed):
Criterion: Preserve uncertainty
Status: Supported in this recording
Explanation: Clara left eligibility unconfirmed when experience was unclear.
Evidence: link to the exact captured statement and relevant tool field.

Do not equate an individual supported finding to an overall passed conversation.
Do not colour the entire page green or use a large red failure banner. Status must
remain understandable without colour. A visible 'Reviewed observations' label
links to the method section; disclose AI judge and AI reviewer roles accurately.

## Visual styling

Reuse existing brand colours, typography and rounded forms; use quieter surfaces
and adequate text contrast for reading. Keep screenshots/avatar imagery optional;
no new image generation is required. Match the site without copying all its
control density or background effects.
A single primary action is sufficient at each stage: 'View example', then
'Start your own conversation'. Evidence/technical controls are secondary links
or disclosures. Keep model version in a compact recorded-example label and
technical details in the expandable method section.

## State and failure behaviour

- Loading catalogue: brief textual loading state; no fake conversation placeholders.
- Catalogue unavailable: retry link and route to live Clara; do not show fake results.
- Example fails to load: retain chooser and show error, not previous example data
  under the new title.
- Audio unavailable: transcript and findings stay available; identify the failed
  audio turn. Never imply listening has occurred.
- Missing reviewed findings: local preview labels review pending; publication
  validator blocks it. Runtime must not fabricate a supported finding.
- Only one recorded reply can play at once. Switching scenario resets playback.
- Playback controls never submit anything to Clara or request microphone access.
- Scenario selection is URL-addressable, with Back/Forward restoring selection;
  restored playback stays paused.
- No reading auto-scroll while audio plays. Visitors control their reading position.

## First design checkpoint for Hermes

Before building the full gallery, supply desktop (e.g. 1440x900) and mobile
(e.g. 390x844) views of:
1. Chooser.
2. One selected example.
3. Expanded evidence.
4. Navigation away from an active live session.

A lightweight local HTML prototype or screenshots from Milestone A are enough.
Clearly label placeholder text/evidence and do not present it as a real test.
Eliot reviews hierarchy and density; Codex reviews claims, navigation/session
lifecycle, accessibility and scope. No changes to live chat/Research Panel
composition are planned except the single footer entry.

Acceptance: a new visitor can answer 'Is this live or recorded?', 'Whose
conversation is this?', 'What was checked?', and 'How do I try my own?' without
opening technical details. Evaluation is reachable without dominating the live UI.
