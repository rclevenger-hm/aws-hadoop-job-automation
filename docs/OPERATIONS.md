# Operations and incident response

## Unknown submission

Treat `SUBMISSION_UNKNOWN` as potentially running. A timeout, permission error or unavailable EMR response does not cause automatic resubmission. Look up the persisted step name and cluster using privileged operator access. Reconciliation searches all pages, saving progress. Multiple matches or no match after a day transitions to `NEEDS_REVIEW`; this ends automation, not the remote workload.

To resolve review, inspect EMR steps, YARN applications and output paths. If a matching step exists, an operator can attach the verified ID and resume tracking through a reviewed conditional metadata repair. This repository intentionally exposes no public arbitrary redrive or reset-to-queued endpoint. Submit with a new key only after deciding a new execution is safe. Preserve incident evidence before modifying state.

## Queue and reconciliation incidents

A failed intake publish can return 503 after a job was persisted. Retry the same key; do not generate a replacement key. Scheduled recovery republishes queued rows. SQS failures use partial batch reporting and eventually reach a 14-day DLQ. Inspect each payload's tenant/job hashes and current job state before redrive: only queued jobs can submit. Correct infrastructure/IAM problems before replaying messages.

A queued job older than one day is marked failed without execution. An active remote job has no metadata TTL, so it cannot disappear merely because it ran longer than expected. Reconciler errors advance the polling due time and raise a Lambda error for alarming; transient problems will be revisited. A persistently invalid EMR pagination marker or missing step requires operator investigation rather than guessed resubmission.

