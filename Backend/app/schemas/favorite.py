from datetime import datetime
from pydantic import BaseModel
class FavoriteFieldResponse(BaseModel):
    field_id: int; field_name: str; sport_type: str; location: str; image_url: str | None
    price: float; rating: float; review_count: int; distance_km: float | None
    status: str; has_availability: bool; next_slot: str | None; created_at: datetime
class FavoriteStatusResponse(BaseModel):
    field_id: int; is_favorite: bool
