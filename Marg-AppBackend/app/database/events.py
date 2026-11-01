"""
Global ORM event hooks.

Optimistic-concurrency version maintenance: every modified row that carries
a ``version`` column (AuditMixin) gets its version incremented exactly once
per flush, unless the handler already changed ``version`` explicitly. This
makes offline-sync conflict detection reliable across all modules without
relying on each router remembering ``obj.version += 1``.
"""

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from app.models.base import AuditMixin


@event.listens_for(Session, "before_flush")
def _bump_versions(session: Session, flush_context, instances) -> None:
    for obj in session.dirty:
        if not isinstance(obj, AuditMixin):
            continue
        if not session.is_modified(obj, include_collections=False):
            continue
        state = inspect(obj)
        if state.attrs.version.history.has_changes():
            continue  # handler bumped it explicitly
        obj.version = (obj.version or 1) + 1
