from ..core.ownership import management_owner_id
from ..models.operations import AuditLog


def record_audit(db, user, entity_type: str, entity_id: int | None, action: str, changes: dict | None = None):
    db.add(AuditLog(
        owner_id=management_owner_id(user, db), actor_id=user.id, actor_role=user.role,
        entity_type=entity_type, entity_id=entity_id, action=action, changes=changes or {},
    ))
