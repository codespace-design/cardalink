from __future__ import annotations

import base64
import hashlib
import logging
import os
from typing import Any

from cryptography.fernet import Fernet
from cryptography.fernet import InvalidToken
from django.conf import settings
from django.db import models

logger = logging.getLogger(__name__)


def get_field_fernet() -> Fernet:
    """Retrieve or derive the Fernet cipher instance using FIELD_ENCRYPTION_KEY.

    Never uses SECRET_KEY to prevent coupling session/CSRF rotation with data-at-rest.
    """
    key = getattr(settings, "FIELD_ENCRYPTION_KEY", "") or os.environ.get("FIELD_ENCRYPTION_KEY", "")
    if not key:
        # Deterministic fallback for dev/tests if env is not yet set
        derived = hashlib.sha256(b"cardalink-field-encryption-fallback-key").digest()
        key = base64.urlsafe_b64encode(derived).decode()
        logger.warning(
            "FIELD_ENCRYPTION_KEY is not set. Using local development fallback key."
        )

    if isinstance(key, str):
        key_bytes = key.strip().encode("utf-8")
    else:
        key_bytes = key

    # Ensure key is valid 32 url-safe base64 bytes
    try:
        return Fernet(key_bytes)
    except Exception as exc:
        derived = hashlib.sha256(key_bytes).digest()
        safe_key = base64.urlsafe_b64encode(derived)
        return Fernet(safe_key)


class EncryptedCharField(models.CharField):
    """CharField that encrypts data on write and decrypts data on read using Fernet.

    Stores the base64 Fernet token in the underlying database column.
    """

    description = "Fernet-encrypted CharField for sensitive at-rest data"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("max_length", 255)
        super().__init__(*args, **kwargs)

    def get_prep_value(self, value: Any) -> Any:
        value = super().get_prep_value(value)
        if value is None or value == "":
            return value

        str_val = str(value)
        fernet = get_field_fernet()

        # Check if already a valid fernet token to avoid double encryption
        try:
            fernet.decrypt(str_val.encode("utf-8"))
            return str_val
        except (InvalidToken, Exception):
            pass

        encrypted = fernet.encrypt(str_val.encode("utf-8")).decode("utf-8")
        return encrypted

    def from_db_value(
        self, value: Any, expression: Any, connection: Any
    ) -> Any:
        if value is None or value == "":
            return value

        fernet = get_field_fernet()
        try:
            return fernet.decrypt(str(value).encode("utf-8")).decode("utf-8")
        except (InvalidToken, Exception):
            # Return raw if not valid token (e.g. legacy plain test values)
            return value

    def to_python(self, value: Any) -> Any:
        if value is None or value == "":
            return value

        str_val = str(value)
        fernet = get_field_fernet()
        try:
            return fernet.decrypt(str_val.encode("utf-8")).decode("utf-8")
        except (InvalidToken, Exception):
            return str_val
