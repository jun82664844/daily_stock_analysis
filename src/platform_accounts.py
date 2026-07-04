# -*- coding: utf-8 -*-
"""Platform user, quota, and user-owned API key services."""

from __future__ import annotations

import base64
import copy
import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from src.storage import (
    DatabaseManager,
    PlatformUsageEvent,
    PlatformUser,
    PlatformUserApiKey,
)
from src.platform_feature_policy import get_bucket_weekly_limit, get_feature_policy


PLATFORM_SESSION_COOKIE = "dsa_user_session"
PLATFORM_PASSWORD_ITERATIONS = 120_000
PLATFORM_SESSION_MAX_AGE_HOURS_DEFAULT = 24 * 14
PLATFORM_ANALYSIS_PLANS: Dict[str, Optional[int]] = {
    "free": 5,
    "pro": 500,
    "premium": 500,
    "enterprise": None,
}


class PlatformAccountError(Exception):
    """Base class for platform account errors."""


class InvalidCredentials(PlatformAccountError):
    """Raised when login credentials are invalid."""


class QuotaExceeded(PlatformAccountError):
    """Raised when a user does not have enough analysis quota."""

    def __init__(self, *, remaining: int, requested: int, weekly_limit: Optional[int]) -> None:
        super().__init__("analysis quota exceeded")
        self.remaining = remaining
        self.requested = requested
        self.weekly_limit = weekly_limit


@dataclass(frozen=True)
class PlatformIdentity:
    """Authenticated platform principal."""

    user_id: Optional[int]
    email: str
    role: str
    plan: str
    is_admin: bool = False


def is_platform_user_auth_enabled() -> bool:
    return os.getenv("PLATFORM_USER_AUTH_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def _week_start(today: Optional[date] = None) -> date:
    current = today or datetime.now(timezone.utc).date()
    return current - timedelta(days=current.weekday())


def _mask_secret(secret: str) -> str:
    if len(secret) <= 8:
        return "*" * len(secret)
    return f"{secret[:4]}...{secret[-4:]}"


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(32)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PLATFORM_PASSWORD_ITERATIONS,
    )
    return ":".join(
        (
            str(PLATFORM_PASSWORD_ITERATIONS),
            base64.standard_b64encode(salt).decode("ascii"),
            base64.standard_b64encode(digest).decode("ascii"),
        )
    )


def _verify_password(password: str, stored: str) -> bool:
    try:
        iterations_text, salt_text, digest_text = stored.split(":", 2)
        iterations = int(iterations_text)
        salt = base64.standard_b64decode(salt_text)
        expected = base64.standard_b64decode(digest_text)
    except Exception:
        return False
    actual = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(actual, expected)


def _data_dir() -> Path:
    db_path = os.getenv("DATABASE_PATH", "./data/stock_analysis.db")
    return Path(db_path).resolve().parent


def _platform_secret_path() -> Path:
    return _data_dir() / ".platform_fernet_key"


def _platform_secret_bytes() -> bytes:
    key_path = _platform_secret_path()
    key_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        key = key_path.read_bytes()
        Fernet(key)
    except Exception:
        key = Fernet.generate_key()
        tmp_path = key_path.with_suffix(".tmp")
        tmp_path.write_bytes(key)
        try:
            tmp_path.chmod(0o600)
        except OSError:
            pass
        tmp_path.replace(key_path)
    return key


def _load_fernet() -> Fernet:
    return Fernet(_platform_secret_bytes())


def _record_audit(user_id: Optional[int], action: str, metadata: Dict[str, Any]) -> None:
    try:
        from src.platform_audit import PlatformAuditLogger

        PlatformAuditLogger().record(user_id=user_id, action=action, metadata=metadata)
    except Exception:
        pass


def _session_secret() -> bytes:
    return _platform_secret_bytes()


def create_platform_session(user: PlatformUser) -> str:
    nonce = secrets.token_urlsafe(24)
    ts = str(int(datetime.now(timezone.utc).timestamp()))
    payload = f"{int(user.id)}.{ts}.{nonce}"
    sig = hmac.new(_session_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def verify_platform_session(value: Optional[str]) -> Optional[PlatformIdentity]:
    if not value:
        return None
    parts = value.split(".")
    if len(parts) != 4:
        return None
    user_id_text, ts_text, nonce, sig = parts
    payload = f"{user_id_text}.{ts_text}.{nonce}"
    expected = hmac.new(_session_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        user_id = int(user_id_text)
        ts = int(ts_text)
    except ValueError:
        return None
    try:
        max_age_hours = int(
            os.getenv("PLATFORM_SESSION_MAX_AGE_HOURS", str(PLATFORM_SESSION_MAX_AGE_HOURS_DEFAULT))
        )
    except ValueError:
        max_age_hours = PLATFORM_SESSION_MAX_AGE_HOURS_DEFAULT
    if datetime.now(timezone.utc).timestamp() - ts > max_age_hours * 3600:
        return None
    user = PlatformAccountService().get_user(user_id)
    if user is None or user.status != "active":
        return None
    return PlatformIdentity(
        user_id=int(user.id),
        email=user.email,
        role=user.role,
        plan=user.plan,
        is_admin=user.role == "admin",
    )


def platform_identity_from_request(request: Any) -> Optional[PlatformIdentity]:
    cookie_value = request.cookies.get(PLATFORM_SESSION_COOKIE) if request is not None else None
    return verify_platform_session(cookie_value)


class PlatformAccountService:
    """Service for public platform users, quotas, and user-owned API keys."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None) -> None:
        self.db = db_manager or DatabaseManager.get_instance()

    def create_user(
        self,
        email: str,
        password: str,
        *,
        plan: str = "free",
        role: str = "user",
    ) -> PlatformUser:
        normalized_email = _normalize_email(email)
        if not normalized_email or "@" not in normalized_email:
            raise ValueError("invalid email")
        if len(password or "") < 8:
            raise ValueError("password must be at least 8 characters")
        if plan not in PLATFORM_ANALYSIS_PLANS:
            raise ValueError(f"unsupported plan: {plan}")

        with self.db.session_scope() as session:
            user = PlatformUser(
                email=normalized_email,
                password_hash=_hash_password(password),
                role=role,
                plan=plan,
                status="active",
                weekly_quota=PLATFORM_ANALYSIS_PLANS[plan],
                created_at=_utc_now(),
                updated_at=_utc_now(),
            )
            session.add(user)
            session.flush()
            session.refresh(user)
            session.expunge(user)
            return user

    def verify_login(self, email: str, password: str) -> PlatformUser:
        user = self.get_user_by_email(email)
        if user is None or user.status != "active" or not _verify_password(password or "", user.password_hash):
            raise InvalidCredentials("invalid email or password")
        return user

    def get_user(self, user_id: int) -> Optional[PlatformUser]:
        with self.db.get_session() as session:
            user = session.execute(
                select(PlatformUser).where(PlatformUser.id == int(user_id))
            ).scalars().first()
            if user is not None:
                session.expunge(user)
            return user

    def get_user_by_email(self, email: str) -> Optional[PlatformUser]:
        normalized_email = _normalize_email(email)
        with self.db.get_session() as session:
            user = session.execute(
                select(PlatformUser).where(PlatformUser.email == normalized_email)
            ).scalars().first()
            if user is not None:
                session.expunge(user)
            return user

    def list_users(self, *, limit: int = 100) -> List[PlatformUser]:
        with self.db.get_session() as session:
            users = session.execute(
                select(PlatformUser).order_by(PlatformUser.created_at.desc()).limit(max(1, min(limit, 500)))
            ).scalars().all()
            for user in users:
                session.expunge(user)
            return list(users)

    def set_user_plan(self, user_id: int, plan: str) -> PlatformUser:
        if plan not in PLATFORM_ANALYSIS_PLANS:
            raise ValueError(f"unsupported plan: {plan}")
        with self.db.session_scope() as session:
            user = session.execute(
                select(PlatformUser).where(PlatformUser.id == int(user_id))
            ).scalars().first()
            if user is None:
                raise ValueError("user not found")
            user.plan = plan
            user.weekly_quota = PLATFORM_ANALYSIS_PLANS[plan]
            user.updated_at = _utc_now()
            session.flush()
            session.refresh(user)
            session.expunge(user)
            return user

    def get_quota_status(self, user_id: int, *, today: Optional[date] = None) -> Dict[str, Any]:
        user = self.get_user(user_id)
        if user is None:
            raise ValueError("user not found")
        period_start = _week_start(today)
        used = self._used_analysis_quota(user.id, period_start)
        weekly_limit = user.weekly_quota
        remaining = None if weekly_limit is None else max(0, int(weekly_limit) - used)
        return {
            "user_id": user.id,
            "plan": user.plan,
            "weekly_limit": weekly_limit,
            "used": used,
            "remaining": remaining,
            "period_start": period_start.isoformat(),
        }

    def get_feature_quota_status(
        self,
        user_id: int,
        quota_bucket: str,
        *,
        today: Optional[date] = None,
    ) -> Dict[str, Any]:
        user = self.get_user(user_id)
        if user is None:
            raise ValueError("user not found")
        bucket = (quota_bucket or "analysis").strip().lower()
        period_start = _week_start(today)
        weekly_limit = get_bucket_weekly_limit(bucket, plan=user.plan)
        used = self._used_feature_quota(user.id, bucket, period_start)
        remaining = None if weekly_limit is None else max(0, int(weekly_limit) - used)
        return {
            "user_id": user.id,
            "plan": user.plan,
            "quota_bucket": bucket,
            "weekly_limit": weekly_limit,
            "used": used,
            "remaining": remaining,
            "period_start": period_start.isoformat(),
        }

    def reserve_feature_quota(
        self,
        user_id: int,
        feature: str,
        *,
        api_key_mode: str = "platform",
        quantity: int = 1,
        reference_id: str | None = None,
        today: Optional[date] = None,
    ) -> Dict[str, Any]:
        user = self.get_user(user_id)
        if user is None:
            raise ValueError("platform user not found")
        policy = get_feature_policy(feature, plan=user.plan, api_key_mode=api_key_mode)
        multiplier = max(1, int(quantity or 1))
        units = max(0, multiplier * int(policy.cost_units))
        abuse_units = max(0, multiplier * int(policy.server_abuse_units))
        reserved_units = max(units, abuse_units)
        if reserved_units <= 0:
            return self.get_feature_quota_status(user_id, policy.quota_bucket, today=today)
        status = self._reserve_quota_units(
            user_id=user.id,
            plan=user.plan,
            quota_bucket=policy.quota_bucket,
            feature=policy.feature,
            units=reserved_units,
            weekly_limit=policy.weekly_limit,
            reference_id=reference_id,
            today=today,
        )
        _record_audit(
            int(user.id),
            "quota_reserved",
            {
                "feature": policy.feature,
                "quota_bucket": policy.quota_bucket,
                "units": reserved_units,
                "reference_id": reference_id,
            },
        )
        return status

    def reserve_analysis_quota(
        self,
        user_id: int,
        quantity: int = 1,
        *,
        reason: str = "analysis",
        reference_id: Optional[str] = None,
        today: Optional[date] = None,
    ) -> Dict[str, Any]:
        requested = max(1, int(quantity or 1))
        period_start = _week_start(today)
        with self.db.session_scope() as session:
            user = session.execute(
                select(PlatformUser).where(PlatformUser.id == int(user_id))
            ).scalars().first()
            if user is None or user.status != "active":
                raise ValueError("user not found or inactive")
            used = int(
                session.execute(
                    select(func.coalesce(func.sum(PlatformUsageEvent.quantity), 0)).where(
                        and_(
                            PlatformUsageEvent.user_id == user.id,
                            PlatformUsageEvent.event_type == "analysis",
                            PlatformUsageEvent.period_start == period_start,
                        )
                    )
                ).scalar_one()
                or 0
            )
            if user.weekly_quota is not None:
                remaining = max(0, int(user.weekly_quota) - used)
                if requested > remaining:
                    raise QuotaExceeded(
                        remaining=remaining,
                        requested=requested,
                        weekly_limit=int(user.weekly_quota),
                    )

            session.add(
                PlatformUsageEvent(
                    user_id=user.id,
                    event_type="analysis",
                    feature="ai_quick",
                    quota_bucket="ai_quick",
                    quantity=requested,
                    units=requested,
                    reason=reason,
                    reference_id=reference_id,
                    period_start=period_start,
                    created_at=_utc_now(),
                )
            )
            used_after = used + requested
            remaining_after = None if user.weekly_quota is None else max(0, int(user.weekly_quota) - used_after)
            return {
                "user_id": user.id,
                "plan": user.plan,
                "weekly_limit": user.weekly_quota,
                "used": used_after,
                "remaining": remaining_after,
                "period_start": period_start.isoformat(),
            }

    def _used_analysis_quota(self, user_id: int, period_start: date) -> int:
        with self.db.get_session() as session:
            return int(
                session.execute(
                    select(func.coalesce(func.sum(PlatformUsageEvent.quantity), 0)).where(
                        and_(
                            PlatformUsageEvent.user_id == int(user_id),
                            PlatformUsageEvent.event_type == "analysis",
                            PlatformUsageEvent.period_start == period_start,
                        )
                    )
                ).scalar_one()
                or 0
            )

    def _used_feature_quota(self, user_id: int, quota_bucket: str, period_start: date) -> int:
        with self.db.get_session() as session:
            return self._used_feature_quota_in_session(session, user_id, quota_bucket, period_start)

    def _used_feature_quota_in_session(
        self,
        session: Any,
        user_id: int,
        quota_bucket: str,
        period_start: date,
    ) -> int:
        bucket = (quota_bucket or "analysis").strip().lower()
        if bucket == "analysis":
            return int(
                session.execute(
                    select(func.coalesce(func.sum(PlatformUsageEvent.quantity), 0)).where(
                        and_(
                            PlatformUsageEvent.user_id == int(user_id),
                            PlatformUsageEvent.event_type == "analysis",
                            PlatformUsageEvent.period_start == period_start,
                        )
                    )
                ).scalar_one()
                or 0
            )
        if bucket == "ai_quick":
            return int(
                session.execute(
                    select(func.coalesce(func.sum(PlatformUsageEvent.units), 0)).where(
                        and_(
                            PlatformUsageEvent.user_id == int(user_id),
                            PlatformUsageEvent.period_start == period_start,
                            or_(
                                PlatformUsageEvent.quota_bucket == "ai_quick",
                                PlatformUsageEvent.quota_bucket == "analysis",
                            ),
                        )
                    )
                ).scalar_one()
                or 0
            )
        return int(
            session.execute(
                select(func.coalesce(func.sum(PlatformUsageEvent.units), 0)).where(
                    and_(
                        PlatformUsageEvent.user_id == int(user_id),
                        PlatformUsageEvent.quota_bucket == bucket,
                        PlatformUsageEvent.period_start == period_start,
                    )
                )
            ).scalar_one()
            or 0
        )

    def _reserve_quota_units(
        self,
        *,
        user_id: int,
        plan: str,
        quota_bucket: str,
        feature: str,
        units: int,
        weekly_limit: Optional[int],
        reference_id: Optional[str],
        today: Optional[date],
    ) -> Dict[str, Any]:
        requested = max(1, int(units or 1))
        bucket = (quota_bucket or "analysis").strip().lower()
        period_start = _week_start(today)
        with self.db.session_scope() as session:
            user = session.execute(
                select(PlatformUser).where(PlatformUser.id == int(user_id))
            ).scalars().first()
            if user is None or user.status != "active":
                raise ValueError("user not found or inactive")

            used = self._used_feature_quota_in_session(session, user.id, bucket, period_start)
            if weekly_limit is not None:
                remaining = max(0, int(weekly_limit) - used)
                if requested > remaining:
                    raise QuotaExceeded(
                        remaining=remaining,
                        requested=requested,
                        weekly_limit=int(weekly_limit),
                    )

            session.add(
                PlatformUsageEvent(
                    user_id=user.id,
                    event_type="analysis" if feature in {"analysis", "ai_quick", "ai_deep"} else feature,
                    feature=feature,
                    quota_bucket=bucket,
                    quantity=requested,
                    units=requested,
                    reason=feature,
                    reference_id=reference_id,
                    period_start=period_start,
                    created_at=_utc_now(),
                )
            )
            used_after = used + requested
            remaining_after = None if weekly_limit is None else max(0, int(weekly_limit) - used_after)
            return {
                "user_id": user.id,
                "plan": plan,
                "quota_bucket": bucket,
                "weekly_limit": weekly_limit,
                "used": used_after,
                "remaining": remaining_after,
                "period_start": period_start.isoformat(),
            }

    def store_api_key(
        self,
        user_id: int,
        *,
        provider: str,
        api_key: str,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        normalized_provider = (provider or "").strip().lower()
        secret = (api_key or "").strip()
        normalized_model = (model or "").strip() or None
        if normalized_provider not in {"deepseek", "openai", "anthropic", "gemini"}:
            raise ValueError("unsupported provider")
        if len(secret) < 8:
            raise ValueError("api key is too short")

        encrypted = _load_fernet().encrypt(secret.encode("utf-8")).decode("ascii")
        masked = _mask_secret(secret)
        now = _utc_now()
        with self.db.session_scope() as session:
            stmt = sqlite_insert(PlatformUserApiKey).values(
                user_id=int(user_id),
                provider=normalized_provider,
                model=normalized_model,
                encrypted_secret=encrypted,
                masked_key=masked,
                enabled=True,
                created_at=now,
                updated_at=now,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["user_id", "provider"],
                set_={
                    "encrypted_secret": encrypted,
                    "masked_key": masked,
                    "model": normalized_model,
                    "enabled": True,
                    "updated_at": now,
                },
            )
            session.execute(stmt)
        return {
            "provider": normalized_provider,
            "model": normalized_model,
            "masked_key": masked,
            "enabled": True,
        }

    def list_api_keys(self, user_id: int) -> List[Dict[str, Any]]:
        with self.db.get_session() as session:
            rows = session.execute(
                select(PlatformUserApiKey)
                .where(PlatformUserApiKey.user_id == int(user_id))
                .order_by(PlatformUserApiKey.provider.asc())
            ).scalars().all()
            return [
                {
                    "id": row.id,
                    "provider": row.provider,
                    "model": row.model,
                    "masked_key": row.masked_key,
                    "enabled": bool(row.enabled),
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                }
                for row in rows
            ]

    def get_api_key_secret(self, user_id: int, provider: str) -> Optional[str]:
        normalized_provider = (provider or "").strip().lower()
        with self.db.get_session() as session:
            row = session.execute(
                select(PlatformUserApiKey).where(
                    and_(
                        PlatformUserApiKey.user_id == int(user_id),
                        PlatformUserApiKey.provider == normalized_provider,
                        PlatformUserApiKey.enabled.is_(True),
                    )
                )
            ).scalars().first()
            if row is None:
                return None
            encrypted = row.encrypted_secret
        try:
            return _load_fernet().decrypt(encrypted.encode("ascii")).decode("utf-8")
        except (InvalidToken, UnicodeDecodeError, ValueError):
            return None

    def apply_user_llm_config(self, config: Any, user_id: Optional[int], *, mode: str = "platform") -> Any:
        if (mode or "platform").lower() != "user" or not user_id:
            return config
        for provider in ("deepseek", "openai", "anthropic", "gemini"):
            secret = self.get_api_key_secret(user_id, provider)
            if secret:
                scoped = copy.copy(config)
                self._apply_provider_secret(scoped, provider, secret)
                return scoped
        return config

    @staticmethod
    def _apply_provider_secret(config: Any, provider: str, secret: str) -> None:
        if provider == "deepseek":
            setattr(config, "deepseek_api_keys", [secret])
            setattr(config, "deepseek_api_key", secret)
        elif provider == "openai":
            setattr(config, "openai_api_keys", [secret])
            setattr(config, "openai_api_key", secret)
        elif provider == "anthropic":
            setattr(config, "anthropic_api_keys", [secret])
            setattr(config, "anthropic_api_key", secret)
        elif provider == "gemini":
            setattr(config, "gemini_api_keys", [secret])
            setattr(config, "gemini_api_key", secret)


def get_platform_account_service() -> PlatformAccountService:
    return PlatformAccountService()
