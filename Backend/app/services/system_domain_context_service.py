"""
SystemDomainContextService — read-only access to the SportHub System Source-of-Truth.

Provides live data for AI modes about:
- Sport-level products/services (FacilityProduct + ProductSport, ACTIVE at APPROVED facilities)
- Sport-level amenities (Field/Facility amenities aggregated from sport-supporting venues ONLY)
- Venue-level amenities (Field.amenities + Facility.amenities for a specific field)
- Venue-level products (FacilityProduct for a specific facility)

Authorization rules (enforced here):
- Only FacilityProduct.status == ACTIVE
- Only Facility.status == APPROVED and Facility.is_active == True
- Never expose: raw stock counts, reserved_quantity, owner identity,
  payment info, booking data, or admin-scoped data
- is_available flag only (no internal inventory numbers)

Catalog vs Live distinction (mandatory):
- LIVE: FacilityProduct + ProductSport → what facilities are currently offering
- CATALOG: ProductCatalogItem → system suggestions, NOT live inventory
  These must NEVER be described as "currently available" or "đang có sẵn"
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..models.facility import Facility, FacilityStatus
from ..models.field import Field
from ..models.product import FacilityProduct, ProductCatalogItem, ProductSport, ProductStatus


# ── Sport resolution ────────────────────────────────────────────────────────

# Canonical sport names (Vietnamese)
SUPPORTED_SPORTS = frozenset({
    'bóng đá', 'cầu lông', 'pickleball', 'tennis', 'bóng rổ', 'bóng chuyền',
})

SPORT_ALIASES: dict[str, str] = {
    # bóng đá
    'bong da': 'bóng đá', 'da bong': 'bóng đá', 'san bong': 'bóng đá',
    'football': 'bóng đá', 'soccer': 'bóng đá', 'futsal': 'bóng đá',
    'bong da mini': 'bóng đá',
    # cầu lông
    'cau long': 'cầu lông', 'badminton': 'cầu lông',
    'danh cau long': 'cầu lông', 'choi cau long': 'cầu lông',
    # pickleball
    'pickleball': 'pickleball', 'pickle ball': 'pickleball',
    'danh pickleball': 'pickleball', 'choi pickleball': 'pickleball',
    # tennis
    'tennis': 'tennis', 'quan vot': 'tennis',
    'danh tennis': 'tennis', 'choi tennis': 'tennis',
    # bóng rổ
    'bong ro': 'bóng rổ', 'basketball': 'bóng rổ',
    'choi bong ro': 'bóng rổ',
    # bóng chuyền
    'bong chuyen': 'bóng chuyền', 'volleyball': 'bóng chuyền',
    'choi bong chuyen': 'bóng chuyền',
}


def _normalize(text: str) -> str:
    """Normalize Vietnamese text: lowercase, remove diacritics, collapse whitespace."""
    normalized = unicodedata.normalize('NFD', text.strip().casefold())
    plain = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn').replace('đ', 'd')
    return ' '.join(plain.split())


def resolve_sport(text: str) -> str | None:
    """Normalize text and resolve to a canonical sport name, or None if unrecognized."""
    if not text:
        return None
    key = _normalize(text)
    # Direct alias lookup
    if key in SPORT_ALIASES:
        return SPORT_ALIASES[key]
    # Check if canonical already
    for sport in SUPPORTED_SPORTS:
        if _normalize(sport) == key:
            return sport
    # Partial alias match (longer aliases first for specificity)
    for alias in sorted(SPORT_ALIASES, key=len, reverse=True):
        if alias in key or key in alias:
            return SPORT_ALIASES[alias]
    return None


# ── Data Transfer Objects ────────────────────────────────────────────────────

@dataclass
class LiveProductItem:
    """
    A product/service actively offered by a SportHub facility.
    Source: FacilityProduct (ACTIVE) at Facility (APPROVED, is_active).
    """
    name: str
    product_type: str          # SELL | RENT | SERVICE
    price: float
    unit: str
    is_available: bool         # track_inventory? (available_qty > 0) : always True
    facility_name: str         # which facility offers this


@dataclass
class CatalogSuggestion:
    """
    A product type defined in the SportHub product catalog.

    IMPORTANT: This is a SYSTEM SUGGESTION, not live inventory.
    Must NOT be described as "đang cung cấp", "hiện có sẵn", or similar.
    Use phrasing like "hệ thống gợi ý" / "danh mục tham khảo".
    """
    name: str
    product_type: str          # SELL | RENT | SERVICE
    unit: str
    sport: str                 # sport this suggestion applies to


@dataclass
class SportProductsContext:
    """
    Products/services context for a sport across all SportHub facilities.

    source field indicates data quality:
    - 'live'    : live FacilityProduct records found → real current offerings
    - 'catalog' : only ProductCatalogItem found → system suggestions only
    - 'both'    : both live and catalog data present
    - 'none'    : no data at all

    NEVER label catalog_items as "đang cung cấp" or "hiện có sẵn".
    """
    sport: str
    live_products: list[LiveProductItem]
    catalog_items: list[CatalogSuggestion]
    source: Literal['live', 'catalog', 'both', 'none']
    contributing_facility_count: int = 0   # how many facilities contribute live products


@dataclass
class VenueAmenityContext:
    """Amenities for a specific field and its parent facility."""
    field_id: int
    field_name: str
    facility_id: int | None
    facility_name: str | None
    field_amenities: list[str]
    facility_amenities: list[str]

    @property
    def all_amenities(self) -> list[str]:
        """Deduplicated union of field + facility amenities (field first)."""
        seen: set[str] = set()
        result: list[str] = []
        for a in (self.field_amenities or []) + (self.facility_amenities or []):
            key = a.strip().lower()
            if key and key not in seen:
                seen.add(key)
                result.append(a.strip())
        return result


@dataclass
class SportAmenityContext:
    """
    Amenities aggregated from venues confirmed to support a given sport.

    Note: amenities are gathered only from fields whose sport_type matches
    and from facilities that explicitly list the sport in Facility.sports.
    Different venues may have different amenities; this is an aggregate.
    """
    sport: str
    amenities: list[str]
    source_facility_count: int   # how many facilities contributed amenities
    has_data: bool


# ── Service ──────────────────────────────────────────────────────────────────

class SystemDomainContextService:
    """
    Read-only service exposing SportHub's System Source-of-Truth to the AI layer.

    Usage rules:
    - Never serialize the full database
    - Query only what the specific question requires
    - Distinguish LIVE (FacilityProduct) from CATALOG (ProductCatalogItem)
    - Do not expose private owner data, raw stock, payment, booking, or admin data
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    # ── Sport resolution ───────────────────────────────────────────────────

    @staticmethod
    def resolve_sport(text: str) -> str | None:
        """Return canonical sport name or None."""
        return resolve_sport(text)

    # ── Venue resolution ───────────────────────────────────────────────────

    def resolve_field(self, name_or_id: str | int) -> Field | None:
        """
        Resolve a field by id (int/digit string) or name substring.
        Only returns available fields at approved facilities.
        """
        # By ID
        if isinstance(name_or_id, int) or (isinstance(name_or_id, str) and str(name_or_id).isdigit()):
            fid = int(name_or_id)
            return self._db.scalar(
                select(Field)
                .options(selectinload(Field.facility))
                .where(Field.id == fid, Field.status == 'available')
            )

        # By name substring
        name_key = _normalize(str(name_or_id))
        if not name_key:
            return None
        candidates = self._db.scalars(
            select(Field)
            .options(selectinload(Field.facility))
            .where(Field.status == 'available')
        ).all()
        # Prefer exact name match, then facility name match
        for f in candidates:
            if name_key == _normalize(f.name):
                return f
        for f in candidates:
            if name_key in _normalize(f.name):
                return f
        for f in candidates:
            if f.facility and name_key in _normalize(f.facility.name):
                return f
        return None

    # ── Sport-level product lookup ─────────────────────────────────────────

    def get_sport_products(self, sport: str) -> SportProductsContext:
        """
        Return live products linked to sport via ProductSport at ACTIVE/APPROVED facilities.
        Falls back to ProductCatalogItem ONLY if no live products exist,
        and clearly marks catalog data as suggestions.
        """
        canonical = resolve_sport(sport) or sport
        sport_key = _normalize(canonical)
        common_key = _normalize('Dùng chung')

        # Query all ACTIVE products at APPROVED/active facilities
        products = self._db.scalars(
            select(FacilityProduct)
            .join(Facility, FacilityProduct.facility_id == Facility.id)
            .options(
                selectinload(FacilityProduct.sport_links),
                selectinload(FacilityProduct.facility),
            )
            .where(
                FacilityProduct.status == ProductStatus.ACTIVE.value,
                Facility.status == FacilityStatus.APPROVED.value,
                Facility.is_active.is_(True),
            )
            .order_by(FacilityProduct.name)
        ).unique().all()

        # Filter by sport via ProductSport links
        live_products: list[LiveProductItem] = []
        facility_names: set[str] = set()
        for p in products:
            sport_keys_for_product = {_normalize(link.sport_name) for link in p.sport_links}
            if sport_key in sport_keys_for_product or common_key in sport_keys_for_product:
                is_avail = not p.track_inventory or p.available_quantity > 0
                fac_name = p.facility.name if p.facility else ''
                live_products.append(LiveProductItem(
                    name=p.name,
                    product_type=p.product_type,
                    price=float(p.price),
                    unit=p.unit,
                    is_available=is_avail,
                    facility_name=fac_name,
                ))
                if fac_name:
                    facility_names.add(fac_name)

        # Only use catalog as fallback (never combined with live as "live")
        catalog_items: list[CatalogSuggestion] = []
        if not live_products:
            rows = self._db.scalars(
                select(ProductCatalogItem)
                .where(ProductCatalogItem.is_active.is_(True))
                .order_by(ProductCatalogItem.sort_order, ProductCatalogItem.id)
            ).all()
            for row in rows:
                row_key = _normalize(row.sport_name)
                if row_key == sport_key or row_key == common_key:
                    catalog_items.append(CatalogSuggestion(
                        name=row.name,
                        product_type=row.product_type,
                        unit=row.unit,
                        sport=canonical if row_key != common_key else 'Dùng chung',
                    ))

        if live_products and catalog_items:
            source: Literal['live', 'catalog', 'both', 'none'] = 'both'
        elif live_products:
            source = 'live'
        elif catalog_items:
            source = 'catalog'
        else:
            source = 'none'

        return SportProductsContext(
            sport=canonical,
            live_products=live_products,
            catalog_items=catalog_items,
            source=source,
            contributing_facility_count=len(facility_names),
        )

    # ── Sport-level amenity lookup ─────────────────────────────────────────

    def get_sport_amenities(self, sport: str) -> SportAmenityContext:
        """
        Aggregate amenities only from Fields/Facilities confirmed to support sport.

        - Field is included if Field.sport_type == sport (case-insensitive)
        - Facility is included if sport is listed in Facility.sports JSON array
        - Fields belonging to a sport-supporting facility are also included

        Does NOT assume all active amenities belong to this sport.
        Returns only what is deterministically linked to the sport.
        """
        canonical = resolve_sport(sport) or sport
        sport_key = _normalize(canonical)

        # Step 1: Find Fields whose sport_type matches
        matching_fields = self._db.scalars(
            select(Field)
            .options(selectinload(Field.facility))
            .where(
                Field.status == 'available',
                func.lower(Field.sport_type) == canonical.lower(),
            )
        ).all()

        # Step 2: Find Facilities that list this sport in their sports JSON
        # Load all APPROVED/active facilities, filter in Python (DB-agnostic JSON search)
        all_approved_facilities = self._db.scalars(
            select(Facility)
            .where(
                Facility.status == FacilityStatus.APPROVED.value,
                Facility.is_active.is_(True),
            )
        ).all()

        sport_facility_ids: set[int] = set()
        sport_facilities: list[Facility] = []
        for fac in all_approved_facilities:
            sports_list = fac.sports or []
            if any(_normalize(s) == sport_key for s in sports_list):
                sport_facility_ids.add(fac.id)
                sport_facilities.append(fac)

        # Also include facilities of matching fields (field sport_type is authoritative)
        fac_map: dict[int, Facility] = {fac.id: fac for fac in all_approved_facilities}
        for f in matching_fields:
            if f.facility_id and f.facility_id not in sport_facility_ids:
                sport_facility_ids.add(f.facility_id)
                if f.facility_id in fac_map:
                    sport_facilities.append(fac_map[f.facility_id])
                elif f.facility:
                    sport_facilities.append(f.facility)

        # Step 3: Aggregate amenities from confirmed sport-supporting sources
        seen: set[str] = set()
        amenities: list[str] = []

        # From matching fields (these are CONFIRMED sport fields)
        for f in matching_fields:
            for a in (f.amenities or []):
                key = a.strip().lower()
                if key and key not in seen:
                    seen.add(key)
                    amenities.append(a.strip())

        # From sport-supporting facilities (their facility-level amenities)
        unique_fac_ids_done: set[int] = set()
        for fac in sport_facilities:
            if fac.id in unique_fac_ids_done:
                continue
            unique_fac_ids_done.add(fac.id)
            for a in (fac.amenities or []):
                key = a.strip().lower()
                if key and key not in seen:
                    seen.add(key)
                    amenities.append(a.strip())

        return SportAmenityContext(
            sport=canonical,
            amenities=sorted(amenities),
            source_facility_count=len(unique_fac_ids_done),
            has_data=bool(amenities),
        )

    # ── Venue-level amenity lookup ─────────────────────────────────────────

    def get_venue_amenities(self, field_id: int) -> VenueAmenityContext | None:
        """
        Return Field.amenities + Facility.amenities for a specific field.
        Returns None if the field is not found or not available.
        """
        f = self._db.scalar(
            select(Field)
            .options(selectinload(Field.facility))
            .where(Field.id == field_id, Field.status == 'available')
        )
        if f is None:
            return None
        facility = f.facility
        return VenueAmenityContext(
            field_id=f.id,
            field_name=f.name,
            facility_id=facility.id if facility else None,
            facility_name=facility.name if facility else None,
            field_amenities=list(f.amenities or []),
            facility_amenities=list(facility.amenities or []) if facility else [],
        )

    # ── Venue-level product lookup ─────────────────────────────────────────

    def get_venue_products(
        self, facility_id: int, sport: str | None = None
    ) -> list[LiveProductItem]:
        """
        Return ACTIVE FacilityProduct records for a specific facility.
        Optionally filtered by sport via ProductSport links.
        Only returns products from APPROVED/active facilities.
        """
        query = (
            select(FacilityProduct)
            .join(Facility, FacilityProduct.facility_id == Facility.id)
            .options(
                selectinload(FacilityProduct.sport_links),
                selectinload(FacilityProduct.facility),
            )
            .where(
                FacilityProduct.facility_id == facility_id,
                FacilityProduct.status == ProductStatus.ACTIVE.value,
                Facility.status == FacilityStatus.APPROVED.value,
                Facility.is_active.is_(True),
            )
            .order_by(FacilityProduct.name)
        )
        products = self._db.scalars(query).unique().all()

        if sport:
            sport_key = _normalize(resolve_sport(sport) or sport)
            common_key = _normalize('Dùng chung')
            products = [
                p for p in products
                if sport_key in {_normalize(link.sport_name) for link in p.sport_links}
                or common_key in {_normalize(link.sport_name) for link in p.sport_links}
            ]

        result: list[LiveProductItem] = []
        for p in products:
            is_avail = not p.track_inventory or p.available_quantity > 0
            result.append(LiveProductItem(
                name=p.name,
                product_type=p.product_type,
                price=float(p.price),
                unit=p.unit,
                is_available=is_avail,
                facility_name=p.facility.name if p.facility else '',
            ))
        return result
