import zlib
from urllib.parse import urlsplit

from botocore.exceptions import ClientError
from app.validation import ApiError

REMOTE_STATES = {'PENDING': 'SUBMITTED', 'CANCEL_PENDING': 'CANCEL_REQUESTED', 'RUNNING': 'RUNNING',
                 'COMPLETED': 'SUCCEEDED', 'CANCELLED': 'CANCELLED', 'FAILED': 'FAILED', 'INTERRUPTED': 'FAILED'}
MAX_LOG = 1024 * 1024


class Emr:
    def __init__(self, client, s3):
        self.client, self.s3 = client, s3
