import base64
import json
import logging
import time
from datetime import datetime, timezone
from decimal import Decimal

from boto3.dynamodb.conditions import Key
from boto3.dynamodb.types import TypeSerializer
from botocore.exceptions import ClientError

from app.validation import ApiError, TERMINAL, canonical, digest, invalid

SERIALIZER = TypeSerializer()


def encode(item):
    return {k: SERIALIZER.serialize(v) for k, v in item.items()}
