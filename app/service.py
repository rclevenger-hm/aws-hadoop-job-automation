import uuid

from app.validation import ApiError, TERMINAL, digest, identifier, job_request, key_id


def public(job):
    fields = ['job_id', 'status', 'created_at', 'updated_at', 'step_id', 'cancel_requested', 'cancel_accepted', 'reason', 'expires_at']
    return {**{k: job[k] for k in fields if k in job}, 'profile': job['request']['profile']}
