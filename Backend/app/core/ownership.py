from sqlalchemy import select

from ..models.user import User


def management_owner_id(user: User, db) -> int | None:
    if user.role == 'OWNER':
        return user.id
    if user.role == 'MANAGER' and user.owner_id:
        owner = db.get(User, user.owner_id)
        return owner.id if owner and owner.role == 'OWNER' and owner.is_active else None
    return None


def owns_field(user: User, field, db) -> bool:
    owner_id = management_owner_id(user, db)
    return owner_id is not None and (field.owner_id == owner_id or field.owner_id is None)
