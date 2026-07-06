"""
NagaForge — in-app notifications (the engagement layer).

Writes rows into the existing `notifications` table so users get an activity
feed. Delivery to email/SMS is a later step; this is the in-app channel and is
fully functional today.

Resolution rules:
  - notify_username: exact username within the tenant (reliable — used for @mentions).
  - notify_person:   best-effort by full_name within the tenant (used for
                     sign-off events, where we only have the display name).
Both are no-ops if the target user can't be resolved (never raises).
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from sqlalchemy.orm import Session

import models

_log = logging.getLogger("nagaforge.notify")

MENTION_RE = re.compile(r"@([A-Za-z0-9_.-]{2,50})")


def _add(db: Session, user_id: int, title: str, message: str,
         ntype: str, entity_type: str, entity_id) -> Optional[models.Notification]:
    try:
        n = models.Notification(
            user_id=user_id, title=title[:300], message=message,
            type=ntype, entity_type=entity_type,
            entity_id=int(entity_id) if entity_id is not None else None,
            is_read=False,
        )
        db.add(n)
        db.flush()
        return n
    except Exception as exc:
        _log.warning("notification add failed: %s", exc)
        return None


def notify_username(db, company_id, username, title, message,
                    ntype="info", entity_type=None, entity_id=None, exclude_user_id=None):
    u = (db.query(models.User)
           .filter(models.User.username == username, models.User.company_id == company_id)
           .first())
    if u and u.id != exclude_user_id:
        return _add(db, u.id, title, message, ntype, entity_type, entity_id)
    return None


def notify_person(db, company_id, full_name, title, message,
                  ntype="info", entity_type=None, entity_id=None, exclude_user_id=None):
    if not full_name:
        return None
    u = (db.query(models.User)
           .filter(models.User.full_name == full_name, models.User.company_id == company_id)
           .first())
    if u and u.id != exclude_user_id:
        return _add(db, u.id, title, message, ntype, entity_type, entity_id)
    return None


def notify_mentions(db, company_id, body, title, message,
                    entity_type=None, entity_id=None, exclude_user_id=None):
    """Create a notification for every @username mentioned in `body`."""
    created = 0
    for uname in set(MENTION_RE.findall(body or "")):
        if notify_username(db, company_id, uname, title, message, "mention",
                           entity_type, entity_id, exclude_user_id):
            created += 1
    return created


def list_for_user(db, user_id, unread_only=False, limit=50):
    q = db.query(models.Notification).filter(models.Notification.user_id == user_id)
    if unread_only:
        q = q.filter(models.Notification.is_read == False)  # noqa: E712
    return q.order_by(models.Notification.created_at.desc()).limit(min(limit, 200)).all()
