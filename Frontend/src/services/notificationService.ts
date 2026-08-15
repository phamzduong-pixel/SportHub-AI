import { apiRequest } from './apiClient';

export interface AppNotification {
  id: number; user_id: number; type: string; title: string; message: string;
  reference_type?: string; reference_id?: number; is_read: boolean;
  created_at: string; read_at?: string;
}
export interface NotificationList {
  items: AppNotification[]; total: number; unread_count: number; page: number; page_size: number;
}
export const getNotifications = () => apiRequest<NotificationList>('/notifications?page_size=100');
export const getUnreadCount = () => apiRequest<{ unread_count: number }>('/notifications/unread-count');
export const markNotificationRead = (id: number) => apiRequest<AppNotification>(`/notifications/${id}/read`, { method: 'PATCH' });
export const markAllNotificationsRead = () => apiRequest<{ updated_count: number }>('/notifications/read-all', { method: 'PATCH' });
