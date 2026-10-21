# Run the queue and browse finished claims

Requested by the student after the pilot: add a control that runs the entire waiting queue and tabs that separate work still requiring attention from finished claims.

## Behavior

- Run queue snapshots all waiting, undecided claims and reviews them sequentially with the existing agent. It returns immediately, runs on the backend and continues when the browser closes.
- Only one queue run can be active. Claims started individually after the snapshot are skipped; existing decisions, running claims and payments are never rerun or replaced.
- Each snapshot claim is attempted once. A failed claim stays available for an explicit retry, and the batch continues with the remaining claims. Show reviewed/attempted count, failures, skipped claims and the current claim. Preserve progress across page refreshes; an interrupted backend marks the batch stopped without automatically rerunning model calls.
- Queue contains waiting, running, sign-off-pending and unpaid claims. Finished contains decided claims, including approve/decline/refer, with decision and payout visible in the list and full evidence accessible by selection.
- Over-limit approvals still require handler sign-off. They move to Finished after the separate payment succeeds.
- The Run queue control explains that it uses the configured model through OpenRouter. Building this feature does not automatically execute the real queue.

## Verification

- [x] Backend tests cover an entire 25-claim snapshot, sequential execution, duplicate queue requests, no eligible claims, concurrent individual starts, failure continuation, preserved payments/sign-off and restart interruption.
- [x] Dashboard tests cover starting/error/retry, progress polling, correct tab membership/counts, empty states and opening finished claims.
- [x] Playwright runs a full queue with the scripted model, checks refresh-persistent progress and finished claims, verifies sign-off is still required, and checks desktop/mobile layouts.
- [x] Full `npm run check` passes with existing thresholds; update `docs/STATUS.md` and commit the verified changes without including the student's lockfile change.

## Reset tab

Also requested during this build: add a Reset dashboard tab to start the pilot over. It clears decisions, sign-offs, simulated payments, activity and batch progress, returning all existing claims to waiting while retaining all source evidence, policies/customers/plans/handlers and configuration. It must refuse resets while a batch or individual agent is running, enforce a required `RESET` confirmation in the API and UI, and never trigger a reset merely by opening the tab. Test on isolated databases only; do not reset the student's development data during this build.

- [x] API and dashboard tests verify exact confirmation, active-run blocking, preserved source records and cleared workflow/progress; Playwright demonstrates reset followed by another queue run on its temporary database.

Verified with `npm run check`: 36 Python tests (99.77% coverage), 16 dashboard tests (100% statement coverage), and 11 Playwright tests. The browser suite completed two whole-queue passes with a reset between them, using a temporary database and scripted model. Desktop Finished and mobile/dark Reset screenshots were inspected. No development claims were run or reset during verification.
