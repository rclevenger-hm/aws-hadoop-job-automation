import json
import logging
import time
from decimal import Decimal

import boto3
from botocore.config import Config

from app.config import settings
from app.emr import Emr
from app.service import Service, public
from app.store import Store
from app.validation import ApiError, STATES, body, digest, integer, principal

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)
_SERVICE = None


def runtime():
    global _SERVICE
    if _SERVICE is None:
        cfg = settings()
        common = Config(connect_timeout=3, read_timeout=5, retries={'total_max_attempts': 3, 'mode': 'standard'})
        # Zero SDK retries on the non-idempotent submission operation, including transport errors.
        emr_config = Config(connect_timeout=3, read_timeout=8, retries={'total_max_attempts': 1, 'mode': 'standard'})
        resource = boto3.resource('dynamodb', config=common)
        store = Store(resource.Table(cfg['table']), boto3.client('dynamodb', config=common), boto3.client('sqs', config=common), cfg['queue'],
                      cfg['daily_limit'], cfg['rate_limit'], cfg['retention'])
        _SERVICE = Service(store, Emr(boto3.client('emr', config=emr_config), boto3.client('s3', config=common)), cfg['profiles'], cfg['prefix'])
    return _SERVICE
