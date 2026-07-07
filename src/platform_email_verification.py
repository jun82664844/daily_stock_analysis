# -*- coding: utf-8 -*-
"""Local registration email verification-code service.

This module intentionally keeps delivery local-only for the current product
phase. Production SMTP/provider delivery can be attached behind the same
request and verify methods later.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from dataclasses import dataclass
from threading import Lock
from typing import Dict, Tuple


_RecordKey = Tuple[str, str]


@dataclass(frozen=True)
class RegistrationVerificationCode:
    email: str
    code: str
    expires_in_seconds: int


@dataclass
class _VerificationRecord:
    code_hash: str
    expires_at: float
    attempts: int = 0


_records: Dict[_RecordKey, _VerificationRecord] = {}
_lock = Lock()


def _truthy_env(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def email_verification_required() -> bool:
    return _truthy_env("PLATFORM_EMAIL_VERIFICATION_REQUIRED", "false")


def registration_dev_code_visible() -> bool:
    return _truthy_env("PLATFORM_EMAIL_VERIFICATION_DEV_CODE_VISIBLE", "true")


def _int_env(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
    return max(1, value)


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def _scope() -> str:
    return os.getenv("DATABASE_PATH", "")


def _record_key(email: str) -> _RecordKey:
    return (_scope(), email)


def _secret_bytes() -> bytes:
    secret = (
        os.getenv("PLATFORM_EMAIL_VERIFICATION_SECRET")
        or os.getenv("PLATFORM_SECRET")
        or os.getenv("SECRET_KEY")
        or "dsa-local-email-verification"
    )
    return secret.encode("utf-8")


def _code_hash(email: str, code: str) -> str:
    payload = f"{_scope()}:{email}:{code}".encode("utf-8")
    return hmac.new(_secret_bytes(), payload, hashlib.sha256).hexdigest()


def reset_registration_verification_codes() -> None:
    with _lock:
        _records.clear()


class PlatformEmailVerificationService:
    """Generate and verify local registration codes."""

    def request_registration_code(self, email: str) -> RegistrationVerificationCode:
        normalized_email = _normalize_email(email)
        if not normalized_email or "@" not in normalized_email:
            raise ValueError("invalid email")

        code = f"{secrets.randbelow(1_000_000):06d}"
        ttl_seconds = _int_env("PLATFORM_EMAIL_VERIFICATION_TTL_SECONDS", 600)
        record = _VerificationRecord(
            code_hash=_code_hash(normalized_email, code),
            expires_at=time.time() + ttl_seconds,
        )
        with _lock:
            _records[_record_key(normalized_email)] = record
        return RegistrationVerificationCode(
            email=normalized_email,
            code=code,
            expires_in_seconds=ttl_seconds,
        )

    def verify_registration_code(self, email: str, code: str) -> bool:
        normalized_email = _normalize_email(email)
        normalized_code = (code or "").strip()
        if not normalized_email or not normalized_code:
            return False

        key = _record_key(normalized_email)
        now = time.time()
        with _lock:
            record = _records.get(key)
            if record is None:
                return False
            if record.expires_at < now:
                _records.pop(key, None)
                return False

            record.attempts += 1
            expected = _code_hash(normalized_email, normalized_code)
            if hmac.compare_digest(record.code_hash, expected):
                _records.pop(key, None)
                return True

            max_attempts = _int_env("PLATFORM_EMAIL_VERIFICATION_MAX_ATTEMPTS", 5)
            if record.attempts >= max_attempts:
                _records.pop(key, None)
            return False
