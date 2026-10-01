# Clara visitor entry and live example — revised direction

Date: 2026-09-18. Owner: Eliot. Implementer: Hermes. Reviewer: Codex.
Status: approved product direction; implementation handoff must resolve runtime details before coding the live runner. No deployment authorized by this document.

## Authority and scope

This document supersedes the recorded-first entry, quiet-footer-only navigation, and static-only scope in public-showcase-v1.md and public-showcase-ux.md. Preserve those documents and recording artifacts as history. Do not continue the three-recording gallery milestone as the primary experience.

Owner chose two explicit branches: **Watch a live example** and **Ask Clara yourself**. Start with one fixed, versioned persona and scripted student turns. Clara responds live on the existing Gemini Live 3.1 configuration. Do not add adaptive student agents, custom personas, model migration, or evaluation of visitors' personal conversations in this slice.

## Landing state at /

Lead with the student problem:

**Unsure which course fits your circumstances?**
See how Clara helps you explore study options and understand what remains uncertain.

Two clearly separated choices with equal visual discoverability:

- **Watch a live example**
  Follow a scripted student's questions and hear Clara respond live. See automated checks of this conversation afterwards.
- **Ask Clara yourself**
  Talk or type about your interests, experience and study needs.

Below both: “Demonstration using a fictional university and sample course information.” Keep this visible but subordinate to the benefit. Remove competing “Explore options with AI” entry copy.

Use the existing conversation area for this welcome state rather than adding a third panel or covering the workspace with a modal. The right research panel is a quiet empty state: “Course information will appear here when you talk to Clara.” On mobile, show the two choices before any research-panel empty state. No microphone permission, live session, model greeting, or audible playback on landing.

## Branch A: Watch a live example

Navigate to /showcase, a distinct watch-and-review view. Show one scenario, not a gallery of disabled future choices:

**Can I return to study without a degree?**
A fictional student has IT work experience and wants to explore further study.

Clearly label “Scripted student · Clara responds live”. Show the persona facts and intended questions before starting. Exact facts and messages must come from the versioned scenario, not duplicated copy that can drift.

Action: **Start live example**. This explicit gesture starts the bounded run and enables audio; no visitor microphone is needed. The landing choice only navigates, avoiding unexpected audio or spending before the visitor sees the scenario.

Show scripted student messages and fresh Clara transcripts/audio as turns occur. Submit the next fixed message only after the prior response finishes. Provide **Stop example**. States: Ready → Connecting → Live conversation → Checking this conversation → Results; include stopped, failed, and evaluation-unavailable states. Never show a recording or cached judgment as a live result.

Keep the existing two-column conversation/findings concept. During conversation, the right side says “What we will check”; after completion it displays findings tied to this run. On mobile put the short criteria before the conversation and findings below it. No Research Panel plus findings third column.

Evaluation uses the actual captured transcript and tool results. Distinguish automated checks, provisional AI judgments, and human-reviewed observations. Missing evidence or judge failure produces “Unable to assess”, never an inferred pass. No overall trust score. Judge model configuration and live-run transport need a concrete technical handoff; do not guess a model identifier.

After completion: **Ask Clara yourself** starts a fresh personal conversation, without transferring persona facts. **Run example again** is secondary and creates a new run. Any recording fallback must require explicit selection and say “Previously recorded example”.

## Branch B: Ask Clara yourself

Stay on / and replace the welcome choices with the existing conversation UI; retain the Research Panel. Establish the personal session only after this branch is selected. Do not request microphone permission merely from selecting the branch.

Before the first message, show:

**What would you like help with?**
“Tell Clara what you want to study, or what needs to fit around your life.”

Give the input a useful placeholder: “For example: I work full-time and need an online course.”
Keep the microphone action visibly labelled **Talk to Clara**, with adjacent **or type a message** guidance and a visible text input/send control. Microphone permission follows that explicit action; denial leaves typing available.

Optional starter suggestions are editable drafts, never silently submitted:
- “I’m not sure what to study.”
- “I need an online course.”
- “Could my work experience help me get in?”

Once the visitor begins, collapse introductory guidance so the conversation and retrieved information take priority. Keep “Watch a live example” as secondary navigation, not a competing primary control. Existing Under the hood remains a tool-activity explanation.

## Navigation and session lifecycle

Never share live-example context with personal conversation context. Leaving an active personal conversation requires clear confirmation and complete microphone, screen-sharing, playback and WebSocket cleanup. Leaving/stopping a live example cancels its runner and pending evaluation work where possible. Back/refresh never silently resumes an old run, submits another scripted turn or starts audio. Landing and chooser states must not consume live model capacity.

## Bounded implementation sequence

1. Hermes prepares a concrete delta against existing Milestone A: routes, lazy session initialization, live runner and cancellation, server-side fixed script enforcement, read-only tools, admission/concurrency/cost bounds, per-run evidence contract, judge integration, and tests. Reuse reviewed evidence/export concepts without importing offline evaluation modules into production. Server must not accept arbitrary script/model/tool arguments from visitors.
2. Implement the two-branch welcome and personal-conversation onboarding as the first reviewable UI slice. Do not expose a nonfunctional live CTA publicly or disguise recordings as live. Owner reviews desktop/mobile interactions manually.
3. Connect one fixed live scenario and then its per-run evaluation. Validate separation, bounded execution, interruptions, failures, evidence grounding and fresh-session behavior before release review.

## Acceptance

A first-time visitor can tell which action lets them watch and which lets them talk. They can start their own text or voice conversation without guessing what to press. Watching requires no microphone. The live example genuinely generates new responses, results refer only to that run, and uncertainty is visible. Public deployment remains a separate reviewed action.
