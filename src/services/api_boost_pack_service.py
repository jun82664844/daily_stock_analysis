# -*- coding: utf-8 -*-
"""Expiring member API grants and the fixed V112 boost-pack product."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from sqlalchemy import case, select
from sqlalchemy.orm import Session

from src.platform_accounts import membership_month_quota, normalize_membership_plan
from src.storage import (
    DatabaseManager,
    PlatformBillingSubscription,
    PlatformQuotaGrant,
    PlatformQuotaReservation,
    utc_naive_now,
)


class MemberApiQuotaExceeded(ValueError):
    def __init__(self, quota_type: str, requested: int, remaining: int) -> None:
        self.quota_type = quota_type
        self.requested = requested
        self.remaining = remaining
        super().__init__("member_api_quota_exhausted")


class BoostPackNotAvailable(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class BoostPackProduct:
    code: str = "api_boost_168_28"
    price_hkd: int = 28
    flash_units: int = 168
    pro_units: int = 28


class ApiBoostPackService:
    PRODUCT = BoostPackProduct()
    MIN_REMAINING_MINUTES = 60

    def __init__(self, db_manager: Optional[DatabaseManager] = None) -> None:
        self.db = db_manager or DatabaseManager.get_instance()

    def assert_can_purchase(
        self,
        *,
        user_id: int,
        now: Optional[datetime] = None,
    ) -> PlatformBillingSubscription:
        effective_now = now or utc_naive_now()
        with self.db.get_session() as session:
            subscription = session.execute(
                select(PlatformBillingSubscription).where(
                    PlatformBillingSubscription.user_id == int(user_id)
                )
            ).scalars().first()
            if (
                subscription is None
                or subscription.status != "active"
                or normalize_membership_plan(subscription.plan) not in {"pro", "max"}
            ):
                raise BoostPackNotAvailable("boost_pack_not_available")
            if subscription.current_period_end is None or subscription.expires_at is None:
                raise BoostPackNotAvailable("membership_period_unknown")
            expires_at = min(subscription.current_period_end, subscription.expires_at)
            if expires_at <= effective_now + timedelta(minutes=self.MIN_REMAINING_MINUTES):
                raise BoostPackNotAvailable("renew_membership_first")
            session.expunge(subscription)
            return subscription

    def grant_from_payment_event(
        self,
        session: Session,
        *,
        user_id: int,
        provider_event_id: str,
        starts_at: datetime,
        expires_at: datetime,
    ) -> PlatformQuotaGrant:
        existing = session.execute(
            select(PlatformQuotaGrant).where(
                PlatformQuotaGrant.source_reference == provider_event_id
            )
        ).scalars().first()
        if existing is not None:
            return existing
        grant = PlatformQuotaGrant(
            user_id=int(user_id),
            source_type="boost_pack",
            source_reference=provider_event_id,
            flash_total=self.PRODUCT.flash_units,
            flash_used=0,
            pro_total=self.PRODUCT.pro_units,
            pro_used=0,
            starts_at=starts_at,
            expires_at=expires_at,
            status="active",
            created_at=starts_at,
        )
        session.add(grant)
        session.flush()
        return grant

    def grant_membership_period(
        self,
        *,
        user_id: int,
        plan: str,
        period_reference: str,
        starts_at: datetime,
        expires_at: datetime,
        session: Optional[Session] = None,
    ) -> PlatformQuotaGrant:
        allowance = membership_month_quota(plan)
        reference = f"membership:{(period_reference or '').strip()}"
        if reference == "membership:":
            raise ValueError("period_reference_required")
        if expires_at <= starts_at:
            raise ValueError("invalid_membership_period")

        def _write(session: Session) -> PlatformQuotaGrant:
            existing = session.execute(
                select(PlatformQuotaGrant).where(
                    PlatformQuotaGrant.source_reference == reference
                )
            ).scalars().first()
            if existing is not None:
                if int(existing.user_id) != int(user_id):
                    raise ValueError("grant_owner_mismatch")
                return existing
            grant = PlatformQuotaGrant(
                user_id=int(user_id),
                source_type="membership",
                source_reference=reference,
                flash_total=int(allowance["flash"]),
                flash_used=0,
                pro_total=int(allowance["pro"]),
                pro_used=0,
                starts_at=starts_at,
                expires_at=expires_at,
                status="active",
                created_at=starts_at,
            )
            session.add(grant)
            session.flush()
            return grant

        if session is not None:
            return _write(session)
        grant_id = self.db._run_write_transaction(
            "platform_v112_membership_grant",
            lambda write_session: int(_write(write_session).id),
        )
        with self.db.get_session() as read_session:
            grant = read_session.get(PlatformQuotaGrant, grant_id)
            if grant is None:  # pragma: no cover - defensive database boundary
                raise RuntimeError("membership_grant_not_found")
            read_session.expunge(grant)
            return grant

    def purchase_summary(self, user_id: int, *, now: Optional[datetime] = None) -> Dict[str, Any]:
        effective_now = now or utc_naive_now()
        can_purchase = True
        reason = None
        expires_at = None
        try:
            subscription = self.assert_can_purchase(user_id=user_id, now=effective_now)
            expires_at = min(subscription.current_period_end, subscription.expires_at)
        except BoostPackNotAvailable as exc:
            can_purchase = False
            reason = exc.code
        return {
            "product_code": self.PRODUCT.code,
            "price_hkd": self.PRODUCT.price_hkd,
            "flash": self.PRODUCT.flash_units,
            "pro": self.PRODUCT.pro_units,
            "balance": self.balance(user_id, now=effective_now),
            "expires_at": expires_at.isoformat() if expires_at else None,
            "can_purchase": can_purchase,
            "unavailable_reason": reason,
        }

    @staticmethod
    def _normalize_quota_type(quota_type: str) -> str:
        normalized = (quota_type or "").strip().lower()
        if normalized not in {"flash", "pro"}:
            raise ValueError("unsupported_quota_type")
        return normalized

    @staticmethod
    def _reservation_payload(row: PlatformQuotaReservation) -> Dict[str, Any]:
        try:
            allocations = json.loads(row.allocations_json or "[]")
        except (TypeError, ValueError):
            allocations = []
        return {
            "reference_id": row.reference_id,
            "user_id": int(row.user_id),
            "quota_type": row.quota_type,
            "units": int(row.units),
            "allocations": allocations,
            "status": row.status,
        }

    def reserve(
        self,
        user_id: int,
        quota_type: str,
        units: int,
        reference_id: str,
        *,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        normalized_type = self._normalize_quota_type(quota_type)
        requested = max(1, int(units or 1))
        reference = (reference_id or "").strip()
        if not reference:
            raise ValueError("reference_id_required")
        effective_now = now or utc_naive_now()

        def _write(session: Session) -> Dict[str, Any]:
            existing = session.execute(
                select(PlatformQuotaReservation).where(
                    PlatformQuotaReservation.reference_id == reference
                )
            ).scalars().first()
            if existing is not None:
                if int(existing.user_id) != int(user_id):
                    raise ValueError("reservation_owner_mismatch")
                return self._reservation_payload(existing)

            source_priority = case(
                (PlatformQuotaGrant.source_type == "membership", 0),
                (PlatformQuotaGrant.source_type == "boost_pack", 1),
                else_=2,
            )
            grants = session.execute(
                select(PlatformQuotaGrant)
                .where(
                    PlatformQuotaGrant.user_id == int(user_id),
                    PlatformQuotaGrant.status == "active",
                    PlatformQuotaGrant.starts_at <= effective_now,
                    PlatformQuotaGrant.expires_at > effective_now,
                )
                .order_by(source_priority, PlatformQuotaGrant.expires_at, PlatformQuotaGrant.id)
            ).scalars().all()

            allocations = []
            needed = requested
            total_remaining = 0
            for grant in grants:
                total = int(getattr(grant, f"{normalized_type}_total") or 0)
                used = int(getattr(grant, f"{normalized_type}_used") or 0)
                available = max(0, total - used)
                total_remaining += available
                if needed <= 0 or available <= 0:
                    continue
                take = min(available, needed)
                allocations.append({"grant_id": int(grant.id), "units": take})
                needed -= take

            if needed > 0:
                raise MemberApiQuotaExceeded(normalized_type, requested, total_remaining)

            grant_by_id = {int(grant.id): grant for grant in grants}
            for allocation in allocations:
                grant = grant_by_id[allocation["grant_id"]]
                used_field = f"{normalized_type}_used"
                setattr(grant, used_field, int(getattr(grant, used_field) or 0) + int(allocation["units"]))

            reservation = PlatformQuotaReservation(
                user_id=int(user_id),
                reference_id=reference,
                quota_type=normalized_type,
                units=requested,
                allocations_json=json.dumps(allocations, separators=(",", ":")),
                status="reserved",
                created_at=effective_now,
                updated_at=effective_now,
            )
            session.add(reservation)
            session.flush()
            return self._reservation_payload(reservation)

        return self.db._run_write_transaction("platform_v112_quota_reserve", _write)

    def release(self, reference_id: str) -> Dict[str, Any]:
        reference = (reference_id or "").strip()

        def _write(session: Session) -> Dict[str, Any]:
            reservation = session.execute(
                select(PlatformQuotaReservation).where(
                    PlatformQuotaReservation.reference_id == reference
                )
            ).scalars().first()
            if reservation is None:
                return {"reference_id": reference, "released": False, "status": "not_found"}
            if reservation.status != "reserved":
                return {"reference_id": reference, "released": False, "status": reservation.status}
            allocations = json.loads(reservation.allocations_json or "[]")
            for allocation in allocations:
                grant = session.get(PlatformQuotaGrant, int(allocation["grant_id"]))
                if grant is None:
                    continue
                field = f"{reservation.quota_type}_used"
                setattr(grant, field, max(0, int(getattr(grant, field) or 0) - int(allocation["units"])))
            reservation.status = "released"
            reservation.updated_at = utc_naive_now()
            return {"reference_id": reference, "released": True, "status": "released"}

        return self.db._run_write_transaction("platform_v112_quota_release", _write)

    def consume(self, reference_id: str) -> Dict[str, Any]:
        reference = (reference_id or "").strip()

        def _write(session: Session) -> Dict[str, Any]:
            reservation = session.execute(
                select(PlatformQuotaReservation).where(
                    PlatformQuotaReservation.reference_id == reference
                )
            ).scalars().first()
            if reservation is None:
                return {"reference_id": reference, "consumed": False, "status": "not_found"}
            if reservation.status == "reserved":
                reservation.status = "consumed"
                reservation.updated_at = utc_naive_now()
                return {"reference_id": reference, "consumed": True, "status": "consumed"}
            return {"reference_id": reference, "consumed": False, "status": reservation.status}

        return self.db._run_write_transaction("platform_v112_quota_consume", _write)

    def balance(self, user_id: int, *, now: Optional[datetime] = None) -> Dict[str, int]:
        effective_now = now or utc_naive_now()
        with self.db.get_session() as session:
            grants = session.execute(
                select(PlatformQuotaGrant).where(
                    PlatformQuotaGrant.user_id == int(user_id),
                    PlatformQuotaGrant.status == "active",
                    PlatformQuotaGrant.starts_at <= effective_now,
                    PlatformQuotaGrant.expires_at > effective_now,
                )
            ).scalars().all()
            return {
                "flash": sum(max(0, int(row.flash_total or 0) - int(row.flash_used or 0)) for row in grants),
                "pro": sum(max(0, int(row.pro_total or 0) - int(row.pro_used or 0)) for row in grants),
            }
