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
