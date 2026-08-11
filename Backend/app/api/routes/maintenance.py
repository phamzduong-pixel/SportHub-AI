from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...database.session import get_db
from ...models.user import User
from ...schemas.maintenance import MaintenanceCreate, MaintenanceResponse, MaintenanceSummary, MaintenanceUpdate
from ...services.maintenance_service import MaintenanceService
from ..dependencies import require_permission

router = APIRouter(prefix='/maintenance', tags=['maintenance'])


@router.get('', response_model=list[MaintenanceResponse])
def list_maintenance(field_id: int | None = Query(None, gt=0), facility_id: int | None = Query(None, gt=0),
                     status: str | None = Query(None, pattern='^(SCHEDULED|IN_PROGRESS|COMPLETED|CANCELLED)$'),
                     maintenance_type: str | None = Query(None, max_length=40), date_from: date | None = None,
                     date_to: date | None = None, user: User = Depends(require_permission('maintenance.view')),
                     db: Session = Depends(get_db)):
    return MaintenanceService(db).list(user, field_id=field_id, facility_id=facility_id, status=status,
                                       maintenance_type=maintenance_type, date_from=date_from, date_to=date_to)


@router.get('/summary', response_model=MaintenanceSummary)
def maintenance_summary(user: User = Depends(require_permission('maintenance.view')), db: Session = Depends(get_db)):
    return MaintenanceService(db).summary(user)


@router.post('', response_model=MaintenanceResponse, status_code=201)
def create_maintenance(payload: MaintenanceCreate, user: User = Depends(require_permission('maintenance.manage')), db: Session = Depends(get_db)):
    return MaintenanceService(db).create(payload, user)


@router.put('/{maintenance_id}', response_model=MaintenanceResponse)
def update_maintenance(maintenance_id: int, payload: MaintenanceUpdate, user: User = Depends(require_permission('maintenance.manage')), db: Session = Depends(get_db)):
    return MaintenanceService(db).update(maintenance_id, payload, user)


@router.patch('/{maintenance_id}/start', response_model=MaintenanceResponse)
def start_maintenance(maintenance_id: int, user: User = Depends(require_permission('maintenance.manage')), db: Session = Depends(get_db)):
    return MaintenanceService(db).transition(maintenance_id, 'IN_PROGRESS', user)


@router.patch('/{maintenance_id}/complete', response_model=MaintenanceResponse)
def complete_maintenance(maintenance_id: int, user: User = Depends(require_permission('maintenance.manage')), db: Session = Depends(get_db)):
    return MaintenanceService(db).transition(maintenance_id, 'COMPLETED', user)


@router.patch('/{maintenance_id}/cancel', response_model=MaintenanceResponse)
def cancel_maintenance(maintenance_id: int, user: User = Depends(require_permission('maintenance.manage')), db: Session = Depends(get_db)):
    return MaintenanceService(db).transition(maintenance_id, 'CANCELLED', user)
