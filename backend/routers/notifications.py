"""
In-app notifications feed — the user's activity inbox.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from auth import get_current_user
import models
import notify

router = APIRouter(prefix="/notifications", tags=["Notifications"])


def _dict(n: models.Notification) -> dict:
    return {"id": n.id, "title": n.title, "message": n.message, "type": n.type,
            "entity_type": n.entity_type, "entity_id": n.entity_id,
            "is_read": bool(n.is_read), "created_at": n.created_at}


@router.get("/")
def my_notifications(unread_only: bool = False, limit: int = 50,
                     current_user: models.User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    rows = notify.list_for_user(db, current_user.id, unread_only, limit)
    unread = (db.query(models.Notification)
                .filter(models.Notification.user_id == current_user.id,
                        models.Notification.is_read == False)  # noqa: E712
                .count())
    return {"unread_count": unread, "items": [_dict(n) for n in rows]}


@router.post("/{notif_id}/read")
def mark_read(notif_id: int, current_user: models.User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    n = (db.query(models.Notification)
           .filter(models.Notification.id == notif_id,
                   models.Notification.user_id == current_user.id).first())
    if not n:
        raise HTTPException(status_code=404, detail="Notification not found")
    n.is_read = True
    db.commit()
    return {"ok": True}


@router.post("/read-all")
def mark_all_read(current_user: models.User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    updated = (db.query(models.Notification)
                 .filter(models.Notification.user_id == current_user.id,
                         models.Notification.is_read == False)  # noqa: E712
                 .update({models.Notification.is_read: True}))
    db.commit()
    return {"ok": True, "marked_read": updated}
