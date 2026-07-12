# -*- coding: utf-8 -*-
"""Local sandbox billing lifecycle and idempotent reconciliation."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from src.platform_accounts import PLATFORM_ANALYSIS_PLANS
from src.storage import (
    DatabaseManager,
    PlatformBillingCheckoutSession,
    PlatformBillingEvent,
    PlatformBillingSubscription,
    PlatformUser,
    utc_naive_now,
)


CHECKOUT_EVENT_STATUSES = {
    "checkout.completed": "completed",
    "checkout.cancelled": "cancelled",
    "checkout.expired": "expired",
    "payment.failed": "failed",
}


def _iso(value: Any) -> Optional[str]:
    return value.isoformat() if value is not None else None


def _parse_datetime(value: Any) -> Optional[datetime]:
    if value in {None, ""}:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise ValueError("invalid_subscription_period") from exc
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _metadata_json(value: Dict[str, Any]) -> str:
    safe = {
        key: item
        for key, item in (value or {}).items()
        if str(key).lower() not in {"signature", "secret", "api_key", "apikey", "token"}
    }
    return json.dumps(safe, ensure_ascii=False, default=str)


class BillingLifecycleService:
    """Persists and reconciles local sandbox billing events."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None) -> None:
        self.db = db_manager or DatabaseManager.get_instance()

    def record_checkout_created(
        self,
        *,
        user_id: int,
        provider_session_id: str,
        checkout_url: str,
        plan: str,
        provider: str = "sandbox",
        product_type: str = "subscription",
        product_code: Optional[str] = None,
    ) -> None:
        normalized_product_type = (product_type or "subscription").strip().lower()
        if normalized_product_type not in {"subscription", "add_on"}:
            raise ValueError("unsupported_product_type")
        normalized_plan = self._normalize_plan(plan, allow_free=normalized_product_type == "add_on")
        provider_event_id = f"evt_checkout_created_{provider_session_id}"
        now = utc_naive_now()

        def _write(session: Session) -> None:
            self._ensure_subscription(session, user_id=int(user_id), provider=provider)
            session.add(
                PlatformBillingCheckoutSession(
                    user_id=int(user_id),
                    provider=provider,
                    provider_session_id=provider_session_id,
                    checkout_url=checkout_url,
                    plan=normalized_plan,
                    product_type=normalized_product_type,
                    product_code=product_code,
                    status="created",
                    metadata_json=_metadata_json(
                        {"mode": "local_sandbox", "product_type": normalized_product_type, "product_code": product_code}
                    ),
                    created_at=now,
                    updated_at=now,
                )
            )
            if self._find_event(session, provider_event_id) is None:
                session.add(
                    PlatformBillingEvent(
                        user_id=int(user_id),
                        provider=provider,
                        provider_event_id=provider_event_id,
                        provider_session_id=provider_session_id,
                        event_type="checkout.created",
                        plan=normalized_plan,
                        processing_status="processed",
                        metadata_json=_metadata_json(
                            {"source": "checkout", "product_type": normalized_product_type, "product_code": product_code}
                        ),
                        created_at=now,
                        updated_at=now,
                    )
                )

        self.db._run_write_transaction("platform_billing_checkout_created", _write)

    def process_verified_sandbox_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        event_type = str(payload.get("event") or "").strip().lower()
        provider_event_id = self._provider_event_id(payload)
        if not provider_event_id:
            raise ValueError("missing_provider_event_id")
        now = utc_naive_now()

        def _write(session: Session) -> Dict[str, Any]:
            existing = self._find_event(session, provider_event_id)
            if existing is not None:
                return self._result_from_existing_event(session, existing)

            if event_type in CHECKOUT_EVENT_STATUSES:
                result = self._process_checkout_event(
                    session=session,
                    payload=payload,
                    provider_event_id=provider_event_id,
                    event_type=event_type,
                    now=now,
                )
            elif event_type == "subscription.updated":
                result = self._process_subscription_updated(
                    session=session,
                    payload=payload,
                    provider_event_id=provider_event_id,
                    event_type=event_type,
                    now=now,
                )
            else:
                raise ValueError("unsupported_event")
            return result

        return self.db._run_write_transaction("platform_billing_webhook", _write)

    def get_user_billing_summary(self, user_id: int, *, billing_enabled: bool, provider: str) -> Dict[str, Any]:
        with self.db.get_session() as session:
            subscription = session.execute(
                select(PlatformBillingSubscription).where(PlatformBillingSubscription.user_id == int(user_id))
            ).scalars().first()
            sessions = session.execute(
                select(PlatformBillingCheckoutSession)
                .where(PlatformBillingCheckoutSession.user_id == int(user_id))
                .order_by(desc(PlatformBillingCheckoutSession.created_at), desc(PlatformBillingCheckoutSession.id))
                .limit(20)
            ).scalars().all()
            events = session.execute(
                select(PlatformBillingEvent)
                .where(PlatformBillingEvent.user_id == int(user_id))
                .order_by(desc(PlatformBillingEvent.created_at), desc(PlatformBillingEvent.id))
                .limit(20)
            ).scalars().all()
            return {
                "billing_enabled": bool(billing_enabled),
                "provider": provider,
                "mode": "local_sandbox" if bool(billing_enabled) and provider == "sandbox" else "disabled",
                "copy": "Local sandbox billing only; not real payment processing.",
                "subscription": self._subscription_payload(subscription, user_id=int(user_id)),
                "checkout_sessions": [self._checkout_payload(row) for row in sessions],
                "recent_events": [self._event_payload(row) for row in events],
            }

    def list_admin_billing_events(self, *, limit: int = 100) -> Dict[str, Any]:
        capped_limit = max(1, min(int(limit or 100), 500))
        with self.db.get_session() as session:
            events = session.execute(
                select(PlatformBillingEvent)
                .order_by(desc(PlatformBillingEvent.created_at), desc(PlatformBillingEvent.id))
                .limit(capped_limit)
            ).scalars().all()
            users = {
                int(user.id): user.email
                for user in session.execute(select(PlatformUser)).scalars().all()
            }
            payload = []
            for event in events:
                item = self._event_payload(event)
                item["email"] = users.get(int(event.user_id)) if event.user_id is not None else None
                payload.append(item)
            return {"events": payload}

    def _process_checkout_event(
        self,
        *,
        session: Session,
        payload: Dict[str, Any],
        provider_event_id: str,
        event_type: str,
        now: Any,
    ) -> Dict[str, Any]:
        provider_session_id = str(payload.get("provider_session_id") or "").strip()
        checkout = session.execute(
            select(PlatformBillingCheckoutSession).where(
                PlatformBillingCheckoutSession.provider_session_id == provider_session_id
            )
        ).scalars().first()
        if checkout is None:
            raise ValueError("checkout_session_not_found")

        checkout_status = CHECKOUT_EVENT_STATUSES[event_type]
        checkout.status = checkout_status
        checkout.updated_at = now

        target_plan = checkout.plan
        subscription = self._ensure_subscription(session, user_id=int(checkout.user_id), provider=checkout.provider)
        subscription_status = subscription.status
        grant = None
        if checkout.product_type == "add_on":
            if event_type == "checkout.completed":
                if subscription.current_period_end is None or subscription.expires_at is None:
                    raise ValueError("membership_period_unknown")
                from src.services.api_boost_pack_service import ApiBoostPackService

                grant = ApiBoostPackService(self.db).grant_from_payment_event(
                    session,
                    user_id=int(checkout.user_id),
                    provider_event_id=provider_event_id,
                    starts_at=now,
                    expires_at=min(subscription.current_period_end, subscription.expires_at),
                )
        else:
            if event_type == "checkout.completed":
                self._set_user_plan(session, int(checkout.user_id), target_plan)
                subscription.plan = target_plan
                subscription.status = "active"
                subscription_status = "active"
                subscription.current_period_start = subscription.current_period_start or now
                subscription.current_period_end = subscription.current_period_end or (now + timedelta(days=30))
                subscription.expires_at = subscription.expires_at or subscription.current_period_end
                if target_plan in {"pro", "premium", "max"}:
                    from src.services.api_boost_pack_service import ApiBoostPackService

                    ApiBoostPackService(self.db).grant_membership_period(
                        user_id=int(checkout.user_id),
                        plan=target_plan,
                        period_reference=f"{provider_session_id}:{subscription.current_period_start.isoformat()}",
                        starts_at=subscription.current_period_start,
                        expires_at=min(subscription.current_period_end, subscription.expires_at),
                        session=session,
                    )
            elif event_type == "payment.failed" and subscription.status == "active":
                subscription.status = "past_due"
                subscription_status = "past_due"
            subscription.updated_at = now

        billing_event = PlatformBillingEvent(
            user_id=int(checkout.user_id),
            provider=checkout.provider,
            provider_event_id=provider_event_id,
            provider_session_id=provider_session_id,
            event_type=event_type,
            plan=target_plan,
            processing_status="processed",
            metadata_json=_metadata_json(
                {
                    "checkout_status": checkout_status,
                    "subscription_status": subscription_status,
                    "product_type": checkout.product_type,
                    "product_code": checkout.product_code,
                    "quota_grant_id": int(grant.id) if grant is not None else None,
                }
            ),
            created_at=now,
            updated_at=now,
        )
        session.add(billing_event)
        session.flush()
        return {
            "status": "processed",
            "idempotent": False,
            "provider": checkout.provider,
            "provider_event_id": provider_event_id,
            "provider_session_id": provider_session_id,
            "event": event_type,
            "plan": target_plan,
            "user_id": int(checkout.user_id),
            "checkout_status": checkout_status,
            "subscription_status": subscription_status,
            "product_type": checkout.product_type,
            "product_code": checkout.product_code,
            "quota_grant_id": int(grant.id) if grant is not None else None,
        }

    def _process_subscription_updated(
        self,
        *,
        session: Session,
        payload: Dict[str, Any],
        provider_event_id: str,
        event_type: str,
        now: Any,
    ) -> Dict[str, Any]:
        try:
            user_id = int(payload.get("user_id"))
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid_user_id") from exc
        requested_status = str(payload.get("subscription_status") or payload.get("status") or "active").strip().lower()
        requested_plan = self._normalize_plan(str(payload.get("plan") or "free"), allow_free=True)
        target_plan = "free" if requested_status in {"cancelled", "canceled", "inactive"} else requested_plan
        self._set_user_plan(session, user_id, target_plan)
        subscription = self._ensure_subscription(session, user_id=user_id, provider="sandbox")
        subscription.plan = target_plan
        subscription.status = "cancelled" if requested_status in {"cancelled", "canceled", "inactive"} else requested_status
        subscription.provider_subscription_id = str(payload.get("provider_subscription_id") or "") or None
        subscription.current_period_start = (
            _parse_datetime(payload.get("current_period_start")) or subscription.current_period_start
        )
        subscription.current_period_end = (
            _parse_datetime(payload.get("current_period_end")) or subscription.current_period_end
        )
        subscription.expires_at = _parse_datetime(payload.get("expires_at")) or subscription.expires_at
        subscription.updated_at = now

        if (
            subscription.status == "active"
            and target_plan in {"pro", "premium", "max"}
            and subscription.current_period_start is not None
            and subscription.current_period_end is not None
        ):
            from src.services.api_boost_pack_service import ApiBoostPackService

            period_reference = subscription.provider_subscription_id or f"user-{user_id}"
            ApiBoostPackService(self.db).grant_membership_period(
                user_id=user_id,
                plan=target_plan,
                period_reference=f"{period_reference}:{subscription.current_period_start.isoformat()}",
                starts_at=subscription.current_period_start,
                expires_at=min(
                    subscription.current_period_end,
                    subscription.expires_at or subscription.current_period_end,
                ),
                session=session,
            )

        billing_event = PlatformBillingEvent(
            user_id=user_id,
            provider="sandbox",
            provider_event_id=provider_event_id,
            provider_session_id=str(payload.get("provider_session_id") or "") or None,
            event_type=event_type,
            plan=target_plan,
            processing_status="processed",
            metadata_json=_metadata_json(
                {
                    "subscription_status": subscription.status,
                    "provider_subscription_id": subscription.provider_subscription_id,
                }
            ),
            created_at=now,
            updated_at=now,
        )
        session.add(billing_event)
        session.flush()
        return {
            "status": "processed",
            "idempotent": False,
            "provider": "sandbox",
            "provider_event_id": provider_event_id,
            "provider_session_id": billing_event.provider_session_id,
            "event": event_type,
            "plan": target_plan,
            "user_id": user_id,
            "subscription_status": subscription.status,
        }

    def _result_from_existing_event(self, session: Session, event: PlatformBillingEvent) -> Dict[str, Any]:
        checkout_status = None
        subscription_status = None
        if event.provider_session_id:
            checkout = session.execute(
                select(PlatformBillingCheckoutSession).where(
                    PlatformBillingCheckoutSession.provider_session_id == event.provider_session_id
                )
            ).scalars().first()
            checkout_status = checkout.status if checkout is not None else None
        if event.user_id is not None:
            subscription = session.execute(
                select(PlatformBillingSubscription).where(PlatformBillingSubscription.user_id == int(event.user_id))
            ).scalars().first()
            subscription_status = subscription.status if subscription is not None else None
        return {
            "status": "processed",
            "idempotent": True,
            "provider": event.provider,
            "provider_event_id": event.provider_event_id,
            "provider_session_id": event.provider_session_id,
            "event": event.event_type,
            "plan": event.plan,
            "user_id": event.user_id,
            "checkout_status": checkout_status,
            "subscription_status": subscription_status,
        }

    def _ensure_subscription(self, session: Session, *, user_id: int, provider: str) -> PlatformBillingSubscription:
        subscription = session.execute(
            select(PlatformBillingSubscription).where(PlatformBillingSubscription.user_id == int(user_id))
        ).scalars().first()
        if subscription is not None:
            return subscription
        user = session.get(PlatformUser, int(user_id))
        if user is None:
            raise ValueError("user_not_found")
        now = utc_naive_now()
        subscription = PlatformBillingSubscription(
            user_id=int(user_id),
            provider=provider,
            plan=user.plan or "free",
            status="none",
            created_at=now,
            updated_at=now,
        )
        session.add(subscription)
        session.flush()
        return subscription

    def _set_user_plan(self, session: Session, user_id: int, plan: str) -> PlatformUser:
        normalized_plan = self._normalize_plan(plan, allow_free=True)
        user = session.get(PlatformUser, int(user_id))
        if user is None:
            raise ValueError("user_not_found")
        user.plan = normalized_plan
        user.weekly_quota = PLATFORM_ANALYSIS_PLANS[normalized_plan]
        user.updated_at = utc_naive_now()
        return user

    def _find_event(self, session: Session, provider_event_id: str) -> Optional[PlatformBillingEvent]:
        return session.execute(
            select(PlatformBillingEvent).where(PlatformBillingEvent.provider_event_id == provider_event_id)
        ).scalars().first()

    def _provider_event_id(self, payload: Dict[str, Any]) -> str:
        explicit = str(payload.get("provider_event_id") or "").strip()
        if explicit:
            return explicit
        event_type = str(payload.get("event") or "").strip().lower()
        session_id = str(payload.get("provider_session_id") or "").strip()
        if event_type and session_id:
            return f"evt_{event_type.replace('.', '_')}_{session_id}"
        return ""

    def _normalize_plan(self, plan: str, *, allow_free: bool = False) -> str:
        normalized = (plan or "").strip().lower()
        allowed = set(PLATFORM_ANALYSIS_PLANS)
        if not allow_free:
            allowed.discard("free")
        if normalized not in allowed:
            raise ValueError("unsupported_plan")
        return normalized

    def _subscription_payload(
        self,
        row: Optional[PlatformBillingSubscription],
        *,
        user_id: int,
    ) -> Dict[str, Any]:
        if row is None:
            return {
                "user_id": user_id,
                "provider": "sandbox",
                "provider_subscription_id": None,
                "plan": "free",
                "status": "none",
                "current_period_start": None,
                "current_period_end": None,
                "expires_at": None,
                "created_at": None,
                "updated_at": None,
            }
        return {
            "user_id": int(row.user_id),
            "provider": row.provider,
            "provider_subscription_id": row.provider_subscription_id,
            "plan": row.plan,
            "status": row.status,
            "current_period_start": _iso(row.current_period_start),
            "current_period_end": _iso(row.current_period_end),
            "expires_at": _iso(row.expires_at),
            "created_at": _iso(row.created_at),
            "updated_at": _iso(row.updated_at),
        }

    def _checkout_payload(self, row: PlatformBillingCheckoutSession) -> Dict[str, Any]:
        return {
            "id": row.id,
            "user_id": int(row.user_id),
            "provider": row.provider,
            "provider_session_id": row.provider_session_id,
            "checkout_url": row.checkout_url,
            "plan": row.plan,
            "status": row.status,
            "product_type": row.product_type,
            "product_code": row.product_code,
            "created_at": _iso(row.created_at),
            "updated_at": _iso(row.updated_at),
        }

    def _event_payload(self, row: PlatformBillingEvent) -> Dict[str, Any]:
        try:
            metadata = json.loads(row.metadata_json or "{}")
        except (TypeError, ValueError):
            metadata = {}
        return {
            "id": row.id,
            "user_id": row.user_id,
            "provider": row.provider,
            "provider_event_id": row.provider_event_id,
            "provider_session_id": row.provider_session_id,
            "event_type": row.event_type,
            "plan": row.plan,
            "processing_status": row.processing_status,
            "metadata": metadata,
            "created_at": _iso(row.created_at),
            "updated_at": _iso(row.updated_at),
        }
