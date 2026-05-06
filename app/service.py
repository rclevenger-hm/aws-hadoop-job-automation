import uuid

from app.validation import ApiError, TERMINAL, digest, identifier, job_request, key_id


def public(job):
    fields = ['job_id', 'status', 'created_at', 'updated_at', 'step_id', 'cancel_requested', 'cancel_accepted', 'reason', 'expires_at']
    return {**{k: job[k] for k in fields if k in job}, 'profile': job['request']['profile']}


class Service:
    def __init__(self, store, emr, profiles, prefix):
        self.store, self.emr, self.profiles, self.prefix = store, emr, profiles, prefix

    def submit(self, caller, key, payload):
        request = job_request(payload, self.profiles, caller)
        tenant = digest(caller)
        job_id = key_id(key, tenant)
        job, created = self.store.create(tenant, job_id, request, self.profiles[request['profile']], f'{self.prefix}-{job_id}')
        if job['status'] == 'QUEUED':
            self.store.enqueue(job)
        return public(job), created

    def owned(self, caller, job_id):
        job = self.store.get(digest(caller), identifier(job_id))
        if not job:
            raise ApiError(404, 'NOT_FOUND', 'Job not found')
        return job

    def cancel(self, caller, job_id):
        for _ in range(4):
            job = self.owned(caller, job_id)
            if job['status'] == 'CANCELLED' or job.get('cancel_requested'):
                return public(job)
            if job['status'] in TERMINAL:
                raise ApiError(409, 'ALREADY_FINISHED', 'This job is no longer accepting cancellation')
            status = 'CANCELLED' if job['status'] == 'QUEUED' else 'CANCEL_REQUESTED'
            updated = self.store.replace(job, status=status, cancel_requested=True, next_check=self.store.now())
            if updated:
                return public(updated)
        raise ApiError(409, 'STATE_CHANGED', 'Job changed concurrently; retry the request')

    def attach(self, tenant, job_id, step_id=None, reason=None):
        for _ in range(5):
            job = self.store.get(tenant, job_id)
            if not job or job['status'] in TERMINAL or job.get('step_id'):
                return
            changes = {'next_check': self.store.now()}
            if step_id:
                changes.update(step_id=step_id, status='CANCEL_REQUESTED' if job.get('cancel_requested') else 'SUBMITTED', reason='')
            else:
                changes.update(status='CANCEL_REQUESTED' if job.get('cancel_requested') else 'SUBMISSION_UNKNOWN', reason=reason)
            if self.store.replace(job, **changes):
                return
        raise RuntimeError('Concurrent updates prevented step attachment; reconciliation will retry')

    def process(self, message):
        tenant, job_id = identifier(message.get('tenant')), identifier(message.get('job_id'))
        job = self.store.get(tenant, job_id)
        if not job or job['status'] != 'QUEUED':
            return
        if self.store.now() - job['created_at'] >= 86400:
            self.store.replace(job, status='FAILED', reason='QUEUE_ADMISSION_EXPIRED')
            return
        job = self.store.replace(job, status='SUBMITTING', submitted_at=self.store.now(), dispatch_token=str(uuid.uuid4()), next_check=self.store.now() + 120)
        if not job:
            return
        # AddJobFlowSteps has no idempotency token. Never retry this call automatically.
        try:
            step_id = self.emr.submit(job)
        except Exception:
            self.attach(tenant, job_id, reason='SUBMISSION_OUTCOME_UNKNOWN')
            return
        self.attach(tenant, job_id, step_id=step_id)

    def reconcile_one(self, tenant, job_id):
        job = self.store.claim_poll(tenant, job_id)
        if not job:
            return
        if job['status'] == 'QUEUED':
            if self.store.now() - job['created_at'] > 86400:
                self.store.replace(job, status='FAILED', reason='QUEUE_ADMISSION_EXPIRED')
            else:
                self.store.enqueue(job)
            return
        if not job.get('step_id'):
            # Allow the submitter to finish before looking for a lost response.
            if self.store.now() - job.get('submitted_at', job['created_at']) < 120:
                return
            matches, marker = self.emr.find(job)
            if len(matches) > 1:
                self.store.replace(job, status='NEEDS_REVIEW', reason='MULTIPLE_MATCHING_STEPS')
            elif marker:
                self.store.replace(job, scan_marker=marker, scan_matches=matches, next_check=self.store.now() + 30)
            elif matches:
                self.attach(tenant, job_id, step_id=matches[0])
            elif self.store.now() - job.get('submitted_at', job['created_at']) > 86400:
                self.store.replace(job, status='NEEDS_REVIEW', reason='NO_STEP_FOUND_OUTCOME_STILL_UNKNOWN')
            else:
                self.store.replace(job, status='CANCEL_REQUESTED' if job.get('cancel_requested') else 'SUBMISSION_UNKNOWN', scan_marker='', scan_matches=[], reason='SUBMISSION_OUTCOME_UNKNOWN')
            return
        state = self.emr.status(job)
        changes = {'status': state}
        if job.get('cancel_requested') and state not in TERMINAL:
            changes.update(status='CANCEL_REQUESTED', cancel_accepted=self.emr.cancel(job))
        self.store.replace(job, **changes)

    def reconcile(self, remaining_ms=lambda: 120000):
        processed, failed = 0, 0
        # Rotate the first shard to avoid starving later shards on a busy minute.
        start = (self.store.now() // 60) % 16
        for offset in range(16):
            if remaining_ms() < 20000:
                return {'processed': processed, 'failed': failed}
            shard = format((start + offset) % 16, 'x')
            for job in self.store.due(shard):
                if remaining_ms() < 20000:
                    return {'processed': processed, 'failed': failed}
                try:
                    self.reconcile_one(job['pk'], job['job_id'])
                    processed += 1
                except Exception:
                    failed += 1
                    # Lease moved next_check forward. Never re-submit an ambiguous job.
        return {'processed': processed, 'failed': failed}
