export type ManagementModule =
  | "dashboard"
  | "calendar"
  | "bookings"
  | "venues"
  | "courts"
  | "schedules"
  | "maintenance"
  | "pricing"
  | "products"
  | "customers"
  | "payments"
  | "reports"
  | "ai"
  | "settings";
export type PermissionAction =
  "view" | "create" | "update" | "delete" | "confirm" | "export";
export type ManagementRole = "OWNER";
export interface ManagementUser {
  id: string;
  name: string;
  email: string;
  role: ManagementRole;
  title: string;
  avatar: string;
  avatarUrl: string | null;
  venueIds: string[];
  status: "active" | "invited" | "disabled";
  lastActive: string;
}
