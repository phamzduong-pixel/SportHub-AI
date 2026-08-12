from sqlalchemy import select

from ..models.user import User


def management_owner_id(user: User, db) -> int | None:
    return user.id if user.role == 'OWNER' else None


def owns_field(user: User, field, db) -> bool:
    owner_id = management_owner_id(user, db)
    return owner_id is not None and (field.owner_id == owner_id or field.owner_id is None)
