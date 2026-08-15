import { apiRequest } from "./apiClient";

export type ProductType = "SELL" | "RENT" | "SERVICE";
export type ProductStatus = "ACTIVE" | "INACTIVE" | "ARCHIVED";

export interface FacilityProduct {
  id: number;
  facility_id: number;
  facility_name: string;
  name: string;
  product_type: ProductType;
  description: string | null;
  image_url: string | null;
  price: number;
  unit: string;
  status: ProductStatus;
  stock_quantity: number;
  reserved_quantity: number;
  available_quantity: number;
  track_inventory: boolean;
  is_available: boolean;
  sports: string[];
  has_booking_history: boolean;
  created_at: string;
  updated_at: string;
}
export interface ProductPayload {
  facility_id: number;
  name: string;
  product_type: ProductType;
  description: string | null;
  image_url: string | null;
  price: number;
  unit: string;
  sports: string[];
  status: ProductStatus;
  stock_quantity?: number;
  track_inventory?: boolean;
}
export interface StockMovement {
  id: number;
  product_id: number;
  booking_id: number | null;
  actor_id: number | null;
  movement_type:
    "IMPORT" | "SALE" | "RESERVE" | "RETURN" | "RELEASE" | "ADJUSTMENT";
  stock_delta: number;
  reserved_delta: number;
  stock_before: number;
  stock_after: number;
  reserved_before: number;
  reserved_after: number;
  note: string | null;
  created_at: string;
}
export interface ProductDeleteResult {
  message: string;
  action: "deleted" | "archived";
  product: FacilityProduct | null;
}
export interface ProductCatalogSuggestion {
  key: string;
  name: string;
  product_type: ProductType;
  unit: string;
  track_inventory: boolean;
  sport: string;
}

export const listProducts = (facilityId?: number, sport?: string) => {
  const query = new URLSearchParams();
  if (facilityId) query.set("facility_id", String(facilityId));
  if (sport) query.set("sport", sport);
  return apiRequest<FacilityProduct[]>(`/facility-products${query.size ? `?${query}` : ""}`);
};
export const getProductCatalog = (sport: string) =>
  apiRequest<ProductCatalogSuggestion[]>(`/facility-products/catalog?sport=${encodeURIComponent(sport)}`);
export const importProductCatalog = (payload: { facility_id: number; sport: string; catalog_keys: string[] }) =>
  apiRequest<FacilityProduct[]>("/facility-products/from-catalog", {
    method: "POST",
    body: JSON.stringify(payload),
  });
export const getBookingProductOptions = (bookingId: number) =>
  apiRequest<FacilityProduct[]>(`/bookings/${bookingId}/product-options`);
export const createProduct = (payload: ProductPayload) =>
  apiRequest<FacilityProduct>("/facility-products", {
    method: "POST",
    body: JSON.stringify(payload),
  });
export const updateProduct = (id: number, payload: ProductPayload) =>
  apiRequest<FacilityProduct>(`/facility-products/${id}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
export const setProductActive = (id: number, isActive: boolean) =>
  apiRequest<FacilityProduct>(`/facility-products/${id}/status`, {
    method: "PATCH",
    body: JSON.stringify({ is_active: isActive }),
  });
export const updateProductPrice = (id: number, price: number) =>
  apiRequest<FacilityProduct>(`/facility-products/${id}/price`, {
    method: "PATCH",
    body: JSON.stringify({ price }),
  });
export const deleteProduct = (id: number) =>
  apiRequest<ProductDeleteResult>(`/facility-products/${id}`, {
    method: "DELETE",
  });
export const unassignProductSport = (id: number, sport: string) =>
  apiRequest<FacilityProduct>(`/facility-products/${id}/sports?sport=${encodeURIComponent(sport)}`, {
    method: "DELETE",
  });
export const adjustInventory = (
  id: number,
  payload: {
    stock_quantity?: number;
    quantity_change?: number;
    track_inventory?: boolean;
    note: string;
  },
) =>
  apiRequest<FacilityProduct>(`/facility-products/${id}/inventory`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
export const getInventoryHistory = (id: number) =>
  apiRequest<StockMovement[]>(`/facility-products/${id}/inventory-history`);
