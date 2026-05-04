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
