# Operations and incident response

## Unknown submission

Treat `SUBMISSION_UNKNOWN` as potentially running. A timeout, permission error or unavailable EMR response does not cause automatic resubmission. Look up the persisted step name and cluster using privileged operator access. Reconciliation searches all pages, saving progress. Multiple matches or no match after a day transitions to `NEEDS_REVIEW`; this ends automation, not the remote workload.

To resolve review, inspect EMR steps, YARN applications and output paths. If a matching step exists, an operator can attach the verified ID and resume tracking through a reviewed conditional metadata repair. This repository intentionally exposes no public arbitrary redrive or reset-to-queued endpoint. Submit with a new key only after deciding a new execution is safe. Preserve incident evidence before modifying state.

