# DexTilt Operational State

project_id: dextilt
project_name: DexTilt
revision: 2
last_updated: 2026-09-17
scope: Android motion-command client plus Mac receiver/dashboard

## Current baseline

- Branch: `main`
- Parent before this revision: `20dcf2d9ea044d0fddecc74b54140f64bed764ff`
- Current change: stable face-down end is now an explicit completion invariant for armed gestures and both training passes.
- Implementation commit: `9cc8becb0ecd134e2433382912b7320c87ac117b`
- Publication: implementation commit is on `main`; this documentation follow-up records the hash additively.

## Artifact contract

- DexTilt is a local-first, post-login motion-command layer between the paired Android phone and the Mac receiver.
- Android sends authenticated command IDs; it does not send arbitrary shell commands.
- Gesture-triggered execution must remain conservative: explicit arm, stable face-down start, captured motion, stable face-down end, successful recognition, then receiver-side command acceptance.
- Manual fallback commands and pairing remain available even when gesture recognition is unavailable.

## Active invariants

### DT-INV-001 — Stable-end command gate
State: protected / implemented in revision 1

A gesture may reach matching or execution only after a stable face-down end has actually been observed for the configured hold duration. Reaching the maximum capture duration without that end state is a rejection.

Proof obligations:
- timeout without stable face-down end -> no matching and no command;
- timeout during training without stable face-down end -> no saved training pass/template;
- stable face-down end held for at least 600 ms before or at the duration limit -> capture may complete.

### DT-INV-002 — No raw remote shell
State: protected / evidence-stale but source-backed

Android sends command IDs to the receiver allowlist. This repair must not add a raw shell path.

### DT-INV-003 — Stale phone-control requests do not execute after reconnect
State: protected / previously implemented / current device proof stale

Receiver TTL plus Android reconnect drain/staleness checks remain in place.

## Verified in this revision

- Pure Kotlin `GestureCapturePolicy` compiled and executed in an isolated Kotlin/JVM harness on 2026-09-17.
- Five boundary cases passed: ordinary continue, valid stable-end completion, timeout rejection without stable end, timeout rejection with an insufficient 599 ms hold, and valid completion at the 5000 ms duration boundary.
- Source guard check confirms the old timeout-to-`finishArmedGesture()` and timeout-to-`finishTrainingPass(...)` bypass paths are removed.

## Implemented but unverified

- Full Android/Compose project build for this revision: not run in the current runtime.
- Galaxy S21 physical sensor path for this revision: not run because the authorized Mac/ADB node is offline.
- Existing Mac receiver/runtime behavior is outside this repair's code impact radius and was not rerun.

## Known not-working / current defects

- The dashboard still references Google Fonts and Three.js from public CDNs, so the strongest possible "fully offline dashboard" claim is not currently true.
- Screen-off/background armed sensing remains unverified; the current Android manifest does not establish the planned foreground armed-service architecture.

## Evidence-stale

- Earlier project records report successful Android debug builds and Mac receiver checks from 2026-04-26. They are historical evidence, not proof for this revision.
- Existing README/test-plan wording still contains portions of the older Open-GPT-era flow and should not be treated as the sole current source of truth.

## Pending

1. Run `./gradlew test` or the repository Android test command on the Mac toolchain.
2. Build the debug APK and install it on the Galaxy S21.
3. Physically verify DT-INV-001 using the timeout and valid-end paths in `docs/test_plan.md`.
4. Then continue the planned Armed foreground service and sequence-recognition work.
5. Bundle dashboard web assets locally before claiming completely offline dashboard operation.

## Validation matrix

| ID | User path / property | Current evidence | State |
| --- | --- | --- | --- |
| DT-INV-001A | Armed timeout without stable end sends no command | Pure policy harness + source guard | partially-verified |
| DT-INV-001B | Training timeout without stable end saves nothing | Pure policy harness + source guard | partially-verified |
| DT-INV-001C | Valid stable end still completes | Pure policy harness | partially-verified |
| DT-INV-002 | Android cannot send raw shell commands | Existing source/docs, not rerun | evidence-stale |
| DT-INV-003 | Reconnect does not execute stale dashboard control | Existing implementation record, not rerun | evidence-stale |
| DEVICE-001 | Galaxy S21 end-to-end gesture execution | No current hardware run | pending |

## Revision history

### Revision 2 — 2026-09-17

Recorded implementation commit `9cc8becb0ecd134e2433382912b7320c87ac117b` after verified publication to `main`. No behavior claims were promoted beyond the evidence already recorded.

### Revision 1 — 2026-09-17

Bootstrapped current operational state and promoted the face-down completion rule into DT-INV-001 after discovering that timeout paths could previously call matching/training finalization without observing the required stable face-down end.
