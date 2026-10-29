# Agent Instructions

## Start here

- Read `CONTEXT.md` before naming or changing domain concepts.
- Read `PROJECT_CHECKPOINT.md` before implementation work to recover the current frontier and verified evidence.
- Read `handoff.md` when joining the project or resuming after a context reset; use `PROJECT_CHECKPOINT.md` for the newest status when historical sections differ.
- Use `MVP_PLAN.md` as the local MVP scope. Use `IMPLEMENTATION_PLAN_FINAL (1).md` only where it agrees with the approved graduation scope and newest checkpoint; its independent-storefront Steps 25–28 and broader production roadmap are not graduation prerequisites.
- Read `.scratch/shopping-copilot-local-mvp/spec.md` before product work. Its approved behaviour decisions override older plan wording when they conflict.
- Work on the next incomplete plan step unless the user explicitly reprioritizes the work.
- Keep each change within the active step and preserve unrelated user changes.

## Product gates

- Approved graduation scope: **Controlled Storefront only → Linux production-host preparation → model qualification and Stockholm (`eu-north-1`) Free-plan deployment**. Bedrock is the AWS candidate; the owner approves the current OpenRouter provider as fallback if Bedrock is unusable. Independent-storefront generalisation is strictly out of scope for this target and belongs to the post-graduation SaaS roadmap.
- The local MVP gate is closed under its recorded owner-approved amendments. Continue from `PROJECT_CHECKPOINT.md`; do not reopen it or require generalisation before host preparation or the Controlled Storefront AWS capstone.
- Preserve the Free-plan and $0-cash constraints. Actual AWS resources, public activation, model spending and deployment require their existing account, qualification, exact cost/resource/rollback and acceptance gates; local host preparation does not waive them.
- Configure the selected provider explicitly. The OpenRouter fallback preserves the current non-resetting $2 key cap and existing spend controls; it does not authorize top-ups, a higher cap, extra calls, or silent provider switching.
- Preserve the safety invariants: off-origin navigation is blocked, Sensitive Field values are excluded, Guarded Mutations require bound Confirmation, and stale or duplicate Actions are rejected.
- Preserve refresh recovery without automatically replaying an Action whose outcome is uncertain.

## Verification

- Test externally observable behaviour at the highest practical seam.
- Run focused checks while iterating, then the repository's relevant format, lint, test, and build commands before declaring work complete.
- Treat every safety invariant affected by a change as a required regression test.

## Agent skills

### Issue tracker

Specs and tickets are local Markdown files under `.scratch/`. See `docs/agents/issue-tracker.md`.

### Triage labels

Use the default five-role triage vocabulary. See `docs/agents/triage-labels.md`.

### Domain docs

This is a single-context repository despite its package layout. See `docs/agents/domain.md`.
