from sqlalchemy import String, and_, func, or_, select
from sqlalchemy.orm import Session

from ..models.field import Booking, Field
from ..models.facility import Facility
from ..models.product import FacilityProduct, ProductStatus

class FieldRepository:
    def __init__(self, db: Session):
        self.db = db

    def list(self, *, search: str | None, sport_type: str | None, status: str | None, page: int, page_size: int, owner_id: int | None = None, facility_active: bool | None = None, amenities: list[str] | None = None):
        filters = []
        if owner_id is not None:
            filters.append(or_(Field.owner_id == owner_id, Field.owner_id.is_(None)))
        if search:
            filters.append(Field.name.ilike(f'%{search.strip()}%'))
        if sport_type:
            st = sport_type.strip()
            st_norm = st.lower()
            filters.append(or_(
                Field.sport_type == st,
                func.lower(Field.sport_type) == st_norm,
                Field.sport_type.ilike(f'%{st}%'),
                Field.sport_type.ilike(f'%{st_norm}%'),
            ))
        if status:
            filters.append(Field.status == status)
        if facility_active is not None:
            filters.append(or_(Field.facility_id.is_(None), Field.facility.has(and_(Facility.is_active.is_(facility_active), Facility.status == 'APPROVED'))))
        if amenities:
            clean_amenities = [
                a.strip() for a in amenities
                if a and a.strip() and a.strip() not in ('[]', '""', "''", 'null', 'undefined')
            ]
            for name_clean in clean_amenities:
                prod_subquery = (
                    select(FacilityProduct.facility_id)
                    .where(
                        or_(
                            FacilityProduct.name == name_clean,
                            func.lower(FacilityProduct.name) == name_clean.lower(),
                            FacilityProduct.name.ilike(name_clean),
                        ),
                        FacilityProduct.status == ProductStatus.ACTIVE.value,
                    )
                )
                filters.append(or_(
                    Field.facility_id.in_(prod_subquery),
                    func.cast(Field.amenities, String).ilike(f'%"{name_clean}"%'),
                ))
        total = self.db.scalar(select(func.count(Field.id)).where(*filters)) or 0
        items = list(self.db.scalars(
            select(Field).where(*filters).order_by(Field.created_at.desc(), Field.id.desc()).offset((page - 1) * page_size).limit(page_size)
        ).all())
        if items:
            facility_ids = [f.facility_id for f in items if f.facility_id]
            if facility_ids:
                active_prods = self.db.execute(
                    select(FacilityProduct.facility_id, FacilityProduct.name).where(
                        FacilityProduct.facility_id.in_(facility_ids),
                        FacilityProduct.status == ProductStatus.ACTIVE.value,
                    )
                ).all()
                fac_prod_map = {}
                for fac_id, prod_name in active_prods:
                    fac_prod_map.setdefault(fac_id, set()).add(prod_name)
                for f in items:
                    if f.facility_id and f.facility_id in fac_prod_map:
                        f.amenities = list(set((f.amenities or []) + list(fac_prod_map[f.facility_id])))
        return items, total

    def get(self, field_id: int) -> Field | None:
        return self.db.get(Field, field_id)

    def create(self, data: dict) -> Field:
        field = Field(**data)
        self.db.add(field)
        self.db.commit()
        self.db.refresh(field)
        return field

    def update(self, field: Field, data: dict) -> Field:
        for key, value in data.items():
            setattr(field, key, value)
        self.db.commit()
        self.db.refresh(field)
        return field

    def delete(self, field: Field):
        self.db.delete(field)
        self.db.commit()

    def has_booking_usage(self, field_id: int) -> bool:
        return self.db.scalar(select(Booking.id).where(Booking.field_id == field_id).limit(1)) is not None
