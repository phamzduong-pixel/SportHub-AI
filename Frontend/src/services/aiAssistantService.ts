import { buildApiUrl, readToken } from '@/services/apiClient';

export interface AssistantSuggestion {
  facility_id: number | null; field_id: number; facility_name: string; court_name: string; field_name: string; sport_type: string; court_type: string | null; location: string; image_url: string | null;
  time_slot_id: number; time_slot_ids: number[]; selected_slots: { slot_id: number; start_time: string; end_time: string; price: number }[]; slot_name: string; start_time: string; end_time: string; price: number; duration_minutes: number;
  rating: number; distance_km: number | null; booking_date: string; reason: string; availability_status: 'available'; is_nearest_alternative: boolean; alternative_type: string | null;
}

export interface AssistantVenueResult {
  facility_id: number | null; field_id: number; facility_name: string; court_name: string;
  sport_type: string; court_type: string; location: string; base_price: number;
  rating: number; image_url: string | null;
}

export interface AssistantAction { label: string; route: string; kind: 'link' }

export interface AssistantResponse {
  reply: string;
  understood: Record<string, unknown>;
  suggestions: AssistantSuggestion[];
  venue_results: AssistantVenueResult[];
  intent: AssistantIntent;
  classification: 'IN_SCOPE' | 'OUT_OF_SCOPE' | 'UNCLEAR';
  confidence: number;
  entities: AssistantEntities;
  needs_clarification: boolean;
  source: 'live_backend' | 'backend_validation' | 'ai_validated' | 'ai_filtered' | 'fallback';
  status: 'OK' | 'NEED_MORE_DATA' | 'NO_AVAILABLE_SLOT' | 'NO_RESULT' | 'OUT_OF_SCOPE';
  missing_fields: string[];
  context_reset: boolean;
  partner_application_status: 'NONE' | 'PENDING' | 'APPROVED' | 'REJECTED' | null;
  action: AssistantAction | null;
}

export type AssistantIntent = 'SEARCH_VENUE' | 'RECOMMEND_VENUE' | 'CHECK_AVAILABILITY' | 'RECOMMEND_SLOT' | 'OCCUPANCY_INSIGHT' | 'PARTNER_APPLICATION_SUPPORT' | 'GET_VENUE_DETAIL' | 'CREATE_BOOKING' | 'GET_BOOKING' | 'CANCEL_BOOKING' | 'RESCHEDULE_BOOKING' | 'PAYMENT_SUPPORT' | 'ACCOUNT_SUPPORT' | 'SYSTEM_GUIDE' | 'GREETING' | 'FOLLOW_UP' | 'UNCLEAR' | 'OUT_OF_SCOPE';

export interface AssistantEntities {
  sport_type: string | null; court_type: string | null; venue_name: string | null; location: string | null; date: string | null;
  start_time: string | null; end_time: string | null; preferred_time: string | null; max_price: number | null; price_max?: number | null;
  number_of_players: number | null; booking_code: string | null;
}

export class AssistantTimeoutError extends Error {}
export class AssistantApiError extends Error {}

export async function askSportHubAssistant(message: string, contextFieldId?: number, context?: Record<string, unknown>, signal?: AbortSignal): Promise<AssistantResponse> {
  const payload = { message, context_field_id: contextFieldId || null, context: context || null };
  const controller = new AbortController();
  let timedOut = false;
  const abortFromCaller = () => controller.abort();
  signal?.addEventListener('abort', abortFromCaller, { once: true });
  const timeout = window.setTimeout(() => { timedOut = true; controller.abort(); }, 12_000);
  try {
    const token = readToken();
    const response = await fetch(buildApiUrl('/ai/assistant'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
    if (!response.ok) {
      const body = await response.json().catch(() => null) as { detail?: string } | null;
      throw new AssistantApiError(body?.detail || `SportHub API trả về lỗi ${response.status}`);
    }
    const result = await response.json() as AssistantResponse;
    return result;
  } catch (error) {
    if (timedOut) throw new AssistantTimeoutError('Assistant request timed out');
    throw error;
  } finally {
    window.clearTimeout(timeout);
    signal?.removeEventListener('abort', abortFromCaller);
  }
}
