# -*- coding: utf-8 -*-
"""Ownership-safe support ticket operations for the DSA platform."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.storage import (
    DatabaseManager,
    PlatformSupportMessage,
    PlatformSupportTicket,
    PlatformUser,
    utc_naive_now,
)


SUPPORT_STATUSES = frozenset({"open", "in_progress", "closed"})


def _utc_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    normalized = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    return normalized.isoformat()


class SupportTicketNotFound(ValueError):
    pass


class SupportTicketClosed(ValueError):
    pass


class SupportInvalidStatus(ValueError):
    pass


class PlatformSupportService:
    def __init__(self, db_manager: DatabaseManager | None = None) -> None:
        self.db = db_manager or DatabaseManager.get_instance()

    @staticmethod
    def _message_payload(message: PlatformSupportMessage) -> dict[str, Any]:
        return {
            "id": int(message.id),
            "ticket_id": int(message.ticket_id),
            "author_role": message.author_role,
            "body": message.body,
            "created_at": _utc_iso(message.created_at),
        }

    @staticmethod
    def _ticket_payload(
        ticket: PlatformSupportTicket,
        *,
        requester_email: str | None,
        message_count: int,
    ) -> dict[str, Any]:
        return {
            "id": int(ticket.id),
            "user_id": int(ticket.user_id),
            "requester_email": requester_email,
            "category": ticket.category,
            "subject": ticket.subject,
            "status": ticket.status,
            "unread_by_user": bool(ticket.unread_by_user),
            "unread_by_admin": bool(ticket.unread_by_admin),
            "message_count": int(message_count),
            "created_at": _utc_iso(ticket.created_at),
            "updated_at": _utc_iso(ticket.updated_at),
            "closed_at": _utc_iso(ticket.closed_at),
        }

    def _detail_payload(self, session: Session, ticket: PlatformSupportTicket) -> dict[str, Any]:
        requester_email = session.execute(
            select(PlatformUser.email).where(PlatformUser.id == int(ticket.user_id))
        ).scalar_one_or_none()
        messages = session.execute(
            select(PlatformSupportMessage)
            .where(PlatformSupportMessage.ticket_id == int(ticket.id))
            .order_by(PlatformSupportMessage.created_at.asc(), PlatformSupportMessage.id.asc())
        ).scalars().all()
        return {
            **self._ticket_payload(
                ticket,
                requester_email=requester_email,
                message_count=len(messages),
            ),
            "messages": [self._message_payload(message) for message in messages],
        }

    @staticmethod
    def _owned_ticket(session: Session, user_id: int, ticket_id: int) -> PlatformSupportTicket:
        ticket = session.execute(
            select(PlatformSupportTicket).where(
                PlatformSupportTicket.id == int(ticket_id),
                PlatformSupportTicket.user_id == int(user_id),
            )
        ).scalars().first()
        if ticket is None:
            raise SupportTicketNotFound("support ticket not found")
        return ticket

    @staticmethod
    def _admin_ticket(session: Session, ticket_id: int) -> PlatformSupportTicket:
        ticket = session.execute(
            select(PlatformSupportTicket).where(PlatformSupportTicket.id == int(ticket_id))
        ).scalars().first()
        if ticket is None:
            raise SupportTicketNotFound("support ticket not found")
        return ticket

    def create_ticket(self, *, user_id: int, category: str, subject: str, message: str) -> dict[str, Any]:
        now = utc_naive_now()
        with self.db.session_scope() as session:
            ticket = PlatformSupportTicket(
                user_id=int(user_id),
                category=category,
                subject=subject.strip(),
                status="open",
                unread_by_user=False,
                unread_by_admin=True,
                created_at=now,
                updated_at=now,
            )
            session.add(ticket)
            session.flush()
            session.add(
                PlatformSupportMessage(
                    ticket_id=int(ticket.id),
                    author_role="user",
                    body=message.strip(),
                    created_at=now,
                )
            )
            session.flush()
            return self._detail_payload(session, ticket)

    def list_user_tickets(self, *, user_id: int, limit: int = 100) -> list[dict[str, Any]]:
        capped_limit = max(1, min(int(limit or 100), 200))
        with self.db.get_session() as session:
            rows = session.execute(
                select(
                    PlatformSupportTicket,
                    PlatformUser.email,
                    func.count(PlatformSupportMessage.id),
                )
                .join(PlatformUser, PlatformUser.id == PlatformSupportTicket.user_id)
                .outerjoin(PlatformSupportMessage, PlatformSupportMessage.ticket_id == PlatformSupportTicket.id)
                .where(PlatformSupportTicket.user_id == int(user_id))
                .group_by(PlatformSupportTicket.id, PlatformUser.email)
                .order_by(PlatformSupportTicket.updated_at.desc(), PlatformSupportTicket.id.desc())
                .limit(capped_limit)
            ).all()
            return [
                self._ticket_payload(ticket, requester_email=email, message_count=count)
                for ticket, email, count in rows
            ]

    def user_summary(self, *, user_id: int) -> dict[str, int]:
        with self.db.get_session() as session:
            unread_count = session.execute(
                select(func.count(PlatformSupportTicket.id)).where(
                    PlatformSupportTicket.user_id == int(user_id),
                    PlatformSupportTicket.unread_by_user.is_(True),
                )
            ).scalar_one()
            active_count = session.execute(
                select(func.count(PlatformSupportTicket.id)).where(
                    PlatformSupportTicket.user_id == int(user_id),
                    PlatformSupportTicket.status != "closed",
                )
            ).scalar_one()
            return {
                "unread_count": int(unread_count or 0),
                "active_count": int(active_count or 0),
            }

    def get_user_ticket(self, *, user_id: int, ticket_id: int) -> dict[str, Any]:
        with self.db.session_scope() as session:
            ticket = self._owned_ticket(session, user_id, ticket_id)
            if ticket.unread_by_user:
                ticket.unread_by_user = False
                ticket.updated_at = ticket.updated_at or utc_naive_now()
                session.flush()
            return self._detail_payload(session, ticket)

    def add_user_message(self, *, user_id: int, ticket_id: int, message: str) -> dict[str, Any]:
        now = utc_naive_now()
        with self.db.session_scope() as session:
            ticket = self._owned_ticket(session, user_id, ticket_id)
            if ticket.status == "closed":
                raise SupportTicketClosed("closed support tickets cannot receive messages")
            session.add(
                PlatformSupportMessage(
                    ticket_id=int(ticket.id),
                    author_role="user",
                    body=message.strip(),
                    created_at=now,
                )
            )
            ticket.unread_by_admin = True
            ticket.unread_by_user = False
            ticket.updated_at = now
            session.flush()
            return self._detail_payload(session, ticket)

    def close_user_ticket(self, *, user_id: int, ticket_id: int) -> dict[str, Any]:
        now = utc_naive_now()
        with self.db.session_scope() as session:
            ticket = self._owned_ticket(session, user_id, ticket_id)
            if ticket.status != "closed":
                ticket.status = "closed"
                ticket.closed_at = now
                ticket.updated_at = now
                ticket.unread_by_admin = True
                session.flush()
            return self._detail_payload(session, ticket)

    def list_admin_tickets(self, *, status: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        normalized_status = status.strip().lower() if status else None
        if normalized_status and normalized_status not in SUPPORT_STATUSES:
            raise SupportInvalidStatus("unsupported support ticket status")
        capped_limit = max(1, min(int(limit or 200), 500))
        with self.db.get_session() as session:
            statement = (
                select(
                    PlatformSupportTicket,
                    PlatformUser.email,
                    func.count(PlatformSupportMessage.id),
                )
                .join(PlatformUser, PlatformUser.id == PlatformSupportTicket.user_id)
                .outerjoin(PlatformSupportMessage, PlatformSupportMessage.ticket_id == PlatformSupportTicket.id)
                .group_by(PlatformSupportTicket.id, PlatformUser.email)
                .order_by(
                    PlatformSupportTicket.unread_by_admin.desc(),
                    PlatformSupportTicket.updated_at.desc(),
                    PlatformSupportTicket.id.desc(),
                )
                .limit(capped_limit)
            )
            if normalized_status:
                statement = statement.where(PlatformSupportTicket.status == normalized_status)
            rows = session.execute(statement).all()
            return [
                self._ticket_payload(ticket, requester_email=email, message_count=count)
                for ticket, email, count in rows
            ]

    def admin_summary(self) -> dict[str, Any]:
        with self.db.get_session() as session:
            unread_count = session.execute(
                select(func.count(PlatformSupportTicket.id)).where(
                    PlatformSupportTicket.unread_by_admin.is_(True),
                )
            ).scalar_one()
            pending_count = session.execute(
                select(func.count(PlatformSupportTicket.id)).where(
                    PlatformSupportTicket.status != "closed",
                )
            ).scalar_one()
            oldest_pending_at = session.execute(
                select(func.min(PlatformSupportTicket.created_at)).where(
                    PlatformSupportTicket.status != "closed",
                )
            ).scalar_one_or_none()
            return {
                "unread_count": int(unread_count or 0),
                "pending_count": int(pending_count or 0),
                "oldest_pending_at": _utc_iso(oldest_pending_at),
            }

    def get_admin_ticket(self, *, ticket_id: int) -> dict[str, Any]:
        with self.db.session_scope() as session:
            ticket = self._admin_ticket(session, ticket_id)
            if ticket.unread_by_admin:
                ticket.unread_by_admin = False
                session.flush()
            return self._detail_payload(session, ticket)

    def add_admin_message(self, *, ticket_id: int, message: str) -> dict[str, Any]:
        now = utc_naive_now()
        with self.db.session_scope() as session:
            ticket = self._admin_ticket(session, ticket_id)
            if ticket.status == "closed":
                raise SupportTicketClosed("closed support tickets cannot receive messages")
            session.add(
                PlatformSupportMessage(
                    ticket_id=int(ticket.id),
                    author_role="admin",
                    body=message.strip(),
                    created_at=now,
                )
            )
            ticket.status = "in_progress"
            ticket.unread_by_user = True
            ticket.unread_by_admin = False
            ticket.updated_at = now
            session.flush()
            return self._detail_payload(session, ticket)

    def update_admin_status(self, *, ticket_id: int, status: str) -> dict[str, Any]:
        normalized_status = status.strip().lower()
        if normalized_status not in SUPPORT_STATUSES:
            raise SupportInvalidStatus("unsupported support ticket status")
        now = utc_naive_now()
        with self.db.session_scope() as session:
            ticket = self._admin_ticket(session, ticket_id)
            if ticket.status != normalized_status:
                ticket.status = normalized_status
                ticket.closed_at = now if normalized_status == "closed" else None
                ticket.updated_at = now
                ticket.unread_by_user = True
                ticket.unread_by_admin = False
                session.flush()
            return self._detail_payload(session, ticket)
